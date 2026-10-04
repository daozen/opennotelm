"""Shared admission budgets; saved settings never interrupt active work."""

from .schemas import ModelRequestConcurrencyInput, TaskConcurrencyInput


class AdmissionSettings:
    def __init__(self, db, settings, *, requests=False):
        self.db = db
        self.key = "model_request_concurrency" if requests else "task_concurrency"
        self.schema = ModelRequestConcurrencyInput if requests else TaskConcurrencyInput
        self.default = getattr(settings, self.key)
        self.maximum = 20 if requests else 8

    def get(self):
        with self.db.connect() as conn:
            row = conn.execute(
                "SELECT value_json FROM app_settings WHERE key=?", (self.key,)
            ).fetchone()
        return {
            "concurrency": self.schema.model_validate_json(row[0]).concurrency
            if row
            else self.default,
            "min_concurrency": 1,
            "max_concurrency": self.maximum,
        }

    def save(self, data):
        with self.db.connect() as conn:
            conn.execute(
                "INSERT INTO app_settings(key,value_json) VALUES (?,?) "
                "ON CONFLICT(key) DO UPDATE SET value_json=excluded.value_json",
                (self.key, data.model_dump_json()),
            )
        return self.get()
