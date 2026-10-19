from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class RecordingBoundary:
    """Callable fake that records exact external-boundary interactions."""

    response: Any = None
    calls: list[dict[str, Any]] = field(default_factory=list)

    def __call__(self, *args: Any, **kwargs: Any) -> Any:
        self.calls.append({"args": list(args), "kwargs": kwargs})
        return self.response


@dataclass
class AsyncRecordingBoundary(RecordingBoundary):
    """Awaitable variant for async external service boundaries."""

    async def __call__(self, *args: Any, **kwargs: Any) -> Any:
        self.calls.append({"args": list(args), "kwargs": kwargs})
        return self.response
