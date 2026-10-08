import json


def seed(client, kind, instruction, date, notebook="history"):
    db = client.app.state.db
    with db.connect() as conn:
        conn.execute(
            "INSERT OR IGNORE INTO notebooks(id,title,created_at,updated_at) VALUES(?,?,?,?)",
            (notebook, notebook, date, date),
        )
        identity = f"{kind}-{notebook}-{date}"
        if kind == "deck":
            conn.execute(
                "INSERT INTO decks(id,notebook_id,title,source_scope_json,target_slide_count,"
                "language,instruction,created_at,updated_at) VALUES(?,?,?,'{}',10,'en',?,?,?)",
                (identity, notebook, "History", instruction, date, date),
            )
        else:
            conn.execute(
                "INSERT INTO podcasts(id,notebook_id,title,input_json,source_scope_json,"
                "source_manifest_json,settings_json,created_at,updated_at) "
                "VALUES(?,?,?,?,'{}','{}','{}',?,?)",
                (
                    identity,
                    notebook,
                    "History",
                    json.dumps({"instruction": instruction}),
                    date,
                    date,
                ),
            )
    return identity


def history(client, kind):
    response = client.get("/api/artifacts/instruction-history", params={"kind": kind})
    assert response.status_code == 200
    return [item["instruction"] for item in response.json()["items"]]


def test_saved_instructions_are_recent_unique_cross_notebook_and_kind_specific(client):
    assert history(client, "deck") == history(client, "podcast") == []
    seed(client, "deck", "Explain simply\nKeep the examples", "01")
    seed(client, "deck", "Compare approaches", "02")
    seed(client, "deck", "  Explain simply\nKeep the examples  ", "03", "other")
    seed(client, "deck", "\n\t \u3000", "04")
    seed(client, "podcast", "Discuss as two hosts", "05")
    assert history(client, "deck") == ["Explain simply\nKeep the examples", "Compare approaches"]
    assert history(client, "podcast") == ["Discuss as two hosts"]


def test_history_is_bounded_and_empty_or_invalid_input_is_not_offered(client):
    for index in range(25):
        seed(client, "podcast", f"Request {index}", f"{index:02}")
    seed(client, "podcast", None, "26")
    seed(client, "podcast", {"not": "text"}, "27")
    seed(client, "podcast", "x" * 4001, "28")
    assert history(client, "podcast") == [f"Request {index}" for index in range(24, 4, -1)]
    assert client.get("/api/artifacts/instruction-history?kind=anything").status_code == 422


def test_deletion_does_not_leave_a_separate_copy_of_user_instructions(client):
    first = seed(client, "deck", "Keep diagrams", "01")
    second = seed(client, "deck", "Keep diagrams", "02", "other")
    assert history(client, "deck") == ["Keep diagrams"]
    with client.app.state.db.connect() as conn:
        conn.execute("DELETE FROM decks WHERE id=?", (second,))
    assert history(client, "deck") == ["Keep diagrams"]
    with client.app.state.db.connect() as conn:
        conn.execute("DELETE FROM decks WHERE id=?", (first,))
    assert history(client, "deck") == []
