from __future__ import annotations

import re


_RE_PRICE_WAN = re.compile(r"(?P<num>\d+(?:\.\d+)?)\s*万")
_RE_INT = re.compile(r"\d+")
_RE_FLOAT = re.compile(r"\d+(?:\.\d+)?")


def parse_price_cny(text: str | None) -> float | None:
    if not text:
        return None
    t = text.replace(",", "").replace(" ", "")
    m = _RE_PRICE_WAN.search(t)
    if m:
        return float(m.group("num")) * 10000.0
    nums = _RE_INT.findall(t)
    if not nums:
        return None
    try:
        return float(nums[0])
    except ValueError:
        return None


def parse_mileage_km(text: str | None) -> int | None:
    if not text:
        return None
    t = text.replace(",", "").replace(" ", "")
    m = _RE_PRICE_WAN.search(t)
    if m and ("公里" in t or "km" in t.lower()):
        return int(float(m.group("num")) * 10000.0)
    nums = _RE_INT.findall(t)
    if not nums:
        return None
    try:
        return int(nums[0])
    except ValueError:
        return None


def parse_year(text: str | None) -> int | None:
    if not text:
        return None
    m = re.search(r"(19\d{2}|20\d{2})", text)
    if not m:
        return None
    try:
        return int(m.group(1))
    except ValueError:
        return None


def parse_engine_volume_l(text: str | None) -> float | None:
    if not text:
        return None
    t = text.strip().lower().replace(" ", "")

    # 2.0L / 1.5t
    m = re.search(r"(\d+(?:\.\d+)?)l", t)
    if m:
        try:
            return float(m.group(1))
        except ValueError:
            return None

    m = re.search(r"(\d+(?:\.\d+)?)t", t)
    if m:
        try:
            return float(m.group(1))
        except ValueError:
            return None

    # 1998cc / 1998ml / 1998毫升
    m = re.search(r"(\d{3,5})\s*(cc|ml|毫升)", t)
    if m:
        try:
            cc = int(m.group(1))
            return round(cc / 1000.0, 3)
        except ValueError:
            return None

    # fallback: just a float (assume liters if <= 10)
    m = _RE_FLOAT.search(t)
    if m:
        try:
            v = float(m.group(0))
            if 0.4 <= v <= 10:
                return v
        except ValueError:
            return None
    return None


def parse_power_hp(text: str | None) -> int | None:
    if not text:
        return None
    t = text.strip().lower().replace(",", "")

    # 171马力 / 171hp / 171ps
    m = re.search(r"(\d{2,4})\s*(马力|hp|ps)", t)
    if m:
        try:
            return int(m.group(1))
        except ValueError:
            return None

    # fallback: first int in reasonable range
    nums = _RE_INT.findall(t)
    for n in nums:
        try:
            v = int(n)
        except ValueError:
            continue
        if 40 <= v <= 2000:
            return v
    return None
