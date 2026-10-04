from uuid import uuid4

from .db import Database
from .errors import AppError
from .model_service import now
from .schemas import NotebookInput


class NotebookService:
    def __init__(self, db: Database):
        self.db = db

    def list(self) -> list[dict]:
        with self.db.connect() as conn:
            return [
                dict(row)
                for row in conn.execute(
                    "SELECT n.*, (SELECT count(*) FROM notebook_sources ns "
                    "WHERE ns.notebook_id=n.id) "
                    "AS source_count, (SELECT count(*) FROM knowledge_pages k "
                    "WHERE k.notebook_id=n.id) AS knowledge_count, (SELECT count(*) FROM decks d "
                    "WHERE d.notebook_id=n.id) AS deck_count "
                    "FROM notebooks n ORDER BY updated_at DESC, id"
                )
            ]

    def get(self, notebook_id: str) -> dict:
        with self.db.connect() as conn:
            row = conn.execute("SELECT * FROM notebooks WHERE id=?", (notebook_id,)).fetchone()
        if not row:
            raise AppError("NOTEBOOK_NOT_FOUND", "This notebook no longer exists.", 404)
        return dict(row)

    def create(self, data: NotebookInput) -> dict:
        notebook_id, timestamp = uuid4().hex, now()
        with self.db.connect() as conn:
            conn.execute(
                "INSERT INTO notebooks VALUES (?,?,?,?,?)",
                (notebook_id, data.title, data.description, timestamp, timestamp),
            )
        return self.get(notebook_id)

    def update(self, notebook_id: str, data: NotebookInput) -> dict:
        self.get(notebook_id)
        with self.db.connect() as conn:
            conn.execute(
                "UPDATE notebooks SET title=?, description=?, updated_at=? WHERE id=?",
                (data.title, data.description, now(), notebook_id),
            )
        return self.get(notebook_id)

    def delete(self, notebook_id: str) -> None:
        self.get(notebook_id)
        with self.db.connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            if conn.execute(
                "SELECT 1 FROM jobs WHERE notebook_id=? AND status IN ('queued','running')",
                (notebook_id,),
            ).fetchone():
                raise AppError(
                    "NOTEBOOK_BUSY",
                    "Wait for this notebook's tasks to finish before deleting it.",
                    409,
                )
            conn.execute("DELETE FROM notebooks WHERE id=?", (notebook_id,))
