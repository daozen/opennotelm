import shutil
from pathlib import Path
from zipfile import ZipFile

import pytest
from docx_factory import make_docx
from opennotelm.db import Database
from opennotelm.docx_parser import DocxParser
from opennotelm.errors import AppError
from restart_support import restart
from test_sources import wait_for_job


def test_word_structure_tables_stable_ids_and_ingestion(client, settings, provider):
    path = settings.data_dir / "test.docx"
    path.write_bytes(make_docx())
    document = DocxParser().parse(path, "source", "Word")
    assert document == DocxParser().parse(path, "source", "Word")
    assert [n.title for n in document.nodes[1:]] == ["第一章 时间", "第二章 练习"]
    assert document.blocks[-1].type == "table"
    assert document.blocks[-1].text == "频率\t每天一次"
    notebook = client.post("/api/notebooks", json={"title": "Word"}).json()["id"]
    uploaded = client.post(
        f"/api/notebooks/{notebook}/sources/upload",
        files={"file": ("阅读.docx", path.read_bytes())},
    ).json()
    assert wait_for_job(client, uploaded["job"]["id"])["status"] == "completed"
    source = uploaded["source"]["id"]
    assert client.get(f"/api/sources/{source}").json()["type"] == "docx"
    blocks = client.get(f"/api/sources/{source}/blocks").json()
    assert len(blocks) == 5
    with restart(client, settings, provider[0]) as restarted:
        assert restarted.get(f"/api/sources/{source}/blocks").json() == blocks


@pytest.mark.parametrize("unsafe", ["../outside.xml", "/outside.xml", "word/../document.xml"])
def test_unsafe_word_archive_rejected(tmp_path, unsafe):
    path = tmp_path / "unsafe.docx"
    with ZipFile(path, "w") as archive:
        archive.writestr(unsafe, "private")
    with pytest.raises(AppError) as error:
        DocxParser().parse(path, "source", "Unsafe")
    assert error.value.code == "DOCX_UNSAFE_ARCHIVE"


def test_invalid_word_does_not_leak_content(tmp_path):
    path = tmp_path / "bad.docx"
    path.write_bytes(b"PRIVATE_NOT_WORD")
    with pytest.raises(AppError) as error:
        DocxParser().parse(path, "source", "Invalid")
    assert error.value.code == "DOCX_PARSE_FAILED"
    assert "PRIVATE_NOT_WORD" not in str(error.value)


def test_word_migration_preserves_sources_references_and_delete_trigger(tmp_path):
    migrations = Path(__file__).parents[1] / "opennotelm/migrations"
    legacy = tmp_path / "legacy"
    legacy.mkdir()
    for path in sorted(migrations.glob("*.sql")):
        if path.stem < "014":
            shutil.copy(path, legacy)
    db = Database(tmp_path / "upgrade.db")
    db.migrate(legacy)
    with db.connect() as conn:
        conn.execute("INSERT INTO notebooks VALUES ('n','Notebook','','now','now')")
        conn.execute(
            "INSERT INTO sources VALUES ('s','epub','Title','book.epub','application/epub+zip',"
            "'sources/s/original.epub',123,'checksum','epub-v1','parsed',NULL,NULL,'now','now','{}')"
        )
        conn.execute("INSERT INTO notebook_sources VALUES ('n','s',0,1,'now')")
        conn.execute(
            "INSERT INTO source_nodes VALUES ('node','s',NULL,'document','Title',"
            "0,0,NULL,NULL,'{}')"
        )
        conn.execute(
            "INSERT INTO content_blocks VALUES ('block','s','node','paragraph',"
            "0,'Original text',NULL,NULL,'{}','{}')"
        )
        tables = ["sources", "notebook_sources", "source_nodes", "content_blocks", "garbage_files"]
        before = {
            table: [tuple(r) for r in conn.execute(f"SELECT * FROM {table}")] for table in tables
        }
    db.migrate()
    with db.connect() as conn:
        assert {
            table: [tuple(r) for r in conn.execute(f"SELECT * FROM {table}")] for table in tables
        } == before
        assert not conn.execute("PRAGMA foreign_key_check").fetchall()
        conn.execute("UPDATE sources SET type='docx' WHERE id='s'")
        conn.execute("DELETE FROM sources WHERE id='s'")
        assert not conn.execute("SELECT * FROM content_blocks").fetchall()
        assert conn.execute("SELECT * FROM garbage_files").fetchone()[0] == "sources/s"


def test_failed_rebuild_migration_rolls_back_all_changes(tmp_path):
    migrations = Path(__file__).parents[1] / "opennotelm/migrations"
    folder = tmp_path / "migrations"
    shutil.copytree(migrations, folder)
    db = Database(tmp_path / "rollback.db")
    db.migrate(folder)
    with db.connect() as conn:
        conn.execute("INSERT INTO notebooks VALUES ('n','Original','','now','now')")
    (folder / "015_failed.sql").write_text(
        "-- requires-foreign-keys-off\n"
        "UPDATE notebooks SET title='Unexpected';\n"
        "INSERT INTO notebook_sources VALUES ('n','missing',0,1,'now');\n"
    )
    with pytest.raises(AppError) as error:
        db.migrate(folder)
    assert error.value.code == "DATABASE_MIGRATION_FAILED"
    with db.connect() as conn:
        assert conn.execute("SELECT title FROM notebooks").fetchone()[0] == "Original"
        assert not conn.execute("SELECT * FROM notebook_sources").fetchall()
        assert not conn.execute(
            "SELECT 1 FROM schema_migrations WHERE version='015_failed'"
        ).fetchone()
        assert conn.execute("PRAGMA foreign_keys").fetchone()[0] == 1


@pytest.mark.parametrize("cycle", [False, True])
def test_inherited_word_styles_and_cycles_parse_without_xml_construction(tmp_path, cycle):
    from io import BytesIO

    from docx_factory import W

    original = ZipFile(BytesIO(make_docx()))
    path = tmp_path / "inherited.docx"
    with ZipFile(path, "w") as archive:
        for info in original.infolist():
            value = original.read(info.filename)
            if info.filename == "word/styles.xml":
                parent = '<w:basedOn w:val="CustomHeading"/>' if cycle else ""
                value = (
                    f'<w:styles xmlns:w="{W}">'
                    '<w:style w:styleId="Heading1"><w:pPr>'
                    '<w:outlineLvl w:val="0"/></w:pPr></w:style>'
                    '<w:style w:styleId="CustomHeading"><w:basedOn w:val="Heading1"/></w:style>'
                    f'<w:style w:styleId="Normal">{parent}</w:style>'
                    '<w:style w:styleId="Body"><w:basedOn w:val="Normal"/></w:style>'
                    "</w:styles>"
                ).encode()
            elif info.filename == "word/document.xml":
                value = value.replace(b'w:val="Heading1"', b'w:val="CustomHeading"')
                value = value.replace(
                    b"<w:p><w:r>", b'<w:p><w:pPr><w:pStyle w:val="Body"/></w:pPr><w:r>'
                )
            archive.writestr(info.filename, value)
    document = DocxParser().parse(path, "source", "Word")
    assert document == DocxParser().parse(path, "source", "Word")
    assert len(document.blocks) == 5
    assert len([n for n in document.nodes if n.type == "heading"]) == (4 if cycle else 2)
    assert any("每日复盘" in b.text for b in document.blocks)


def test_cyclic_styles_terminate_without_losing_text(tmp_path):
    from docx_factory import W

    path = tmp_path / "cycle.docx"
    with ZipFile(path, "w") as archive:
        archive.writestr(
            "word/document.xml",
            f'<w:document xmlns:w="{W}"><w:body><w:p>'
            '<w:pPr><w:pStyle w:val="A"/></w:pPr>'
            "<w:r><w:t>Safe text</w:t></w:r></w:p></w:body></w:document>",
        )
        archive.writestr(
            "word/styles.xml",
            f'<w:styles xmlns:w="{W}">'
            '<w:style w:styleId="A"><w:basedOn w:val="B"/></w:style>'
            '<w:style w:styleId="B"><w:basedOn w:val="A"/></w:style></w:styles>',
        )
    document = DocxParser().parse(path, "source", "Word")
    assert document.blocks[0].text == "Safe text"
    assert len(document.nodes) == 1
