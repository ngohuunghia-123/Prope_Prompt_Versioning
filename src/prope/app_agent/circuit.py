"""Small reusable breaker; each feature owns a separate instance."""

import time
from collections import deque
from collections.abc import Awaitable, Callable


class CircuitOpenError(RuntimeError):
    pass


class CircuitBreaker:
    def __init__(self, *, on_state_change: Callable[[bool], None]) -> None:
        self._outcomes: deque[bool] = deque(maxlen=20)
        self._opened_at: float | None = None
        self._cooldown_seconds = 30.0
        self._on_state_change = on_state_change

    async def call[T](self, operation: Callable[[], Awaitable[T]]) -> T:
        now = time.monotonic()
        if self._opened_at is not None:
            if now - self._opened_at < self._cooldown_seconds:
                self._on_state_change(True)
                raise CircuitOpenError("App Agent circuit breaker is open")
            self._opened_at = None
            self._on_state_change(False)

        try:
            result = await operation()
        except Exception:
            self._outcomes.append(False)
            if len(self._outcomes) >= 10 and self._outcomes.count(False) / len(self._outcomes) > 0.5:
                self._opened_at = now
                self._on_state_change(True)
            raise
        self._outcomes.append(True)
        return result
