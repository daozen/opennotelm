"""Archive bounded article images locally; one failed image never fails the article."""

import asyncio
import hashlib
import json
import re
from io import BytesIO

from PIL import Image

from .concurrency import joined_thread
from .errors import AppError
from .model_service import now
from .request_limits import SharedStageBudget
from .source_vision import normalize_image
from .web_fetch import WebFetcher

WEB_IMAGES_VERSION = "web-images-v1"
ORIGINAL_NAME = re.compile(r"original-[a-f0-9]{64}\.(png|jpg|webp|gif|avif)\Z")


def decode_web_image(data):
    with Image.open(BytesIO(data)) as image:
        if image.format not in ("PNG", "JPEG", "WEBP", "GIF", "AVIF"):
            raise AppError("WEB_IMAGE_TYPE_UNSUPPORTED", "This image format is unsupported.")
        suffix = {"PNG": "png", "JPEG": "jpg", "WEBP": "webp", "GIF": "gif", "AVIF": "avif"}[
            image.format
        ]
    preview, size = normalize_image(data)
    return preview, size, suffix


def save_atomic(path, data):
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_bytes(data)
    temporary.replace(path)


class WebImageService:
    def __init__(self, settings):
        self.settings = settings
        self.download_budget = SharedStageBudget()
        self.fetcher = WebFetcher(
            settings.max_web_image_bytes,
            settings.web_image_timeout,
            fake_ip_fallback=settings.web_fake_ip_dns_fallback,
            image=True,
        )

    async def download(self, source_id, document, context, previous_images=(), *, on_saved=None):
        directory = self.settings.data_dir / "sources" / source_id / "media"
        directory.mkdir(exist_ok=True)
        checkpoint = directory / "web-images.json"
        try:
            saved = json.loads(checkpoint.read_text())
        except (OSError, ValueError):
            saved = {}
        if not isinstance(saved, dict):
            saved = {}
        saved = {
            key: value
            for key, value in saved.items()
            if isinstance(value, dict)
            and isinstance(value.get("source_image_url"), str)
            and isinstance(value.get("original_file"), str)
            and ORIGINAL_NAME.fullmatch(value["original_file"])
        }
        # Published provenance can recover a damaged/missing download checkpoint.
        # Never replace an archived original with today's bytes at the same URL.
        saved = {
            **saved,
            **{info["id"]: info for info in previous_images if info.get("original_file")},
        }
        infos = [
            {"id": image.id, "status": "failed", "error_code": "WEB_FETCH_TIMEOUT"}
            for image in document.images
        ]
        originals, downloads, locks = set(), {}, {}
        total_bytes, completed = 0, 0
        pending = iter(enumerate(document.images))

        async def process(index, image):
            nonlocal total_bytes
            cached = saved.get(image.id, {})
            url = (
                cached.get("source_image_url")
                if cached.get("original_file")
                else image.location["source_image_url"]
            )
            image.location["source_image_url"] = url
            info = {
                "id": image.id,
                "node_id": image.node_id,
                "kind": image.kind,
                "source_image_url": url,
                "alt": image.location["alt"],
                "status": "failed",
            }
            try:
                async with locks.setdefault(url, asyncio.Lock()):
                    result = downloads.get(url)
                    if result is None:
                        data = None
                        filename = cached.get("original_file", "")
                        # Only our own content-addressed files may be read, never a saved URL/path.
                        if cached.get("source_image_url") == url and ORIGINAL_NAME.fullmatch(
                            filename
                        ):
                            path = directory / filename
                            if (
                                path.resolve().is_relative_to(directory.resolve())
                                and path.is_file()
                                and path.stat().st_size <= self.settings.max_web_image_bytes
                            ):
                                candidate = path.read_bytes()
                                if hashlib.sha256(candidate).hexdigest() == cached.get("sha256"):
                                    data = candidate
                            if data is None:
                                raise AppError(
                                    "SOURCE_MEDIA_NOT_FOUND",
                                    "The saved original image is unavailable.",
                                )
                        final_url = cached.get("final_image_url", url)
                        fetched_at = cached.get("image_fetched_at")
                        if data is None:
                            snapshot = await self.fetcher.fetch(url)
                            data, final_url = snapshot.data, snapshot.final_url
                            fetched_at = now()
                        try:
                            preview, size, suffix = await joined_thread(decode_web_image, data)
                        except (OSError, ValueError, Image.DecompressionBombError) as error:
                            raise AppError(
                                "SOURCE_IMAGE_INVALID", "This image could not be decoded safely."
                            ) from error
                        if size[0] <= 32 and size[1] <= 32:
                            raise AppError(
                                "WEB_IMAGE_DECORATIVE", "This small decorative image was skipped."
                            )
                        checksum = hashlib.sha256(data).hexdigest()
                        if checksum not in originals:
                            if total_bytes + len(data) > self.settings.max_web_images_bytes:
                                raise AppError(
                                    "WEB_IMAGE_TOO_LARGE",
                                    "The article images exceed the total size limit.",
                                )
                            total_bytes += len(data)
                            originals.add(checksum)
                        filename = f"original-{checksum}.{suffix}"
                        path = directory / filename
                        if not path.exists():
                            save_atomic(path, data)
                        result = downloads[url] = (
                            data,
                            preview,
                            size,
                            filename,
                            checksum,
                            final_url,
                            fetched_at,
                        )
                    data, preview, size, filename, checksum, final_url, fetched_at = result
                    save_atomic(directory / (image.id + ".png"), preview)
                    info.update(
                        status="saved",
                        original_file=filename,
                        sha256=checksum,
                        final_image_url=final_url,
                        image_fetched_at=fetched_at,
                        width=size[0],
                        height=size[1],
                        image_url=f"/api/sources/{source_id}/media/{image.id}",
                        original_image_url=f"/api/sources/{source_id}/media/{image.id}/original",
                    )
                    image.data = data
                    image.location.update(original_image_url=info["original_image_url"])
                    saved[image.id] = info
                    save_atomic(checkpoint, json.dumps(saved, ensure_ascii=False).encode())
            except AppError as error:
                info.update(
                    status="skipped" if error.code == "WEB_IMAGE_DECORATIVE" else "failed",
                    error_code=error.code,
                )
            except OSError:
                info["error_code"] = "SOURCE_IMPORT_FAILED"
            infos[index] = info

        async def worker():
            nonlocal completed
            for index, image in pending:
                async with self.download_budget.slot(self.settings.web_image_download_concurrency):
                    await process(index, image)
                if on_saved is not None and infos[index]["status"] == "saved":
                    on_saved(index, image)
                completed += 1
                context.progress("fetching_images", 0.1 + 0.2 * completed / len(infos))

        try:
            async with asyncio.timeout(self.settings.web_images_timeout):
                async with asyncio.TaskGroup() as group:
                    for _ in range(min(self.settings.web_image_download_concurrency, len(infos))):
                        group.create_task(worker())
        except TimeoutError:
            pass  # Successful siblings/checkpoints survive the batch deadline.
        document.metadata["web_image_downloads"] = infos
        document.metadata["web_image_bytes"] = total_bytes
        return infos
