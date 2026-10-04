"""Provider-neutral image boundary and a bounded Images API compatible implementation."""

import asyncio
import base64
import binascii
import ipaddress
import json
import socket
import warnings
from dataclasses import dataclass
from io import BytesIO
from typing import Protocol

import httpx
from PIL import Image, ImageOps, UnidentifiedImageError

from .errors import AppError

MAX_IMAGE_BYTES = 24 * 1024 * 1024
MAX_IMAGE_PIXELS = 20_000_000
MAX_RESPONSE_BYTES = 34 * 1024 * 1024


@dataclass(frozen=True)
class GeneratedImage:
    data: bytes
    width: int
    height: int
    format: str = "png"


class ImageGenerationAdapter(Protocol):
    async def generate(
        self, config, key: str, prompt: str, *, size: str | None = None
    ) -> GeneratedImage: ...


def validated_image(raw: bytes) -> GeneratedImage:
    if not raw or len(raw) > MAX_IMAGE_BYTES:
        raise AppError("IMAGE_OUTPUT_INVALID", "The image is empty or exceeds 24 MB.", 502)
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(BytesIO(raw)) as image:
                if image.format not in {"PNG", "JPEG", "WEBP"} or getattr(
                    image, "is_animated", False
                ):
                    raise ValueError
                if image.width * image.height > MAX_IMAGE_PIXELS:
                    raise ValueError
                image.verify()
            with Image.open(BytesIO(raw)) as image:
                image.load()
                clean = ImageOps.exif_transpose(image).convert(
                    "RGBA" if "A" in image.getbands() or "transparency" in image.info else "RGB"
                )
                # Re-encode pixels only: no provider metadata, active content or ancillary payloads.
                clean.info.clear()
                output = BytesIO()
                clean.save(output, format="PNG")
                result = output.getvalue()
                if len(result) > MAX_IMAGE_BYTES:
                    raise ValueError
                return GeneratedImage(result, clean.width, clean.height)
    except (
        ValueError,
        OSError,
        UnidentifiedImageError,
        Image.DecompressionBombError,
        Image.DecompressionBombWarning,
    ) as exc:
        raise AppError(
            "IMAGE_OUTPUT_INVALID",
            "The provider did not return a valid, bounded PNG, JPEG or WebP image.",
            502,
        ) from exc


async def bounded_bytes(response, limit):
    response.raise_for_status()
    result = bytearray()
    async for chunk in response.aiter_bytes(65536):
        result.extend(chunk)
        if len(result) > limit:
            raise AppError(
                "IMAGE_OUTPUT_TOO_LARGE", "The image response exceeds the size limit.", 502
            )
    return bytes(result)


def origin(url):
    return url.scheme, url.host, url.port


async def download_target(url, provider_url):
    """Pin public DNS answers; explicitly configured same-origin local providers are supported."""
    if url.scheme not in {"http", "https"} or not url.host or url.userinfo or url.fragment:
        raise AppError("IMAGE_URL_REJECTED", "The provider returned an unsupported image URL.", 502)
    if origin(url) == origin(provider_url):
        return url, {}, {}
    if url.scheme != "https":
        raise AppError("IMAGE_URL_REJECTED", "External image downloads require HTTPS.", 502)
    try:
        addresses = await asyncio.wait_for(
            asyncio.to_thread(socket.getaddrinfo, url.host, url.port or 443, 0, socket.SOCK_STREAM),
            timeout=10,
        )
        candidates = list(dict.fromkeys(entry[4][0] for entry in addresses))
        if not candidates or any(not ipaddress.ip_address(ip).is_global for ip in candidates):
            raise ValueError
    except (OSError, ValueError) as exc:
        raise AppError(
            "IMAGE_URL_REJECTED", "The image URL must resolve to a public address.", 502
        ) from exc
    return (
        url.copy_with(host=candidates[0]),
        {"Host": url.netloc.decode()},
        {"sni_hostname": url.host},
    )


class OpenAIImagesAdapter:
    def __init__(self, client: httpx.AsyncClient, *, budgets=None):
        self.client = client
        self.budgets = budgets

    async def generate(self, config, key, prompt, *, size=None):
        if self.budgets is not None:
            async with self.budgets.slot(config):
                return await self._generate(config, key, prompt, size=size)
        return await self._generate(config, key, prompt, size=size)

    async def _generate(self, config, key, prompt, *, size=None):
        payload = {"model": config.model_id, "prompt": prompt, "n": 1}
        if size:
            payload["size"] = size
        try:
            async with self.client.stream(
                "POST",
                f"{config.base_url}/images/generations",
                headers={"Authorization": f"Bearer {key}"} if key else {},
                json=payload,
                timeout=300,
            ) as response:
                raw = await bounded_bytes(response, MAX_RESPONSE_BYTES)
            result = json.loads(raw)
            item = result["data"][0]
            if item.get("b64_json"):
                encoded = item["b64_json"]
                if not isinstance(encoded, str) or len(encoded) > MAX_RESPONSE_BYTES:
                    raise ValueError
                raw_image = base64.b64decode(encoded, validate=True)
            elif item.get("url"):
                raw_image = await self.download(item["url"], config.base_url)
            else:
                raise ValueError
            return await asyncio.to_thread(validated_image, raw_image)
        except httpx.TimeoutException as exc:
            raise AppError(
                "IMAGE_GENERATION_TIMEOUT", "Image generation timed out. Retry this image.", 502
            ) from exc
        except httpx.HTTPError as exc:
            raise AppError(
                "IMAGE_GENERATION_FAILED",
                "Image generation or download failed. Check the image model and retry.",
                502,
            ) from exc
        except (
            ValueError,
            KeyError,
            IndexError,
            TypeError,
            binascii.Error,
            httpx.InvalidURL,
        ) as exc:
            raise AppError(
                "IMAGE_OUTPUT_INVALID", "The provider returned no usable image.", 502
            ) from exc

    async def download(self, value, provider):
        url, provider_url = httpx.URL(value), httpx.URL(provider)
        for _ in range(4):
            target, headers, extensions = await download_target(url, provider_url)
            # Never forward the provider key/cookies to an image URL, even on the same origin.
            request = httpx.Request("GET", target, headers=headers, extensions=extensions)
            response = await self.client.send(request, stream=True, follow_redirects=False)
            try:
                if response.status_code in {301, 302, 303, 307, 308}:
                    url = url.join(response.headers["location"])
                    continue
                return await bounded_bytes(response, MAX_IMAGE_BYTES)
            finally:
                await response.aclose()
        raise AppError("IMAGE_URL_REJECTED", "The image download redirected too many times.", 502)
