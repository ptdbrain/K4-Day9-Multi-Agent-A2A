"""Trace logger — writes agent steps to trace.jsonl."""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

TRACE_FILE = Path(__file__).parent.parent / "trace.jsonl"


class TraceLogger:
    """Append-mode JSONL logger for agent trace."""

    _instance: "TraceLogger | None" = None
    _file = None

    def __new__(cls) -> "TraceLogger":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def open(self) -> None:
        """Open (truncate) trace file for a fresh run."""
        self._file = open(TRACE_FILE, "w", encoding="utf-8")

    def close(self) -> None:
        if self._file:
            self._file.close()
            self._file = None

    def log(
        self,
        case_id: str,
        agent: str,
        step: str,
        data: Any = None,
        model: str | None = None,
    ) -> None:
        record = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "case_id": case_id,
            "agent": agent,
            "step": step,
        }
        if model:
            record["model"] = model
        if data is not None:
            record["data"] = data
        line = json.dumps(record, ensure_ascii=False, default=str)
        if self._file:
            self._file.write(line + "\n")
            self._file.flush()
        else:
            # fallback: open + append
            with open(TRACE_FILE, "a", encoding="utf-8") as f:
                f.write(line + "\n")
