"""Synthetic audio for protocol/browser tests; never used by application code."""

import io
import math
import struct
import wave


def sample_wav():
    output = io.BytesIO()
    with wave.open(output, "wb") as stream:
        stream.setparams((1, 2, 24000, 0, "NONE", "not compressed"))
        stream.writeframes(
            b"".join(struct.pack("<h", int(1500 * math.sin(i / 10))) for i in range(4800))
        )
    return output.getvalue()
