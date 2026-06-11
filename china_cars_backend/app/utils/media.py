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


def _to_webp_bytes(data: bytes, *, min_width: int | None = None, min_height: int | None = None) -> bytes:
    with Image.open(io.BytesIO(data)) as im:
        width, height = im.size
        if min_width is not None and width < int(min_width):
            raise ValueError(f"Image is too small: width={width}")
        if min_height is not None and height < int(min_height):
            raise ValueError(f"Image is too small: height={height}")
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


def _is_guazi_image_url(url: str) -> bool:
    host = (urlparse(url).hostname or "").lower()
    return "guazi" in host


def guazi_brand_art_metrics(data: bytes) -> dict[str, float | int]:
    """Return simple visual metrics for Guazi service art detection."""
    try:
        with Image.open(io.BytesIO(data)) as im:
            width, height = im.size
            im = im.convert("RGB")
            im.thumbnail((160, 160))
            pixels = im.load()
            thumb_w, thumb_h = im.size
    except Exception:
        return {"valid": 0}

    if thumb_w <= 0 or thumb_h <= 0:
        return {"valid": 0}

    grid_size = 5
    cell_totals = [0 for _ in range(grid_size * grid_size)]
    cell_greens = [0 for _ in range(grid_size * grid_size)]
    green_count = 0
    strong_green_count = 0
    dark_count = 0
    bright_count = 0
    neutral_count = 0
    total = thumb_w * thumb_h

    for y in range(thumb_h):
        for x in range(thumb_w):
            r, g, b = pixels[x, y]
            avg = (r + g + b) / 3
            is_dark = avg <= 105
            is_bright = avg >= 185
            is_neutral = (max(r, g, b) - min(r, g, b)) <= 32
            is_green = (
                g >= 90
                and (g - r) >= 24
                and (g - b) >= 10
                and g >= int(r * 1.18)
                and g >= int(b * 1.05)
            )
            is_guazi_green = (
                g >= 115
                and (g - r) >= 35
                and (g - b) >= 20
                and g >= int(r * 1.35)
                and g >= int(b * 1.15)
            )

            cell_x = min(grid_size - 1, x * grid_size // thumb_w)
            cell_y = min(grid_size - 1, y * grid_size // thumb_h)
            cell_index = cell_y * grid_size + cell_x
            cell_totals[cell_index] += 1

            if is_dark:
                dark_count += 1
            if is_bright:
                bright_count += 1
            if is_neutral:
                neutral_count += 1
            if is_green:
                green_count += 1
                cell_greens[cell_index] += 1
            if is_guazi_green:
                strong_green_count += 1

    green_ratio = green_count / total
    strong_green_ratio = strong_green_count / total
    dark_ratio = dark_count / total
    bright_ratio = bright_count / total
    neutral_ratio = neutral_count / total
    green_cell_peak = max(
        (green / cell_total for green, cell_total in zip(cell_greens, cell_totals) if cell_total),
        default=0.0,
    )
    score = green_ratio * 1.4 + strong_green_ratio * 1.2 + green_cell_peak * 0.9

    return {
        "valid": 1,
        "width": int(width),
        "height": int(height),
        "green_ratio": round(green_ratio, 4),
        "strong_green_ratio": round(strong_green_ratio, 4),
        "green_cell_peak": round(green_cell_peak, 4),
        "dark_ratio": round(dark_ratio, 4),
        "bright_ratio": round(bright_ratio, 4),
        "neutral_ratio": round(neutral_ratio, 4),
        "score": round(score, 4),
    }


def is_guazi_brand_art_image(data: bytes) -> bool:
    """Detect Guazi service art that is delivered as a normal CDN image."""
    m = guazi_brand_art_metrics(data)
    if not m.get("valid"):
        return False
    width = int(m["width"])
    height = int(m["height"])
    if width < 80 or height < 40:
        return False

    green_ratio = float(m["green_ratio"])
    strong_green_ratio = float(m["strong_green_ratio"])
    green_cell_peak = float(m["green_cell_peak"])
    dark_ratio = float(m["dark_ratio"])
    bright_ratio = float(m["bright_ratio"])
    neutral_ratio = float(m["neutral_ratio"])

    # Service art is usually a large Guazi-green glyph/logo on a flat
    # dark, white, or neutral background. Real car photos may contain green
    # license plates, but the green area is small and not concentrated.
    if height <= 80 and (width / height) >= 3.0:
        return green_ratio >= 0.35 and green_cell_peak >= 0.60 and dark_ratio >= 0.50

    flat_background_ratio = max(dark_ratio, bright_ratio, neutral_ratio)
    if green_ratio >= 0.14 and green_cell_peak >= 0.30 and flat_background_ratio >= 0.45:
        return True
    if strong_green_ratio >= 0.10 and green_cell_peak >= 0.28 and flat_background_ratio >= 0.35:
        return True
    return green_ratio >= 0.22 and green_cell_peak >= 0.42


async def download_image(
    url: str,
    dest: pathlib.Path,
    timeout_s: float = 45.0,
    *,
    force_reencode: bool = False,
    min_width: int | None = None,
    min_height: int | None = None,
) -> tuple[str, str]:
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
                if _is_guazi_image_url(url) and is_guazi_brand_art_image(data):
                    raise ValueError("Rejected Guazi service/brand image")
                final_path = dest.with_suffix(".webp")
                if content_type == "image/webp" and not force_reencode and min_width is None and min_height is None:
                    out_bytes = data
                else:
                    out_bytes = await asyncio.to_thread(
                        _to_webp_bytes,
                        data,
                        min_width=min_width,
                        min_height=min_height,
                    )
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
