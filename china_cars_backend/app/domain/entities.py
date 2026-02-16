from __future__ import annotations

import dataclasses
import datetime as dt
from typing import Literal

RunStatus = Literal["running", "success", "partial", "failed"]


@dataclasses.dataclass
class IngestStats:
    source: str
    started_at: dt.datetime
    finished_at: dt.datetime | None = None
    status: RunStatus = "running"
    fetched: int = 0
    upserted: int = 0
    skipped: int = 0
    errors: list[str] = dataclasses.field(default_factory=list)
