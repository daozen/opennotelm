import json
import os
from datetime import UTC, datetime

from .db import Database
from .embedding_identity import index_signature, saved_signature
from .errors import AppError
from .gateway import ModelGateway
from .schemas import ModelInput
from .secrets import SecretStore


def now() -> str:
    return datetime.now(UTC).isoformat()


class ModelService:
    def __init__(self, db: Database, secrets: SecretStore, gateway: ModelGateway):
        self.db, self.secrets, self.gateway = db, secrets, gateway
        self.indexes = None

    def public_configs(self) -> dict:
        with self.db.connect() as conn:
            configs = {}
            for row in conn.execute("SELECT * FROM model_configs"):
                configs[row["role"]] = {
                    "base_url": row["base_url"],
                    "model_id": row["model_id"],
                    "max_context_tokens": row["max_context_tokens"],
                    "has_api_key": True,
                    "capabilities": json.loads(row["capabilities_json"]),
                }
            return {"setup_complete": len(configs) == 3, "models": configs}

    def configured(self, role: str) -> tuple[ModelInput, str]:
        config, key, _ = self.configured_with_capabilities(role)
        return config, key

    def configured_with_capabilities(self, role: str):
        with self.db.connect() as conn:
            row = conn.execute("SELECT * FROM model_configs WHERE role=?", (role,)).fetchone()
        if not row:
            raise AppError("MODEL_NOT_CONFIGURED", f"Configure the {role} model in Settings.", 409)
        return (
            ModelInput(
                base_url=row["base_url"],
                model_id=row["model_id"],
                max_context_tokens=row["max_context_tokens"],
            ),
            self.secrets.get(row["api_key_secret_ref"]),
            json.loads(row["capabilities_json"]),
        )

    def input_key(self, role: str, config: ModelInput) -> str:
        if config.api_key_source:
            return self.configured(config.api_key_source)[1]
        if config.use_saved_key:
            return self.configured(role)[1]
        env = f"OPENNOTELM_{role.upper()}_API_KEY"
        return config.api_key.get_secret_value() or os.getenv(env, "")

    async def test_and_save(self, role: str, config: ModelInput) -> dict:
        key = self.input_key(role, config)
        capabilities = await self.gateway.test(role, config, key)
        env = f"OPENNOTELM_{role.upper()}_API_KEY"
        use_env = (
            not config.use_saved_key
            and not config.api_key_source
            and not config.api_key.get_secret_value()
            and env in os.environ
        )
        ref = f"env:{env}" if use_env else self.secrets.put(key)
        old_ref = None
        try:
            with self.db.connect() as conn:
                conn.execute("BEGIN IMMEDIATE")
                old = conn.execute("SELECT * FROM model_configs WHERE role=?", (role,)).fetchone()
                if old:
                    old_ref = old["api_key_secret_ref"]
                if role == "embedding":
                    previous = (
                        {**dict(old), "capabilities": json.loads(old["capabilities_json"])}
                        if old
                        else None
                    )
                    capabilities["index_signature"] = saved_signature(
                        config, capabilities, previous
                    )
                conn.execute(
                    "INSERT INTO model_configs VALUES (?,?,?,?,?,?,?) "
                    "ON CONFLICT(role) DO UPDATE SET base_url=excluded.base_url, "
                    "model_id=excluded.model_id, api_key_secret_ref=excluded.api_key_secret_ref, "
                    "max_context_tokens=excluded.max_context_tokens, "
                    "capabilities_json=excluded.capabilities_json, updated_at=excluded.updated_at",
                    (
                        role,
                        config.base_url,
                        config.model_id,
                        ref,
                        config.max_context_tokens,
                        json.dumps(capabilities),
                        now(),
                    ),
                )
                if role == "embedding" and self.indexes:
                    self.indexes.enqueue_in_transaction(
                        conn,
                        index_signature(
                            {"model_id": config.model_id, "capabilities": capabilities}
                        ),
                    )
        except Exception:
            self.secrets.delete(ref)
            raise
        if old_ref and old_ref != ref:
            self.secrets.delete(old_ref)
        return {"role": role, "capabilities": capabilities, **self.public_configs()}

    async def test_vision(self):
        with self.db.connect() as conn:
            row = conn.execute("SELECT * FROM model_configs WHERE role='language'").fetchone()
        if not row:
            raise AppError("MODEL_NOT_CONFIGURED", "Configure the language model in Settings.", 409)
        config = ModelInput(
            base_url=row["base_url"],
            model_id=row["model_id"],
            max_context_tokens=row["max_context_tokens"],
        )
        key = self.secrets.get(row["api_key_secret_ref"])
        await self.gateway.vision_probe(config, key)
        capabilities = json.loads(row["capabilities_json"]) | {"vision_input": True}
        with self.db.connect() as conn:
            changed = conn.execute(
                "UPDATE model_configs SET capabilities_json=? "
                "WHERE role='language' AND updated_at=?",
                (json.dumps(capabilities), row["updated_at"]),
            ).rowcount
        if not changed:
            raise AppError(
                "MODEL_CONFIG_CHANGED", "The language model changed during the test. Retry.", 409
            )
        return self.public_configs()

    async def discover(self, role: str, config: ModelInput) -> dict:
        try:
            result = await self.gateway.request(config, self.input_key(role, config), "models")
            model_ids = sorted({str(item["id"]) for item in result["data"]})
            return {"models": model_ids, "custom_model_allowed": True}
        except (AppError, KeyError, TypeError, ValueError):
            return {
                "models": [],
                "custom_model_allowed": True,
                "message": "Model discovery is unavailable. Enter a custom model ID.",
            }
