from io import BytesIO
from xml.sax.saxutils import escape
from zipfile import ZIP_DEFLATED, ZipFile

W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
R = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
A = "http://schemas.openxmlformats.org/drawingml/2006/main"


def make_docx(image=None):
    paragraphs = "".join(
        '<w:p><w:pPr><w:pStyle w:val="Heading1"/></w:pPr>'
        f"<w:r><w:t>{escape(title)}</w:t></w:r></w:p>"
        f"<w:p><w:r><w:t>{escape(body)}</w:t></w:r></w:p>"
        for title, body in [
            ("第一章 时间", "长期复利最大的优势来自时间跨度。"),
            ("第二章 练习", "每日复盘帮助积累经验。"),
        ]
    )
    drawing = (
        ('<w:p><w:r><w:drawing><a:blip r:embed="rId1"/></w:drawing></w:r></w:p>') if image else ""
    )
    xml = (
        f'<w:document xmlns:w="{W}" xmlns:a="{A}" xmlns:r="{R}">'
        f"<w:body>{paragraphs}<w:tbl><w:tr>"
        "<w:tc><w:p><w:r><w:t>频率</w:t></w:r></w:p></w:tc>"
        "<w:tc><w:p><w:r><w:t>每天一次</w:t></w:r></w:p></w:tc>"
        f"</w:tr></w:tbl>{drawing}</w:body></w:document>"
    )
    result = BytesIO()
    with ZipFile(result, "w", ZIP_DEFLATED) as archive:
        archive.writestr(
            "[Content_Types].xml",
            '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
            '<Default Extension="xml" ContentType="application/xml"/></Types>',
        )
        archive.writestr("word/document.xml", xml)
        archive.writestr(
            "word/styles.xml",
            f'<w:styles xmlns:w="{W}">'
            '<w:style w:styleId="Heading1"><w:pPr><w:outlineLvl w:val="0"/>'
            "</w:pPr></w:style></w:styles>",
        )
        if image:
            archive.writestr("word/media/image1.png", image)
            archive.writestr(
                "word/_rels/document.xml.rels",
                '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
                f'<Relationship Id="rId1" Type="{R}/image" '
                'Target="media/image1.png"/></Relationships>',
            )
    return result.getvalue()
