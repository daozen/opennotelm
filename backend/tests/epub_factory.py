from io import BytesIO
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo


def make_epub(path: Path | None = None, *, extra: dict[str, str] | None = None, ncx=False) -> bytes:
    stream = BytesIO()
    with ZipFile(stream, "w", compression=ZIP_DEFLATED) as archive:

        def write(name, content):
            entry = ZipInfo(name, date_time=(2026, 1, 1, 0, 0, 0))
            archive.writestr(entry, content, compress_type=ZIP_DEFLATED)

        write("mimetype", "application/epub+zip")
        write(
            "META-INF/container.xml",
            """<?xml version="1.0"?>
<container xmlns="urn:oasis:names:tc:opendocument:xmlns:container">
<rootfiles><rootfile full-path="OEBPS/book.opf" /></rootfiles></container>""",
        )
        write(
            "OEBPS/book.opf",
            f'''<package xmlns="http://www.idpf.org/2007/opf" version="3.0">
<metadata xmlns:dc="http://purl.org/dc/elements/1.1/"><dc:title>长期思考</dc:title></metadata>
<manifest><item id="a" href="one.xhtml" media-type="application/xhtml+xml" />
<item id="b" href="two.xhtml" media-type="application/xhtml+xml" />
<item id="nav" href="nav.xhtml" media-type="application/xhtml+xml"
 properties="{"other" if ncx else "nav"}" />
<item id="ncx" href="toc.ncx" media-type="application/x-dtbncx+xml" /></manifest>
<spine toc="ncx"><itemref idref="b" /><itemref idref="a" /></spine></package>''',
        )
        write(
            "OEBPS/nav.xhtml",
            """<html xmlns:epub="http://www.idpf.org/2007/ops"><body>
<nav epub:type="toc"><ol><li><a href="one.xhtml">时间的力量</a>
<ol><li><a href="one.xhtml#growth">增长</a></li></ol></li>
<li><a href="two.xhtml">耐心的价值</a></li></ol></nav></body></html>""",
        )
        write(
            "OEBPS/toc.ncx",
            """<ncx xmlns="http://www.daisy.org/z3986/2005/ncx/">
<navMap><navPoint><navLabel><text>时间的力量</text></navLabel><content src="one.xhtml" /></navPoint>
<navPoint><navLabel><text>耐心的价值</text></navLabel><content src="two.xhtml" /></navPoint>
</navMap></ncx>""",
        )
        write(
            "OEBPS/one.xhtml",
            """<html><head><style>body{background:url(https://evil.example)}</style></head><body>
<h1>时间的力量</h1><h2 id="growth">增长</h2><p id="original">长期复利最大的优势来自时间跨度。</p>
<blockquote><p>理解需要耐心。</p></blockquote><ul><li>持续学习</li><li>定期回顾</li></ul>
<pre>return growth</pre><table><tr><td>年份</td><td>积累</td></tr></table>
<script>EXFILTRATE_SECRET()</script><iframe src="https://evil.example"></iframe>
<p onclick="alert(1)">安全正文 &lt;img src=x onerror=alert(1)&gt;</p></body></html>""",
        )
        write(
            "OEBPS/two.xhtml",
            """<html><body><h1>耐心的价值</h1>
<p id="patience">耐心意味着允许小的进步经过长期积累。</p>
<h2>实践</h2><p>每周回顾一次自己的理解。</p></body></html>""",
        )
        for name, content in (extra or {}).items():
            write(name, content)
    data = stream.getvalue()
    if path:
        path.write_bytes(data)
    return data


def make_anchor_epub():
    output = BytesIO()
    with ZipFile(BytesIO(make_epub())) as original, ZipFile(output, "w") as archive:
        for item in original.infolist():
            content = original.read(item.filename)
            if item.filename == "OEBPS/nav.xhtml":
                content = b"""<html xmlns:epub="http://www.idpf.org/2007/ops"><body>
<nav epub:type="toc"><ol><li><a href="one.xhtml#alpha">Alpha</a></li>
<li><a href="one.xhtml#beta">Beta</a></li></ol></nav></body></html>"""
            if item.filename == "OEBPS/one.xhtml":
                content = b"""<html><body><div id="alpha"></div>
<p>ALPHA_ONLY: patient learning compounds over time.</p>
<a name="beta"></a><p>BETA_EXCLUDED: this belongs to another chapter.</p>
</body></html>"""
            archive.writestr(item, content)
    return output.getvalue()
