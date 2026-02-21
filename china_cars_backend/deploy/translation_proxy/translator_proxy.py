from __future__ import annotations

import json
import os
import re
from typing import Any

from fastapi import FastAPI, Header, HTTPException
from openai import AsyncOpenAI
from pydantic import BaseModel


OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "").strip()
OPENAI_MODEL = os.getenv("OPENAI_TRANSLATION_MODEL", "gpt-5-nano").strip() or "gpt-5-nano"
PROXY_TOKEN = os.getenv("TRANSLATION_PROXY_TOKEN", "").strip()

if not OPENAI_API_KEY:
    raise RuntimeError("OPENAI_API_KEY is required")

client = AsyncOpenAI(api_key=OPENAI_API_KEY)
app = FastAPI(title="Primcom Translation Proxy")


class TranslateIn(BaseModel):
    text: str


class TranslateOut(BaseModel):
    translation: str


class TranslateBatchIn(BaseModel):
    values: list[str]


class TranslateBatchOut(BaseModel):
    translations: dict[str, str]


def _check_auth(auth_header: str | None) -> None:
    if not PROXY_TOKEN:
        return
    if not auth_header or not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing bearer token")
    token = auth_header.split(" ", 1)[1].strip()
    if token != PROXY_TOKEN:
        raise HTTPException(status_code=403, detail="Invalid token")


async def _translate_one(value: str) -> str:
    resp = await client.chat.completions.create(
        model=OPENAI_MODEL,
        messages=[
            {
                "role": "system",
                "content": "Translate the given car brand or model name into English. Output only the translation without quotes.",
            },
            {"role": "user", "content": value},
        ],
    )
    out = ((resp.choices[0].message.content or "").strip() if resp.choices else "").strip()
    out = out.strip('"\'').strip()
    if not out:
        raise RuntimeError("empty translation")
    return out


async def _translate_batch(values: list[str]) -> dict[str, str]:
    uniq: list[str] = []
    seen: set[str] = set()
    for value in values:
        s = str(value or "").strip()
        if not s or s in seen:
            continue
        seen.add(s)
        uniq.append(s)
    if not uniq:
        return {}

    prompt = (
        "Translate the following car brand/model names from Chinese to English. "
        "Return ONLY strict JSON object where each key is original string and value is translation. "
        "No markdown, no comments.\n"
        + json.dumps(uniq, ensure_ascii=False)
    )
    resp = await client.chat.completions.create(
        model=OPENAI_MODEL,
        messages=[
            {"role": "system", "content": "You are a precise automotive translator."},
            {"role": "user", "content": prompt},
        ],
    )
    text_out = ((resp.choices[0].message.content or "").strip() if resp.choices else "").strip()
    cleaned = text_out
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```[a-zA-Z0-9_-]*\n", "", cleaned).strip()
        if cleaned.endswith("```"):
            cleaned = cleaned[:-3].strip()
    obj: Any
    try:
        obj = json.loads(cleaned)
    except Exception:
        start = cleaned.find("{")
        end = cleaned.rfind("}")
        if start < 0 or end <= start:
            obj = {}
        else:
            try:
                obj = json.loads(cleaned[start : end + 1])
            except Exception:
                obj = {}
    if not isinstance(obj, dict):
        return {}
    out: dict[str, str] = {}
    for k, v in obj.items():
        if isinstance(k, str) and isinstance(v, str) and k.strip() and v.strip():
            out[k.strip()] = v.strip()
    return out


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/translate", response_model=TranslateOut)
async def translate_one(payload: TranslateIn, authorization: str | None = Header(default=None)) -> TranslateOut:
    _check_auth(authorization)
    value = str(payload.text or "").strip()
    if not value:
        raise HTTPException(status_code=400, detail="text is required")
    try:
        translated = await _translate_one(value)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"translation failed: {e}") from e
    return TranslateOut(translation=translated)


@app.post("/translate-batch", response_model=TranslateBatchOut)
async def translate_batch(payload: TranslateBatchIn, authorization: str | None = Header(default=None)) -> TranslateBatchOut:
    _check_auth(authorization)
    values = [str(x or "").strip() for x in payload.values]
    values = [x for x in values if x]
    if not values:
        return TranslateBatchOut(translations={})
    try:
        translations = await _translate_batch(values)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"batch translation failed: {e}") from e
    return TranslateBatchOut(translations=translations)
