from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


async def upsert_canonical_vehicle(
    session: AsyncSession,
    *,
    listing_id: str,
    brand: str | None,
    model: str | None,
    generation: str | None = None,
    trim: str | None = None,
) -> None:
    if not brand or not model:
        return

    res_make = await session.execute(
        text(
            "INSERT INTO vehicle_make(name) VALUES(:name) "
            "ON CONFLICT (name) DO UPDATE SET name=EXCLUDED.name RETURNING id"
        ),
        {"name": brand.strip()},
    )
    make_id = int(res_make.scalar())

    res_model = await session.execute(
        text(
            "INSERT INTO vehicle_model(make_id, name) VALUES(:make_id, :name) "
            "ON CONFLICT (make_id, name) DO UPDATE SET name=EXCLUDED.name RETURNING id"
        ),
        {"make_id": make_id, "name": model.strip()},
    )
    model_id = int(res_model.scalar())

    generation_id = None
    if generation:
        res_gen = await session.execute(
            text(
                "INSERT INTO vehicle_generation(model_id, name) VALUES(:model_id, :name) "
                "ON CONFLICT (model_id, name) DO UPDATE SET name=EXCLUDED.name RETURNING id"
            ),
            {"model_id": model_id, "name": generation.strip()},
        )
        generation_id = int(res_gen.scalar())

    trim_id = None
    if trim and generation_id is not None:
        res_trim = await session.execute(
            text(
                "INSERT INTO vehicle_trim(generation_id, name) VALUES(:generation_id, :name) "
                "ON CONFLICT (generation_id, name) DO UPDATE SET name=EXCLUDED.name RETURNING id"
            ),
            {"generation_id": generation_id, "name": trim.strip()},
        )
        trim_id = int(res_trim.scalar())

    await session.execute(
        text(
            "INSERT INTO listing_vehicle_map(listing_id, make_id, model_id, generation_id, trim_id) "
            "VALUES(:listing_id, :make_id, :model_id, :generation_id, :trim_id) "
            "ON CONFLICT (listing_id) DO UPDATE SET "
            "make_id=EXCLUDED.make_id, model_id=EXCLUDED.model_id, generation_id=EXCLUDED.generation_id, trim_id=EXCLUDED.trim_id"
        ),
        {
            "listing_id": listing_id,
            "make_id": make_id,
            "model_id": model_id,
            "generation_id": generation_id,
            "trim_id": trim_id,
        },
    )
