"""Persist image worker limits independently of model credentials and preferences."""

from .config import MAX_IMAGE_GENERATION_CONCURRENCY
from .schemas import ImageGenerationSettingsInput


class ImageGenerationSettingsService:
    def __init__(self, db, settings):
        self.db, self.settings = db, settings

    def get(self):
        with self.db.connect() as conn:
            row = conn.execute(
                "SELECT value_json FROM app_settings WHERE key='image_generation'"
            ).fetchone()
        value = (
            ImageGenerationSettingsInput.model_validate_json(row[0]).concurrency
            if row
            else self.settings.image_generation_concurrency
        )
        return {
            "concurrency": value,
            "min_concurrency": 1,
            "max_concurrency": MAX_IMAGE_GENERATION_CONCURRENCY,
        }

    def save(self, data):
        with self.db.connect() as conn:
            conn.execute(
                "INSERT INTO app_settings(key,value_json) VALUES ('image_generation',?) "
                "ON CONFLICT(key) DO UPDATE SET value_json=excluded.value_json",
                (data.model_dump_json(),),
            )
        return self.get()
