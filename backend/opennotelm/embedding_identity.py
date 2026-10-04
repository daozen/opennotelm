"""Index identity, with compatibility for previously saved embedding signatures."""

import hashlib
import json

from .chunking import CHUNKER_VERSION


def legacy_signature(model_id, dimensions):
    return hashlib.sha256(json.dumps([model_id, dimensions, CHUNKER_VERSION]).encode()).hexdigest()


def index_signature(config):
    capabilities = config["capabilities"]
    identity = capabilities.get("index_signature")
    if not identity or identity == "legacy":
        return legacy_signature(config["model_id"], capabilities["dimensions"])
    return hashlib.sha256(json.dumps([identity, CHUNKER_VERSION]).encode()).hexdigest()


def saved_signature(config, capabilities, previous):
    if previous and (
        previous["base_url"] == config.base_url
        and previous["model_id"] == config.model_id
        and previous["capabilities"]["dimensions"] == capabilities["dimensions"]
    ):
        return previous["capabilities"].get("index_signature") or "legacy"
    return hashlib.sha256(
        json.dumps(
            ["embedding-v2", config.base_url, config.model_id, capabilities["dimensions"]]
        ).encode()
    ).hexdigest()
