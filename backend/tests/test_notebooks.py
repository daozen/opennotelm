from restart_support import restart


def test_notebook_crud_and_restart(client, settings, provider):
    response = client.post("/api/notebooks", json={"title": "  阅读计划  ", "description": "EPUB"})
    assert response.status_code == 201
    notebook = response.json()
    assert notebook["title"] == "阅读计划"
    notebook_id = notebook["id"]
    assert client.get("/api/notebooks").json()[0]["source_count"] == 0
    assert (
        client.patch(f"/api/notebooks/{notebook_id}", json={"title": "新名称"}).status_code == 200
    )
    with restart(client, settings, transport=provider[0]) as restarted:
        assert restarted.get(f"/api/notebooks/{notebook_id}").json()["title"] == "新名称"
        assert restarted.delete(f"/api/notebooks/{notebook_id}").status_code == 204
    assert client.get(f"/api/notebooks/{notebook_id}").status_code == 404


def test_notebook_validation_and_missing(client):
    for title in ("", "   ", "a" * 201):
        assert client.post("/api/notebooks", json={"title": title}).status_code == 422
    assert client.delete("/api/notebooks/missing").status_code == 404


def test_delete_notebook_only_unlinks_sources(client):
    notebook = client.post("/api/notebooks", json={"title": "Example"}).json()
    with client.app.state.db.connect() as conn:
        conn.execute(
            "INSERT INTO sources (id,type,title,original_filename,mime_type,file_uri,"
            "file_size,checksum_sha256,created_at,updated_at) VALUES "
            "('source','text','Original','test.txt','text/plain','sources/original',1,'hash','now','now')"
        )
        conn.execute(
            "INSERT INTO notebook_sources VALUES (?,'source',0,1,'now')", (notebook["id"],)
        )
    assert client.delete(f"/api/notebooks/{notebook['id']}").status_code == 204
    with client.app.state.db.connect() as conn:
        assert conn.execute("SELECT count(*) FROM sources").fetchone()[0] == 1
        assert conn.execute("SELECT count(*) FROM notebook_sources").fetchone()[0] == 0


def test_cross_origin_and_host_rejected(client):
    response = client.post(
        "/api/notebooks", headers={"Origin": "https://evil.example"}, json={"title": "CSRF"}
    )
    assert response.status_code == 403
    assert client.get("/api/health", headers={"Host": "evil.example"}).status_code == 400
    assert client.get("/api/health").headers["x-content-type-options"] == "nosniff"
