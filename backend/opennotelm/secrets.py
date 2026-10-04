import os
import re
from pathlib import Path
from uuid import uuid4

from cryptography.fernet import Fernet, InvalidToken

from .errors import AppError


class SecretStore:
    def __init__(self, directory: Path):
        self.directory = directory
        key_path = directory / "master.key"
        if not key_path.exists():
            try:
                fd = os.open(key_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
                with os.fdopen(fd, "wb") as file:
                    file.write(Fernet.generate_key())
            except FileExistsError:
                pass
        self.fernet = Fernet(key_path.read_bytes())

    def put(self, value: str) -> str:
        ref = uuid4().hex
        with os.fdopen(
            os.open(self.directory / ref, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), "wb"
        ) as file:
            file.write(self.fernet.encrypt(value.encode()))
        return ref

    def get(self, ref: str) -> str:
        if ref.startswith("env:"):
            value = os.getenv(ref[4:])
            if value is None:
                raise AppError(
                    "SECRET_UNAVAILABLE", "The configured environment key is unavailable."
                )
            return value
        if not re.fullmatch(r"[a-f0-9]{32}", ref):
            raise AppError("SECRET_UNAVAILABLE", "The saved API key is unavailable.")
        try:
            return self.fernet.decrypt((self.directory / ref).read_bytes()).decode()
        except (OSError, InvalidToken) as exc:
            raise AppError("SECRET_UNAVAILABLE", "The saved API key is unavailable.") from exc

    def delete(self, ref: str) -> None:
        if re.fullmatch(r"[a-f0-9]{32}", ref):
            (self.directory / ref).unlink(missing_ok=True)
