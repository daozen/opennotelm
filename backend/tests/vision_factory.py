import base64
import json
from io import BytesIO

from PIL import Image, ImageDraw
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen.canvas import Canvas


def scan_image():
    image = Image.new("RGB", (1200, 600), "white")
    pen = ImageDraw.Draw(image)
    pen.text((40, 40), "SCAN 27", fill="black", font_size=70)
    pen.text((40, 160), "Patient learning compounds over time.", fill="black", font_size=45)
    output = BytesIO()
    image.save(output, format="PNG")
    return output.getvalue()


def scan_pdf():
    output = BytesIO()
    canvas = Canvas(output, invariant=1)
    for number in range(2):
        canvas.bookmarkPage(str(number))
        canvas.addOutlineEntry(f"Chapter {number + 1}", str(number))
        canvas.drawImage(ImageReader(BytesIO(scan_image())), 20, 400, width=550, height=275)
        canvas.showPage()
    canvas.save()
    return output.getvalue()


def vision_completion(payload):
    content = payload["messages"][-1]["content"]
    if not isinstance(content, list):
        return None
    url = next(c["image_url"]["url"] for c in content if c["type"] == "image_url")
    assert url.startswith("data:image/png;base64,")
    with Image.open(BytesIO(base64.b64decode(url.split(",", 1)[1]))) as image:
        assert image.width > 0 and image.height > 0
    if payload["messages"][0]["role"] == "user":
        return "VISION 27"
    return json.dumps(
        {
            "paragraphs": ["SCAN 27", "Patient learning compounds over time."],
            "description": "",
            "uncertain": False,
        }
    )
