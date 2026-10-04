"""Lossless PDF raster encoding: keep every sample, omit ASCII85 and use PNG prediction."""

import zlib
from io import BytesIO

from PIL import Image
from pypdf import PdfReader, PdfWriter
from pypdf.generic import DictionaryObject, NameObject, NumberObject
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen.canvas import Canvas

ENCODING_VERSION = "lossless-predictor-v1"


def png_image_data(image):
    """Extract IDAT from our own non-interlaced PNG, not from untrusted provider bytes."""
    output = BytesIO()
    image.save(output, format="PNG", compress_level=9)
    png, offset, chunks = output.getvalue(), 8, []
    while offset < len(png):
        length = int.from_bytes(png[offset : offset + 4])
        if png[offset + 4 : offset + 8] == b"IDAT":
            chunks.append(png[offset + 8 : offset + 8 + length])
        offset += length + 12
    return b"".join(chunks)


def compact_raster_streams(page):
    """Only process our Canvas' bounded 8-bit RGB/gray images; keep other objects intact."""
    objects = page["/Resources"].get("/XObject", {})
    for reference in objects.values():
        stream = reference.get_object()
        mode = {"/DeviceRGB": "RGB", "/DeviceGray": "L"}.get(stream.get("/ColorSpace"))
        width, height = stream.get("/Width"), stream.get("/Height")
        if (
            stream.get("/Subtype") != "/Image"
            or not mode
            or stream.get("/BitsPerComponent") != 8
            or not isinstance(width, int)
            or not isinstance(height, int)
            or width <= 0
            or height <= 0
            or width * height > 20_000_000
        ):
            continue
        samples = stream.get_data()
        image = Image.frombytes(mode, (width, height), samples)
        plain, predicted = zlib.compress(samples, 9), png_image_data(image)
        parameters = DictionaryObject(
            {
                NameObject("/Predictor"): NumberObject(15),
                NameObject("/Columns"): NumberObject(width),
                NameObject("/Colors"): NumberObject(3 if mode == "RGB" else 1),
                NameObject("/BitsPerComponent"): NumberObject(8),
            }
        )
        # Prediction has a small dictionary cost. Never enlarge a stream for noise-like images.
        use_prediction = len(predicted) + 120 < len(plain)
        encoded = predicted if use_prediction else plain
        if len(encoded) + (120 if use_prediction else 0) >= len(stream._data):
            stream.decoded_self = None
            continue
        # pypdf set_data recompresses unfiltered samples; these bytes already carry their filter.
        stream._data = encoded
        stream.decoded_self = None
        stream[NameObject("/Filter")] = NameObject("/FlateDecode")
        stream.pop("/DecodeParms", None)
        if use_prediction:
            stream[NameObject("/DecodeParms")] = parameters


def raster_pdf(image):
    output = BytesIO()
    canvas = Canvas(output, pagesize=(1440, 810), pageCompression=1, invariant=1)
    canvas.drawImage(ImageReader(image), 0, 0, width=1440, height=810)
    canvas.showPage()
    canvas.save()
    reader = PdfReader(output)
    compact_raster_streams(reader.pages[0])
    return reader


def write_raster_pdf(raw, target):
    writer = PdfWriter()
    writer.add_page(raster_pdf(BytesIO(raw)).pages[0])
    writer.add_metadata({"/Creator": "OpenNoteLM", "/Producer": ENCODING_VERSION})
    writer.write(target)
