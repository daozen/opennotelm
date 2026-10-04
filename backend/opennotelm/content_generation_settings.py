"""Persist content worker limits independently of model credentials and preferences."""

from .config import MAX_CONTENT_GENERATION_CONCURRENCY
from .schemas import ContentGenerationSettingsInput


class ContentGenerationSettingsService:
    def __init__(self, db, settings):
        self.db, self.settings = db, settings

    def get(self):
        with self.db.connect() as conn:
            row = conn.execute(
                "SELECT value_json FROM app_settings WHERE key='content_generation'"
            ).fetchone()
        value = (
            ContentGenerationSettingsInput.model_validate_json(row[0]).concurrency
            if row
            else self.settings.content_generation_concurrency
        )
        return {
            "concurrency": value,
            "min_concurrency": 1,
            "max_concurrency": MAX_CONTENT_GENERATION_CONCURRENCY,
        }

    def save(self, data):
        with self.db.connect() as conn:
            conn.execute(
                "INSERT INTO app_settings(key,value_json) VALUES ('content_generation',?) "
                "ON CONFLICT(key) DO UPDATE SET value_json=excluded.value_json",
                (data.model_dump_json(),),
            )
        return self.get()
