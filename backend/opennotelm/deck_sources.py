"""Frozen input names and chapter locations; never a replacement for citation facts."""

import copy
import json

from .errors import AppError


def directory(source, nodes):
    entries = [dict(node) for node in nodes if node["type"] in ("chapter", "heading")]
    toc = json.loads(source["metadata_json"]).get("toc", []) if source else []
    if source and source["type"] == "epub" and toc:
        mapped = []
        for entry in toc:
            node = next(
                (
                    node
                    for node in nodes
                    if node["metadata"].get("href") == entry.get("href")
                    and (
                        node["metadata"].get("element_id") == entry["fragment"]
                        if entry.get("fragment")
                        else node["type"] == "chapter"
                    )
                ),
                None,
            )
            if node and not any(item["id"] == node["id"] for item in mapped):
                mapped.append(
                    {
                        **node,
                        "title": entry.get("title") or node["title"],
                        "depth": entry.get("depth", node["depth"]),
                    }
                )
        if mapped:
            entries = mapped
            parents = []
            for node in entries:
                while parents and parents[-1]["depth"] >= node["depth"]:
                    parents.pop()
                node["parent_id"] = parents[-1]["id"] if parents else None
                parents.append(node)
    by_id = {node["id"]: node for node in nodes}
    by_id.update({node["id"]: node for node in entries})
    numbers, siblings = {}, {}
    for node in entries:
        parent, seen = by_id.get(node["parent_id"]), {node["id"]}
        while parent and parent["id"] not in seen and parent["id"] not in numbers:
            seen.add(parent["id"])
            parent = by_id.get(parent["parent_id"])
        parent_id = parent["id"] if parent and parent["id"] in numbers else None
        siblings[parent_id] = siblings.get(parent_id, 0) + 1
        number = str(siblings[parent_id])
        node["number"] = f"{numbers[parent_id]}.{number}" if parent_id else number
        numbers[node["id"]] = node["number"]
        path, current, seen = [], node, set()
        while current and current["id"] not in seen:
            seen.add(current["id"])
            if current["type"] not in ("document", "page"):
                path.append(current["title"])
            current = by_id.get(current["parent_id"])
        node["path"] = list(reversed(path)) or [node["title"]]
    return entries


def capture(conn, scope, snapshot=None, *, historical=False, evidence=(), node_provider=None):
    spans = [span for item in evidence for span in item.get("spans", [])]
    knowledge = []
    if snapshot:
        knowledge = [{key: snapshot[key] for key in ("id", "title", "revision")}]
        if not spans:
            for citation in dict.fromkeys(snapshot["citations"].values()):
                spans.extend(
                    dict(row)
                    for row in conn.execute(
                        "SELECT source_id,block_id FROM citation_spans WHERE citation_id=? "
                        "ORDER BY ordinal",
                        (citation,),
                    )
                )
        source_ids = list(dict.fromkeys(span["source_id"] for span in spans))
    elif scope["kind"] == "selected":
        source_ids = scope.get("source_ids") or []
    else:
        source_ids = [scope["source_id"]]
    sources = []
    for identity in source_ids:
        source = conn.execute("SELECT * FROM sources WHERE id=?", (identity,)).fetchone()
        nodes = [
            {**dict(row), "metadata": json.loads(row["metadata_json"])}
            for row in conn.execute(
                "SELECT * FROM source_nodes WHERE source_id=? ORDER BY ordinal", (identity,)
            )
        ]
        # Legacy EPUB directory anchors can be reading projections rather than
        # persisted fact nodes. Reuse the reader's identities without rewriting them.
        if node_provider and source and source["type"] == "epub":
            nodes = node_provider(identity)
        blocks = list(
            conn.execute(
                "SELECT id,node_id FROM content_blocks WHERE source_id=? ORDER BY ordinal",
                (identity,),
            )
        )
        outline = directory(source, nodes)
        by_id = {node["id"]: node for node in nodes}
        by_id.update({node["id"]: node for node in outline})
        ranks = {block["id"]: index for index, block in enumerate(blocks)}
        first_blocks = {}
        for block in blocks:
            current, seen = by_id.get(block["node_id"]), set()
            while current and current["id"] not in seen:
                seen.add(current["id"])
                first_blocks.setdefault(current["id"], block["id"])
                current = by_id.get(current["parent_id"])
        requested = set(scope.get("node_ids") or [scope.get("node_id")]) - {None}
        if snapshot:
            selected_blocks = {span["block_id"] for span in spans if span["source_id"] == identity}
            selected_nodes = {
                block["node_id"] for block in blocks if block["id"] in selected_blocks
            }
            for identity_node in list(selected_nodes):
                current, seen = by_id.get(identity_node), set()
                while current and current["id"] not in seen:
                    seen.add(current["id"])
                    selected_nodes.add(current["id"])
                    current = by_id.get(current["parent_id"])
            # PDF bookmark sections own page blocks indirectly; don't invent a page TOC.
            requested = selected_nodes | {
                node["id"]
                for node in outline
                if selected_blocks.intersection(node["metadata"].get("section_block_ids", []))
            }
            chapters = [node for node in outline if node["id"] in requested]
            selection = "citations"
        elif requested:
            chapters = [by_id[node["id"]] for node in nodes if node["id"] in requested]
            selection = "chapters"
        else:
            chapters, selection = outline, "whole"

        def anchor(node, first_blocks=first_blocks, ranks=ranks):
            candidates = [
                first_blocks.get(node["id"]),
                *node["metadata"].get("section_block_ids", []),
            ]
            return min(
                (value for value in candidates if value in ranks),
                key=ranks.__getitem__,
                default=None,
            )

        sources.append(
            {
                "id": identity,
                "title": source["title"] if source else None,
                "type": source["type"] if source else None,
                "selection": selection,
                "first_block_id": blocks[0]["id"] if blocks else None,
                "chapters": [
                    {
                        "id": node["id"],
                        "title": node["title"],
                        "number": node.get("number"),
                        "path": node.get("path", [node["title"]]),
                        "first_block_id": anchor(node),
                    }
                    for node in chapters
                ],
            }
        )
    return {"version": 1, "historical": historical, "knowledge": knowledge, "sources": sources}


def source_title(manifest):
    sources = manifest["sources"]
    if manifest["knowledge"] or len(sources) != 1:
        raise AppError("SCOPE_INVALID", "Source naming needs one source or chapter.")
    source = sources[0]
    if source["selection"] == "whole":
        return source["title"]
    if source["selection"] == "chapters" and len(source["chapters"]) == 1:
        chapter = source["chapters"][0]
        return "-".join(
            part for part in (source["title"], chapter.get("number"), chapter["title"]) if part
        )
    raise AppError("SCOPE_INVALID", "Source naming needs one source or chapter.")


def public(conn, deck):
    manifest = copy.deepcopy(deck["source_manifest"])
    if manifest is None:
        manifest = capture(
            conn,
            deck["source_scope"],
            deck["knowledge_snapshot"],
            historical=True,
            evidence=(deck["understanding"] or {}).get("evidence", []),
        )
    backgrounds = {
        reading["source_id"]
        for reading in (deck["understanding"] or {})
        .get("work_context", {})
        .get("whole_work_readings", [])
    }
    for source in manifest["sources"]:
        source["available"] = bool(
            conn.execute(
                "SELECT 1 FROM notebook_sources ns "
                "JOIN content_blocks b ON b.source_id=ns.source_id "
                "WHERE ns.notebook_id=? AND ns.source_id=? LIMIT 1",
                (deck["notebook_id"], source["id"]),
            ).fetchone()
        )
        source["whole_work_background"] = source["id"] in backgrounds
        for chapter in source["chapters"]:
            chapter["available"] = source["available"] and bool(
                conn.execute(
                    "SELECT 1 FROM content_blocks WHERE id=? AND source_id=?",
                    (chapter["first_block_id"], source["id"]),
                ).fetchone()
            )
    for knowledge in manifest["knowledge"]:
        knowledge["available"] = bool(
            conn.execute(
                "SELECT 1 FROM knowledge_pages WHERE id=? AND notebook_id=?",
                (knowledge["id"], deck["notebook_id"]),
            ).fetchone()
        )
    return manifest
