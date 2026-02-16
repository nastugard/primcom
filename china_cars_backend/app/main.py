from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.api import router
from app.core import settings


def create_app() -> FastAPI:
    app = FastAPI(title="Primcom China Cars API", version="2.0.0")

    app.mount(
        "/media",
        StaticFiles(directory=settings.media_dir, check_dir=False),
        name="media",
    )

    cors_origins = settings.cors_origins_list
    if cors_origins:
        allow_origins = list(cors_origins)
        if "null" not in allow_origins:
            allow_origins.append("null")
    else:
        allow_origins = ["*"]

    app.add_middleware(
        CORSMiddleware,
        allow_origins=allow_origins,
        allow_credentials=False,
        allow_origin_regex=r"^https?://(localhost|127\.0\.0\.1)(:\d+)?$",
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(router)
    return app


app = create_app()
