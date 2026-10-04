import pytest
from epub_factory import make_epub
from opennotelm.epub import EpubParser, safe_reference
from opennotelm.errors import AppError


def test_epub_spine_toc_semantics_locations_and_stable_ids(tmp_path):
    path = tmp_path / "book.epub"
    make_epub(path)
    parser = EpubParser()
    document = parser.parse(path, "example-source")
    assert document.title == "长期思考"
    chapters = [n for n in document.nodes if n.type == "chapter"]
    assert [c.title for c in chapters] == ["耐心的价值", "时间的力量"]  # spine, not manifest order
    assert document.metadata["toc"][1]["depth"] == 2
    assert {b.type for b in document.blocks} == {
        "heading",
        "paragraph",
        "list",
        "code",
        "table",
        "quote",
    }
    originals = [b for b in document.blocks if b.location.get("element_id") == "original"]
    assert originals[0].text == "长期复利最大的优势来自时间跨度。"
    assert originals[0].location["href"] == "OEBPS/one.xhtml"
    assert originals[0].location["spine_index"] == 1
    assert sum(b.text == "理解需要耐心。" for b in document.blocks) == 1
    assert "EXFILTRATE_SECRET" not in " ".join(b.text for b in document.blocks)
    assert not any("evil.example" in b.text for b in document.blocks)
    again = parser.parse(path, "example-source")
    assert [b.id for b in document.blocks] == [b.id for b in again.blocks]
    assert all(n.parent_id in {p.id for p in document.nodes} for n in document.nodes if n.parent_id)


def test_ncx_fallback(tmp_path):
    path = tmp_path / "book.epub"
    make_epub(path, ncx=True)
    document = EpubParser().parse(path, "source")
    assert [t["title"] for t in document.metadata["toc"]] == ["时间的力量", "耐心的价值"]


@pytest.mark.parametrize("name", ["../escape", "/absolute", "C:\\escape"])
def test_unsafe_archive_paths_rejected(tmp_path, name):
    path = tmp_path / "book.epub"
    make_epub(path, extra={name: "hostile"})
    with pytest.raises(AppError) as error:
        EpubParser().parse(path, "source")
    assert error.value.code == "EPUB_UNSAFE_PATH"
    assert not (tmp_path.parent / "escape").exists()


def test_zip_bomb_limits(tmp_path):
    path = tmp_path / "book.epub"
    make_epub(path, extra={"large.txt": "x" * 20000})
    with pytest.raises(AppError) as error:
        EpubParser(max_compression_ratio=50).parse(path, "source")
    assert error.value.code == "EPUB_ZIP_LIMIT"
    with pytest.raises(AppError):
        EpubParser(max_entries=2).parse(path, "source")


def test_xml_entity_expansion_rejected(tmp_path):
    path = tmp_path / "book.epub"
    make_epub(path, extra={"evil.xml": ""})
    # A standalone hostile container archive must fail before any entity is resolved.
    from zipfile import ZipFile

    with ZipFile(path, "w") as archive:
        archive.writestr(
            "META-INF/container.xml",
            """<!DOCTYPE container [<!ENTITY secret SYSTEM "file:///etc/passwd">]>
<container>&secret;</container>""",
        )
    with pytest.raises(AppError) as error:
        EpubParser().parse(path, "source")
    assert error.value.code == "EPUB_PARSE_FAILED"


@pytest.mark.parametrize(
    "href", ["../../escape", "https://evil.example/book", "/etc/passwd", "..\\bad"]
)
def test_unsafe_references(href):
    with pytest.raises(AppError):
        safe_reference("OEBPS/book.opf", href)


def test_corrupt_epub_reports_safe_error(tmp_path):
    path = tmp_path / "bad.epub"
    path.write_bytes(b"not a zip")
    with pytest.raises(AppError) as error:
        EpubParser().parse(path, "source")
    assert error.value.code == "EPUB_PARSE_FAILED"
