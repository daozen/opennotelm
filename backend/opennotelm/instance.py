"""One application process owns a data directory, including recovery and migrations."""

import fcntl
import os
from contextlib import contextmanager

from .errors import AppError


@contextmanager
def instance_lock(directory):
    directory.mkdir(parents=True, exist_ok=True)
    # Keep the inode after unlock: unlinking a lock file creates a split-lock race.
    descriptor = os.open(directory / "instance.lock", os.O_CREAT | os.O_RDWR, 0o600)
    try:
        try:
            fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise AppError(
                "INSTANCE_ALREADY_RUNNING",
                "Another OpenNoteLM process is using this data directory. Stop it first; "
                "run the app with one server worker.",
                409,
            ) from None
        yield
    finally:
        os.close(descriptor)
