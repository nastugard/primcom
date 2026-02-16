from __future__ import annotations

from openai import AsyncOpenAI
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import settings
from app.repositories.catalog import (
    get_translation_cache,
    increment_translation_hits,
    upsert_translation_cache,
)
from app.utils.hashing import sha256_text
from app.utils.name_translation import BRAND_MAP, MODEL_MAP, has_chinese, normalize_by_dict


async def translate_term(session: AsyncSession, client: AsyncOpenAI | None, value: str | None) -> str | None:
    if not value:
        return value
    src = str(value).strip()
    if not src:
        return value

    # local dict first
    mapped = normalize_by_dict(src, BRAND_MAP)
    if mapped == src:
        mapped = normalize_by_dict(src, MODEL_MAP)
    if mapped and mapped != src:
        await upsert_translation_cache(
            session,
            source_text=src,
            normalized_text=mapped,
            lang_from="zh",
            lang_to="en",
            provider="dict",
            model="dict",
            checksum=sha256_text(src),
        )
        return mapped

    if not has_chinese(src):
        return src

    cached = await get_translation_cache(session, source_text=src, lang_from="zh", lang_to="en")
    if cached:
        await increment_translation_hits(session, source_text=src, lang_from="zh", lang_to="en")
        return cached

    if client is None:
        return src

    resp = await client.chat.completions.create(
        model=settings.openai_translation_model,
        messages=[
            {
                "role": "system",
                "content": "Translate Chinese car brand/model/trim into English. Output only translated text.",
            },
            {"role": "user", "content": src},
        ],
        temperature=0,
    )
    out = ((resp.choices[0].message.content or "").strip() if resp.choices else "").strip('"\' ').strip()
    if not out:
        out = src
    await upsert_translation_cache(
        session,
        source_text=src,
        normalized_text=out,
        lang_from="zh",
        lang_to="en",
        provider="openai",
        model=settings.openai_translation_model,
        checksum=sha256_text(src),
    )
    return out
