"""Base agent class with built-in trace logging."""
from __future__ import annotations

from typing import Any

from src.data_loader import DataLoader
from src.logger import TraceLogger


class BaseAgent:
    """
    All agents inherit from this class.
    Provides:
      - self.db  → DataLoader singleton
      - self.trace → TraceLogger singleton
      - self.log() helper
    """

    name: str = "BaseAgent"

    def __init__(self) -> None:
        self.db = DataLoader()
        self.trace = TraceLogger()

    def log(
        self,
        case_id: str,
        step: str,
        data: Any = None,
        model: str | None = None,
    ) -> None:
        self.trace.log(
            case_id=case_id,
            agent=self.name,
            step=step,
            data=data,
            model=model,
        )
