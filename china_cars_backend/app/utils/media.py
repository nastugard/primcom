from __future__ import annotations

import asyncio
import io
import pathlib
import re
from urllib.parse import urlparse

import aiofiles
import httpx
from PIL import Image

from app.utils.hashing import sha256_bytes


def _guess_ext(url: str, content_type: str | None) -> str:
    if content_type:
        ct = content_type.split(";")[0].strip().lower()
        if ct == "image/jpeg":
            return ".jpg"
        if ct == "image/png":
            return ".png"
        if ct == "image/webp":
            return ".webp"

    path = urlparse(url).path
    m = re.search(r"\.(jpe?g|png|webp)$", path, flags=re.IGNORECASE)
    if m:
        return "." + m.group(1).lower().replace("jpeg", "jpg")
    return ".jpg"


def _to_webp_bytes(data: bytes) -> bytes:
    with Image.open(io.BytesIO(data)) as im:
        if im.mode in ("RGBA", "LA") or (im.mode == "P" and "transparency" in im.info):
            im = im.convert("RGBA")
        else:
            im = im.convert("RGB")
        out = io.BytesIO()
        im.save(out, format="WEBP", quality=80, method=6)
        return out.getvalue()


def _referer_for_url(url: str) -> str:
    host = (urlparse(url).hostname or "").lower()
    if "guazi" in host:
        return "https://www.guazi.com/"
    if "che168" in host:
        return "https://m.che168.com/"
    if "dongchedi" in host:
        return "https://www.dongchedi.com/"
    return "https://www.guazi.com/"


async def download_image(url: str, dest: pathlib.Path, timeout_s: float = 45.0) -> tuple[str, str]:
    dest.parent.mkdir(parents=True, exist_ok=True)
    headers = {
        "User-Agent": "Mozilla/5.0",
        "Accept": "image/avif,image/webp,image/apng,image/*,*/*;q=0.8",
        "Referer": _referer_for_url(url),
    }
    last_error: Exception | None = None
    for attempt in range(1, 4):
        attempt_timeout_s = timeout_s * (1.0 + 0.35 * (attempt - 1))
        timeout = httpx.Timeout(timeout=attempt_timeout_s, connect=min(15.0, attempt_timeout_s))
        try:
            async with httpx.AsyncClient(follow_redirects=True, timeout=timeout) as client:
                r = await client.get(url, headers=headers)
                r.raise_for_status()
                content_type = (r.headers.get("content-type") or "").split(";", 1)[0].strip().lower()
                if content_type and not content_type.startswith("image/"):
                    raise ValueError(f"Non-image content-type: {content_type}")
                data = r.content
                final_path = dest.with_suffix(".webp")
                if content_type == "image/webp":
                    out_bytes = data
                else:
                    out_bytes = await asyncio.to_thread(_to_webp_bytes, data)
                break
        except (
            httpx.ReadTimeout,
            httpx.ConnectTimeout,
            httpx.WriteTimeout,
            httpx.ReadError,
            httpx.ConnectError,
            httpx.RemoteProtocolError,
        ) as e:
            last_error = e
            if attempt >= 3:
                raise
            await asyncio.sleep(0.8 * attempt)
    else:
        if last_error is not None:
            raise last_error
        raise RuntimeError("download_image failed without details")

    async with aiofiles.open(final_path, "wb") as f:
        await f.write(out_bytes)

    return str(final_path), sha256_bytes(out_bytes)


async def save_upload_image_bytes(data: bytes, dest: pathlib.Path) -> tuple[str, str]:
    dest.parent.mkdir(parents=True, exist_ok=True)
    out_bytes = await asyncio.to_thread(_to_webp_bytes, data)
    final_path = dest.with_suffix(".webp")
    async with aiofiles.open(final_path, "wb") as f:
        await f.write(out_bytes)
    return str(final_path), sha256_bytes(out_bytes)
