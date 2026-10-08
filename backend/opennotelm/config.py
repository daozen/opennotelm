import os
from dataclasses import dataclass, field
from pathlib import Path

MAX_IMAGE_GENERATION_CONCURRENCY = 20
MAX_IMAGE_RECOGNITION_CONCURRENCY = 20
MAX_CONTENT_GENERATION_CONCURRENCY = 20


@dataclass(frozen=True)
class Settings:
    data_dir: Path = field(default_factory=lambda: Path(os.getenv("DATA_DIR", "data")).resolve())
    frontend_dir: Path = field(
        default_factory=lambda: Path(os.getenv("FRONTEND_DIR", "frontend/dist")).resolve()
    )
    allowed_hosts: tuple[str, ...] = field(
        default_factory=lambda: tuple(
            os.getenv("ALLOWED_HOSTS", "localhost,127.0.0.1,[::1],testserver").split(",")
        )
    )
    # Detailed storyboards and image generation can take several minutes before
    # compatible providers return a non-streaming response.
    provider_timeout: float = 300
    task_concurrency: int = field(default_factory=lambda: int(os.getenv("TASK_CONCURRENCY", "3")))
    model_request_concurrency: int = field(
        default_factory=lambda: int(os.getenv("MODEL_REQUEST_CONCURRENCY", "8"))
    )
    image_generation_concurrency: int = field(
        default_factory=lambda: int(os.getenv("IMAGE_GENERATION_CONCURRENCY", "2"))
    )
    image_recognition_concurrency: int = field(
        default_factory=lambda: int(os.getenv("IMAGE_RECOGNITION_CONCURRENCY", "4"))
    )
    content_generation_concurrency: int = field(
        default_factory=lambda: int(os.getenv("CONTENT_GENERATION_CONCURRENCY", "2"))
    )
    speech_generation_concurrency: int = field(
        default_factory=lambda: int(os.getenv("SPEECH_GENERATION_CONCURRENCY", "2"))
    )
    telemetry_host: str = field(
        default_factory=lambda: os.getenv("TELEMETRY_HOST", "https://us.i.posthog.com")
    )
    telemetry_project_token: str = field(
        default_factory=lambda: os.getenv("TELEMETRY_PROJECT_TOKEN", ""), repr=False
    )
    render_browser_executable: str | None = field(
        default_factory=lambda: os.getenv("RENDER_BROWSER_EXECUTABLE") or None
    )
    max_document_bytes: int = field(
        default_factory=lambda: int(os.getenv("MAX_DOCUMENT_BYTES", str(200 * 1024 * 1024)))
    )
    max_text_bytes: int = field(
        default_factory=lambda: int(os.getenv("MAX_TEXT_BYTES", str(20 * 1024 * 1024)))
    )
    max_web_bytes: int = field(
        default_factory=lambda: int(os.getenv("MAX_WEB_BYTES", str(10 * 1024 * 1024)))
    )
    web_fetch_timeout: float = field(
        default_factory=lambda: float(os.getenv("WEB_FETCH_TIMEOUT", "30"))
    )
    web_fake_ip_dns_fallback: bool = field(
        default_factory=lambda: os.getenv("WEB_FAKE_IP_DNS_FALLBACK", "1") == "1"
    )
    max_web_images: int = field(default_factory=lambda: int(os.getenv("MAX_WEB_IMAGES", "50")))
    max_web_image_bytes: int = field(
        default_factory=lambda: int(os.getenv("MAX_WEB_IMAGE_BYTES", str(10 * 1024 * 1024)))
    )
    max_web_images_bytes: int = field(
        default_factory=lambda: int(os.getenv("MAX_WEB_IMAGES_BYTES", str(100 * 1024 * 1024)))
    )
    web_image_download_concurrency: int = field(
        default_factory=lambda: int(os.getenv("WEB_IMAGE_DOWNLOAD_CONCURRENCY", "4"))
    )
    web_image_timeout: float = field(
        default_factory=lambda: float(os.getenv("WEB_IMAGE_TIMEOUT", "20"))
    )
    web_images_timeout: float = field(
        default_factory=lambda: float(os.getenv("WEB_IMAGES_TIMEOUT", "120"))
    )
    max_sources_per_notebook: int = field(
        default_factory=lambda: int(os.getenv("MAX_SOURCES_PER_NOTEBOOK", "50"))
    )
    max_epub_entries: int = field(
        default_factory=lambda: int(os.getenv("MAX_EPUB_ENTRIES", "10000"))
    )
    max_epub_uncompressed_bytes: int = field(
        default_factory=lambda: int(
            os.getenv("MAX_EPUB_UNCOMPRESSED_BYTES", str(400 * 1024 * 1024))
        )
    )
    max_epub_entry_bytes: int = field(
        default_factory=lambda: int(os.getenv("MAX_EPUB_ENTRY_BYTES", str(20 * 1024 * 1024)))
    )
    max_epub_compression_ratio: int = field(
        default_factory=lambda: int(os.getenv("MAX_EPUB_COMPRESSION_RATIO", "1000"))
    )
    max_pdf_pages: int = field(default_factory=lambda: int(os.getenv("MAX_PDF_PAGES", "5000")))
    min_pdf_text_characters: int = field(
        default_factory=lambda: int(os.getenv("MIN_PDF_TEXT_CHARACTERS", "40"))
    )

    def __post_init__(self) -> None:
        if not 1 <= self.speech_generation_concurrency <= 20:
            raise ValueError("SPEECH_GENERATION_CONCURRENCY must be between 1 and 20")
        if not 1 <= self.task_concurrency <= 8 or not 1 <= self.model_request_concurrency <= 20:
            raise ValueError("Task concurrency must be 1–8 and model concurrency 1–20")
        if (
            not 1 <= self.web_image_download_concurrency <= 20
            or not 1 <= self.max_web_images <= 200
        ):
            raise ValueError("Web image concurrency must be 1–20 and image count 1–200")
        if (
            min(
                self.max_web_image_bytes,
                self.max_web_images_bytes,
                self.web_image_timeout,
                self.web_images_timeout,
            )
            <= 0
        ):
            raise ValueError("Web image download limits must be positive")
        if not 1 <= self.image_generation_concurrency <= MAX_IMAGE_GENERATION_CONCURRENCY:
            raise ValueError("IMAGE_GENERATION_CONCURRENCY must be between 1 and 20")

        if not 1 <= self.image_recognition_concurrency <= MAX_IMAGE_RECOGNITION_CONCURRENCY:
            raise ValueError("IMAGE_RECOGNITION_CONCURRENCY must be between 1 and 20")

        if not 1 <= self.content_generation_concurrency <= MAX_CONTENT_GENERATION_CONCURRENCY:
            raise ValueError("CONTENT_GENERATION_CONCURRENCY must be between 1 and 20")

    def prepare(self) -> None:
        for directory in (
            "sources",
            "assets",
            "renders",
            "exports",
            "podcasts",
            "mindmaps",
            "vector",
            "cache",
            "secrets",
        ):
            (self.data_dir / directory).mkdir(parents=True, exist_ok=True)
        (self.data_dir / "secrets").chmod(0o700)
