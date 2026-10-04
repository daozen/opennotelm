"""Opt-in anonymous events. No browser SDK, arbitrary properties or model client."""

import asyncio
import json
import platform
import sqlite3
import time
from typing import Literal
from urllib.parse import urlsplit
from uuid import UUID, uuid4

import httpx
from pydantic import ConfigDict, Field, field_validator

from . import __version__
from .error_codes import safe_error_code
from .model_service import now
from .schemas import StrictModel

EventName = Literal[
    "app_started",
    "source_import_started",
    "source_import_completed",
    "source_import_failed",
    "chat_message_sent",
    "chat_response_completed",
    "chat_response_failed",
    "knowledge_generated",
    "knowledge_updated",
    "deck_generation_started",
    "deck_generation_completed",
    "deck_generation_failed",
    "slide_regenerated",
    "slide_revised",
    "pdf_exported",
    "model_connection_tested",
]


class EventProperties(StrictModel):
    model_config = ConfigDict(
        extra="forbid", strict=True, frozen=True, revalidate_instances="always"
    )
    source_type: Literal["epub", "pdf", "markdown", "text", "docx", "web"] | None = None
    size_bucket: Literal["under_1mb", "1_to_10mb", "10_to_50mb", "50mb_plus"] | None = None
    slide_count: int | None = Field(default=None, ge=0, le=20)
    duration_ms: int | None = Field(default=None, ge=0, le=86400000)
    error_code: str | None = None

    @field_validator("error_code")
    @classmethod
    def known_error(cls, value):
        return safe_error_code(value)

    @field_validator("duration_ms")
    @classmethod
    def bucket_duration(cls, value):
        if value is None:
            return None
        return next(
            bound for bound in (1000, 10000, 60000, 300000, 3600000, 86400000) if value <= bound
        )


class Event(StrictModel):
    name: EventName
    properties: EventProperties


def current_os():
    return {"Darwin": "macos", "Linux": "linux", "Windows": "windows"}.get(
        platform.system(), "other"
    )


def size_bucket(size):
    return (
        "under_1mb"
        if size < 1024**2
        else "1_to_10mb"
        if size < 10 * 1024**2
        else "10_to_50mb"
        if size < 50 * 1024**2
        else "50mb_plus"
    )


class TelemetryService:
    def __init__(self, db, settings, transport=None):
        self.db, self.settings, self.transport = db, settings, transport
        self.task = None
        self.send_lock = asyncio.Lock()
        with db.connect() as conn:
            conn.execute(
                "INSERT OR IGNORE INTO app_settings VALUES ('anonymous_install_id',?)",
                (json.dumps(str(uuid4())),),
            )
            self.install_id = str(
                UUID(
                    json.loads(
                        conn.execute(
                            "SELECT value_json FROM app_settings WHERE key='anonymous_install_id'"
                        ).fetchone()[0]
                    )
                )
            )
            self.prune(conn)
            if not self.enabled(conn):
                conn.execute("DELETE FROM telemetry_queue")

    def configured(self):
        try:
            url = urlsplit(self.settings.telemetry_host)
        except ValueError:
            return False
        return bool(
            self.settings.telemetry_project_token
            and url.hostname
            and not url.username
            and not url.password
            and not url.query
            and not url.fragment
            and (
                url.scheme == "https"
                or url.scheme == "http"
                and url.hostname in ("localhost", "127.0.0.1", "::1")
            )
        )

    def enabled(self, conn=None):
        if conn is None:
            with self.db.connect() as connection:
                return self.enabled(connection)
        row = conn.execute("SELECT value_json FROM app_settings WHERE key='preferences'").fetchone()
        return bool(row and json.loads(row[0]).get("telemetry_enabled") is True)

    def status(self):
        with self.db.connect() as conn:
            return {
                "enabled": self.enabled(conn),
                "configured": self.configured(),
                "queued_events": conn.execute("SELECT count(*) FROM telemetry_queue").fetchone()[0],
            }

    def prune(self, conn):
        conn.execute(
            "DELETE FROM telemetry_queue WHERE queued_at<?", (int(time.time()) - 7 * 86400,)
        )
        conn.execute(
            "DELETE FROM telemetry_queue WHERE id IN (SELECT id FROM telemetry_queue "
            "ORDER BY queued_at DESC,rowid DESC LIMIT -1 OFFSET 1000)"
        )

    def capture(self, name: EventName, properties: EventProperties | None = None):
        if properties is not None and not isinstance(properties, EventProperties):
            raise TypeError("Telemetry requires typed, allowlisted properties")
        event = Event(name=name, properties=properties or EventProperties())
        try:
            with self.db.connect() as conn:
                conn.execute("BEGIN IMMEDIATE")
                if not self.enabled(conn):
                    return
                conn.execute(
                    "INSERT INTO telemetry_queue VALUES (?,?,?,?,?)",
                    (
                        str(uuid4()),
                        event.name,
                        event.properties.model_dump_json(exclude_none=True),
                        now(),
                        int(time.time()),
                    ),
                )
                self.prune(conn)
        except sqlite3.Error:
            # Optional analytics must never make an otherwise successful action fail.
            return

    async def set_enabled(self, enabled):
        return await self.set_preferences({"telemetry_enabled": enabled})

    async def set_preferences(self, changes):
        # The response is returned only after any earlier transmission finishes.
        async with self.send_lock:
            with self.db.connect() as conn:
                conn.execute("BEGIN IMMEDIATE")
                row = conn.execute(
                    "SELECT value_json FROM app_settings WHERE key='preferences'"
                ).fetchone()
                preferences = {"telemetry_enabled": False}
                if row:
                    preferences.update(json.loads(row[0]))
                preferences.update(changes)
                conn.execute(
                    "INSERT INTO app_settings VALUES ('preferences',?) ON CONFLICT(key) "
                    "DO UPDATE SET value_json=excluded.value_json",
                    (json.dumps(preferences),),
                )
                if not preferences["telemetry_enabled"]:
                    conn.execute("DELETE FROM telemetry_queue")
        return {"ui_language": None} | preferences

    async def send_once(self):
        async with self.send_lock:
            if not self.configured() or not self.enabled():
                return True
            with self.db.connect() as conn:
                self.prune(conn)
                rows = conn.execute(
                    "SELECT * FROM telemetry_queue ORDER BY queued_at,rowid LIMIT 50"
                ).fetchall()
            if not rows:
                return True
            batch, valid_ids, invalid_ids = [], [], []
            for row in rows:
                try:
                    event = Event(
                        name=row["event"],
                        properties=EventProperties.model_validate_json(row["properties_json"]),
                    )
                    identity = str(UUID(row["id"]))
                except (ValueError, TypeError):
                    invalid_ids.append((row["id"],))
                    continue
                batch.append(
                    {
                        "uuid": identity,
                        "event": event.name,
                        "distinct_id": self.install_id,
                        "properties": {
                            **event.properties.model_dump(exclude_none=True),
                            "app_version": __version__,
                            "os": current_os(),
                            "$process_person_profile": False,
                            "$geoip_disable": True,
                        },
                    }
                )
                valid_ids.append((row["id"],))
            with self.db.connect() as conn:
                conn.executemany("DELETE FROM telemetry_queue WHERE id=?", invalid_ids)
            if not batch:
                return True
            try:
                # Separate client: never inherit model credentials, cookies or proxy settings.
                async with httpx.AsyncClient(
                    timeout=5, follow_redirects=False, trust_env=False, transport=self.transport
                ) as client:
                    async with client.stream(
                        "POST",
                        self.settings.telemetry_host.rstrip("/") + "/batch/",
                        json={"api_key": self.settings.telemetry_project_token, "batch": batch},
                    ) as response:
                        if not 200 <= response.status_code < 300:
                            return False
            except httpx.HTTPError:
                return False
            with self.db.connect() as conn:
                conn.executemany("DELETE FROM telemetry_queue WHERE id=?", valid_ids)
            return True

    def start(self):
        self.capture("app_started")
        self.task = asyncio.create_task(self.run())

    async def run(self):
        delay = 60
        while True:
            await asyncio.sleep(delay)
            try:
                success = await self.send_once()
            except sqlite3.Error:
                success = False
            delay = 60 if success else min(3600, delay * 2)

    async def stop(self):
        if self.task:
            self.task.cancel()
            try:
                await self.task
            except asyncio.CancelledError:
                pass
