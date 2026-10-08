"""Resource-bounded decoding and atomic audio assembly, with joined subprocess cancellation."""

import asyncio
import hashlib
import os
import shutil
import tempfile
import wave
from pathlib import Path
from uuid import uuid4

from .concurrency import joined_thread
from .errors import AppError


def available():
    if not shutil.which("ffmpeg"):
        raise AppError(
            "AUDIO_RUNTIME_UNAVAILABLE", "Install FFmpeg to generate and export podcasts.", 409
        )


async def ffmpeg(*arguments):
    available()
    process = await asyncio.create_subprocess_exec(
        shutil.which("ffmpeg"),
        "-hide_banner",
        "-loglevel",
        "error",
        "-nostdin",
        "-y",
        *map(str, arguments),
        stdin=asyncio.subprocess.DEVNULL,
        stdout=asyncio.subprocess.DEVNULL,
        stderr=asyncio.subprocess.DEVNULL,
    )
    try:
        async with asyncio.timeout(300):
            code = await process.wait()
    except BaseException:
        if process.returncode is None:
            process.kill()
            await process.wait()
        raise
    if code:
        raise AppError(
            "AUDIO_PROCESSING_FAILED",
            "The audio could not be decoded or assembled. Saved chunks are preserved.",
            502,
        )


def duration(path):
    try:
        with wave.open(str(path)) as stream:
            value = stream.getnframes() / stream.getframerate()
        if not 0 < value <= 180:
            raise ValueError
        return value
    except (ValueError, OSError, EOFError, wave.Error) as exc:
        raise AppError(
            "SPEECH_OUTPUT_INVALID",
            "The service returned an invalid or oversized audio chunk.",
            502,
        ) from exc


async def normalize(raw, destination):
    # Never let format probing interpret a provider response as a local/remote playlist.
    if raw[:4] in (b"RIFF", b"RF64") and raw[8:12] == b"WAVE":
        input_format = "wav"
    elif raw.startswith(b"fLaC"):
        input_format = "flac"
    elif raw.startswith(b"OggS"):
        input_format = "ogg"
    elif raw.startswith(b"ID3") or (
        len(raw) >= 2 and raw[0] == 255 and raw[1] & 0xE0 == 0xE0 and raw[1] & 0x06
    ):
        input_format = "mp3"
    else:
        raise AppError(
            "SPEECH_OUTPUT_INVALID", "The service returned an unsupported audio format.", 502
        )
    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    incoming = destination.parent / f".{uuid4().hex}.input"
    output = destination.parent / f".{uuid4().hex}.wav"
    try:
        await joined_thread(incoming.write_bytes, raw)
        await ffmpeg(
            "-protocol_whitelist",
            "file,pipe",
            "-f",
            input_format,
            "-i",
            incoming,
            "-vn",
            "-ac",
            "1",
            "-ar",
            "24000",
            "-c:a",
            "pcm_s16le",
            "-threads",
            "1",
            "-fs",
            "10000000",
            output,
        )
        seconds = await joined_thread(duration, output)
        os.replace(output, destination)
        return seconds
    finally:
        incoming.unlink(missing_ok=True)
        output.unlink(missing_ok=True)


async def validate_sample(raw):
    with tempfile.TemporaryDirectory(prefix="opennotelm-speech-test-") as directory:
        return await normalize(raw, Path(directory) / "test.wav")


def sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        while part := stream.read(1024 * 1024):
            digest.update(part)
    return digest.hexdigest()


async def assemble(paths, destination):
    """All inputs are normalized owned WAV files; the demuxer opens them sequentially."""
    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    manifest = destination.parent / f".{uuid4().hex}.concat"
    output = destination.parent / f".{uuid4().hex}.mp3"
    try:
        # A one-hour target may vary, but never silently truncate an oversized episode.
        if sum(duration(path) for path in paths) > 7200:
            raise AppError(
                "AUDIO_OUTPUT_TOO_LARGE", "The episode exceeds the two-hour audio limit.", 413
            )
        # Paths are generated internally, never user-supplied names or URLs.
        relative_paths = []
        for path in paths:
            if not Path(path).resolve().is_relative_to(destination.parent.resolve()):
                raise AppError("AUDIO_FILE_INVALID", "An audio chunk path is invalid.")
            relative = Path(path).resolve().relative_to(destination.parent.resolve()).as_posix()
            if "'" in relative or "\n" in relative:
                raise AppError("AUDIO_FILE_INVALID", "An audio chunk path is invalid.")
            relative_paths.append(relative)
        manifest.write_text("".join(f"file '{relative}'\n" for relative in relative_paths))
        await ffmpeg(
            "-protocol_whitelist",
            "file,pipe",
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            manifest,
            "-vn",
            "-c:a",
            "libmp3lame",
            "-b:a",
            "128k",
            "-threads",
            "1",
            "-fs",
            str(256 * 1024 * 1024),
            output,
        )
        if output.stat().st_size >= 256 * 1024 * 1024:
            raise AppError(
                "AUDIO_OUTPUT_TOO_LARGE", "The exported audio exceeds the size limit.", 413
            )
        os.replace(output, destination)
        return await joined_thread(sha256, destination)
    finally:
        manifest.unlink(missing_ok=True)
        output.unlink(missing_ok=True)
