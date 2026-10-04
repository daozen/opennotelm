from contextlib import contextmanager

from fastapi.testclient import TestClient
from opennotelm.main import create_app


@contextmanager
def restart(client, settings, transport):
    """Actually stop the owner before opening the same data directory again."""
    client.__exit__(None, None, None)
    try:
        with TestClient(create_app(settings, transport=transport)) as restarted:
            yield restarted
    finally:
        client.__enter__()
