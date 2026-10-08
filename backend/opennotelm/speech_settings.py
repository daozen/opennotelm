"""Speech worker budget, independent from model secrets and other stages."""

from .schemas import SpeechGenerationSettingsInput


class SpeechSettings:
    def __init__(self, db, settings):
        self.db, self.settings = db, settings

    def get(self):
        with self.db.connect() as conn:
            row = conn.execute(
                "SELECT value_json FROM app_settings WHERE key='speech_generation'"
            ).fetchone()
        value = (
            SpeechGenerationSettingsInput.model_validate_json(row[0]).concurrency
            if row
            else self.settings.speech_generation_concurrency
        )
        return {"concurrency": value, "min_concurrency": 1, "max_concurrency": 20}

    def save(self, data):
        with self.db.connect() as conn:
            conn.execute(
                (
                    "INSERT INTO app_settings VALUES ('speech_generation',?) ON CONFLICT(key) "
                    "DO UPDATE SET value_json=excluded.value_json"
                ),
                (data.model_dump_json(),),
            )
        return self.get()
