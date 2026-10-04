def test_document_deep_links_serve_application_and_missing_api_stays_json(client, settings):
    settings.frontend_dir.mkdir(parents=True)
    index = '<html><script src="/assets/app.js"></script></html>'
    (settings.frontend_dir / "index.html").write_text(index)
    for path in (
        "/notebooks/book",
        "/notebooks/book/sources/source?node=page&block=original",
        "/notebooks/book/knowledge/note",
        "/notebooks/book/decks/deck?slide=second",
    ):
        response = client.get(path)
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/html")
        assert response.text == index
    missing_api = client.get("/api/unknown-route")
    assert missing_api.status_code == 404
    assert missing_api.headers["content-type"].startswith("application/json")
