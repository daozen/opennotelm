"""Bounded public-page download. Resolve once, pin IP, and recheck every redirect."""

import asyncio
import ipaddress
import socket
from dataclasses import dataclass
from urllib.parse import urljoin, urlsplit, urlunsplit

import httpx

from .errors import AppError


def normalize_web_url(value: str) -> str:
    try:
        if len(value) > 4096 or any(ord(c) < 33 for c in value) or "\\" in value:
            raise ValueError
        url = urlsplit(value)
        host = (url.hostname or "").encode("idna").decode("ascii").lower().rstrip(".")
        if (
            url.scheme.lower() not in ("http", "https")
            or not host
            or url.username is not None
            or url.password is not None
            or url.port not in (None, 80, 443)
            or "%" in host
        ):
            raise ValueError
        try:
            address = ipaddress.ip_address(host)
        except ValueError:
            if "." not in host or host.endswith((".localhost", ".local", ".internal")):
                raise ValueError from None
        else:
            if not public_address(str(address)):
                raise AppError("WEB_URL_BLOCKED", "Only public web pages can be imported.")
        authority = f"[{host}]" if ":" in host else host
        default = 443 if url.scheme.lower() == "https" else 80
        if url.port and url.port != default:
            authority += f":{url.port}"
        return urlunsplit((url.scheme.lower(), authority, url.path or "/", url.query, ""))
    except AppError:
        raise
    except (ValueError, UnicodeError):
        raise AppError("WEB_URL_INVALID", "Enter a valid public HTTP or HTTPS URL.") from None


def public_address(value: str) -> bool:
    address = ipaddress.ip_address(value)
    # IPv6 transition/tunnel addresses can map public-looking IPs to private destinations.
    if isinstance(address, ipaddress.IPv6Address) and (
        address.ipv4_mapped or address.sixtofour or address.teredo
    ):
        return False
    return address.is_global and not address.is_multicast


async def resolve_public(host: str, port: int, fake_ip_fallback=True) -> str:
    try:
        addresses = await asyncio.get_running_loop().getaddrinfo(
            host, port, type=socket.SOCK_STREAM
        )
    except OSError:
        raise AppError("WEB_FETCH_FAILED", "The web page could not be reached.") from None
    ips = list(dict.fromkeys(info[4][0] for info in addresses))
    if (
        ips
        and fake_ip_fallback
        and all(ipaddress.ip_address(ip) in ipaddress.ip_network("198.18.0.0/15") for ip in ips)
    ):
        # TUN proxies commonly synthesize these benchmark IPs. Never connect to
        # them directly: obtain real public A records through a pinned DoH server.
        ips = await resolve_doh(host)
    if not ips or any(not public_address(ip) for ip in ips):
        raise AppError("WEB_URL_BLOCKED", "Only public web pages can be imported.")
    return ips[0]


async def resolve_doh(host: str) -> list[str]:
    try:
        async with httpx.AsyncClient(trust_env=False, follow_redirects=False, timeout=10) as client:
            async with client.stream(
                "GET",
                "https://1.1.1.1/dns-query",
                params={"name": host, "type": "A"},
                headers={"Host": "cloudflare-dns.com", "Accept": "application/dns-json"},
                extensions={"sni_hostname": "cloudflare-dns.com"},
            ) as response:
                response.raise_for_status()
                data = bytearray()
                async for chunk in response.aiter_bytes(16 * 1024):
                    data.extend(chunk)
                    if len(data) > 64 * 1024:
                        raise ValueError
                import json

                result = json.loads(data)
                if result.get("Status") != 0:
                    raise ValueError
                ips = [r["data"] for r in result.get("Answer", []) if r.get("type") == 1]
                if not ips or any(not public_address(ip) for ip in ips):
                    raise AppError("WEB_URL_BLOCKED", "Only public web pages can be imported.")
                return ips
    except (httpx.HTTPError, ValueError, KeyError, TypeError, AttributeError):
        raise AppError("WEB_FETCH_FAILED", "Public DNS resolution failed.") from None


@dataclass
class WebSnapshot:
    data: bytes
    final_url: str
    content_type: str


class WebFetcher:
    def __init__(
        self,
        max_bytes=10 * 1024 * 1024,
        timeout=30,
        resolver=None,
        transport=None,
        fake_ip_fallback=True,
        image=False,
    ):
        self.max_bytes, self.timeout = max_bytes, timeout

        async def resolve(host, port):
            return await resolve_public(host, port, fake_ip_fallback)

        self.resolver = resolver or resolve
        self.transport = transport
        self.image = image

    async def fetch(self, value: str) -> WebSnapshot:
        try:
            async with asyncio.timeout(self.timeout):
                return await self._fetch(normalize_web_url(value))
        except (TimeoutError, httpx.TimeoutException):
            raise AppError("WEB_FETCH_TIMEOUT", "The web page took too long to respond.") from None
        except httpx.HTTPError:
            raise AppError("WEB_FETCH_FAILED", "The web page could not be reached.") from None

    async def _fetch(self, url: str) -> WebSnapshot:
        async with httpx.AsyncClient(
            trust_env=False, follow_redirects=False, timeout=self.timeout, transport=self.transport
        ) as client:
            for _ in range(6):
                target = httpx.URL(url)
                address = await self.resolver(
                    target.host, target.port or (443 if target.scheme == "https" else 80)
                )
                if not public_address(address):
                    raise AppError("WEB_URL_BLOCKED", "Only public web pages can be imported.")
                # TLS still authenticates the original hostname, not the chosen IP.
                pinned = target.copy_with(host=address)
                async with client.stream(
                    "GET",
                    pinned,
                    headers={
                        "Host": target.netloc.decode("ascii"),
                        "User-Agent": "OpenNoteLM/0.1 (user-requested source import)",
                        "Accept": "image/png,image/jpeg,image/webp,image/gif,image/avif"
                        if self.image
                        else "text/html,application/xhtml+xml",
                    },
                    extensions={"sni_hostname": target.host},
                ) as response:
                    if response.status_code in (301, 302, 303, 307, 308):
                        location = response.headers.get("location")
                        if not location:
                            break
                        url = normalize_web_url(urljoin(url, location))
                        continue
                    if response.status_code in (401, 403):
                        raise AppError(
                            "WEB_ACCESS_DENIED", "The website denied access to this page."
                        )
                    if response.status_code >= 400:
                        raise AppError("WEB_HTTP_ERROR", "The website returned an error.")
                    content_type = response.headers.get("content-type", "").lower()
                    accepted = (
                        ("image/png", "image/jpeg", "image/webp", "image/gif", "image/avif")
                        if self.image
                        else (
                            "text/html",
                            "application/xhtml+xml",
                        )
                    )
                    if content_type.split(";", 1)[0].strip() not in accepted:
                        raise AppError(
                            "WEB_IMAGE_TYPE_UNSUPPORTED" if self.image else "WEB_TYPE_UNSUPPORTED",
                            "This image format is unsupported."
                            if self.image
                            else "This URL does not point to an HTML page.",
                        )
                    data = bytearray()
                    async for chunk in response.aiter_bytes(64 * 1024):
                        data.extend(chunk)
                        if len(data) > self.max_bytes:
                            raise AppError(
                                "WEB_IMAGE_TOO_LARGE" if self.image else "WEB_TOO_LARGE",
                                "The downloaded file exceeds the size limit.",
                            )
                    return WebSnapshot(bytes(data), url, content_type)
        raise AppError("WEB_REDIRECT_LIMIT", "The web page redirects too many times.")
