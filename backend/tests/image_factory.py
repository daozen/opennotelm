"""Small real raster fixture for image protocol/rendering tests."""

import base64
from io import BytesIO

from PIL import Image, ImageDraw


def image_bytes(size=None):
    image = Image.new("RGB", (512, 512), "#f3efe6")
    draw = ImageDraw.Draw(image)
    for index, color in enumerate(["#ccd5bf", "#667260", "#9d6b39", "#233d31"]):
        y = 160 + index * 65
        draw.ellipse((40, y - 80, 470, y + 95), fill=color)
    if size:
        width, height = map(int, size.split("x"))
        image = image.resize((width, height))
    result = BytesIO()
    image.save(result, "PNG")
    return result.getvalue()


def image_response(size=None):
    return {"data": [{"b64_json": base64.b64encode(image_bytes(size)).decode()}]}
