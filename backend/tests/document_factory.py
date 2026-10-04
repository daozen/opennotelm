from io import BytesIO

from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from reportlab.pdfgen.canvas import Canvas


def make_pdf(blank=False):
    stream = BytesIO()
    canvas = Canvas(stream, invariant=1)
    canvas.setTitle("Patient learning")
    for page, title in enumerate(("1. Time", "2. Practice")):
        canvas.bookmarkPage(str(page))
        canvas.addOutlineEntry(title, str(page), level=0)
        if not blank:
            canvas.setFont("Helvetica-Bold", 24)
            canvas.drawString(60, 760, title)
            canvas.setFont("Helvetica", 12)
            canvas.drawString(60, 720, f"Page {page + 1}: Small improvements accumulate over time.")
            canvas.drawString(60, 690, "Careful practice and patience support sustained learning.")
        canvas.showPage()
    canvas.save()
    return stream.getvalue()


def make_glyph_pdf():
    """Browser/PDF exports often draw each glyph in a separate text operation."""
    pdfmetrics.registerFont(UnicodeCIDFont("STSong-Light"))
    stream = BytesIO()
    canvas = Canvas(stream, invariant=1)
    canvas.setTitle("连续阅读测试")
    for number in range(1, 3):
        canvas.setFont("STSong-Light", 25)
        for index, char in enumerate(f"第{number}页连续阅读"):
            canvas.drawString(60 + 25 * index, 750, char)
        canvas.setFont("STSong-Light", 14)
        text = (
            "这是按字绘制的中文资料，阅读时应该恢复完整段落。"
            "保留原始引用，才能准确返回资料中的位置。"
        )
        for index, char in enumerate(text):
            canvas.drawString(60 + (index % 22) * 14, 700 - (index // 22) * 24, char)
        canvas.setFont("Helvetica", 12)
        x = 60
        for word in ["Clear ", "explanations ", "preserve ", "source ", "evidence."]:
            canvas.drawString(x, 600, word)
            x += pdfmetrics.stringWidth(word, "Helvetica", 12)
        canvas.showPage()
    canvas.save()
    return stream.getvalue()


def make_nested_pdf():
    stream = BytesIO()
    canvas = Canvas(stream, invariant=1)
    canvas.setTitle("Chapter hierarchy acceptance")
    for index, (title, depth, body) in enumerate(
        [
            ("Part One", 0, "PARENT_INTRO: thoughtful learning takes time."),
            ("Section Alpha", 1, "ALPHA_ONLY: careful practice supports learning."),
            ("Detail Alpha", 2, "ALPHA_DETAIL: reflection improves understanding."),
            ("Section Beta", 1, "BETA_ONLY: patience helps knowledge accumulate."),
            ("Part Two", 0, "GAMMA_EXCLUDED: this is a different chapter."),
        ]
    ):
        canvas.bookmarkPage(str(index))
        canvas.addOutlineEntry(title, str(index), level=depth)
        canvas.setFont("Helvetica-Bold", 24)
        canvas.drawString(60, 760, title)
        canvas.setFont("Helvetica", 12)
        canvas.drawString(60, 720, body)
        canvas.showPage()
    canvas.save()
    return stream.getvalue()


MARKDOWN = """# Learning

Small **improvements** accumulate over time.

## Practice

> Keep learning.

- Read
- Reflect

```python
  print("<script>literal code</script>")
```

| Method | Frequency |
| --- | --- |
| Reading | Daily |

Safe <script>EXFILTRATE()</script>content.

<iframe src="https://invalid.example/track">TRACKER</iframe>

### Reflection

A final paragraph.
"""
