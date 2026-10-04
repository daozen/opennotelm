"""Reuse validated visual readings for identical source/model/interpretation inputs."""

import hashlib
import json
from uuid import uuid4

from .citations import CITATION_PATTERN


class VisualReadingCache:
    def __init__(self, directory, identities, payload):
        self.to_stable = {identity: f"CACHE_{i}" for i, identity in enumerate(identities)}
        self.to_actual = {value: key for key, value in self.to_stable.items()}

        def canonical(value):
            if isinstance(value, str):
                if value in self.to_stable:
                    return self.to_stable[value]
                return self.remap(value, self.to_stable)
            if isinstance(value, list):
                return [canonical(v) for v in value]
            if isinstance(value, dict):
                return {k: canonical(v) for k, v in value.items()}
            return value

        digest = hashlib.sha256(
            json.dumps(canonical(payload), ensure_ascii=False, sort_keys=True).encode()
        ).hexdigest()
        self.path = directory / (digest + ".json")
        self.tokens = None

    @staticmethod
    def remap(text, mapping):
        return CITATION_PATTERN.sub(lambda m: "[[" + mapping.get(m[1], m[1]) + "]]", text)

    def get(self):
        try:
            value = json.loads(self.path.read_text())
            if value.get("version") == 1 and isinstance(value.get("content"), str):
                tokens = value.get("tokens")
                self.tokens = tokens if type(tokens) is int and 0 < tokens <= 2_000_000 else None
                return self.remap(value["content"], self.to_actual)
        except (OSError, ValueError, AttributeError):
            pass
        return None

    def save(self, content, tokens=None):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix("." + uuid4().hex + ".tmp")
        try:
            temporary.write_text(
                json.dumps(
                    {
                        "version": 1,
                        "content": self.remap(content, self.to_stable),
                        "tokens": tokens,
                    },
                    ensure_ascii=False,
                )
            )
            temporary.replace(self.path)
        finally:
            temporary.unlink(missing_ok=True)
