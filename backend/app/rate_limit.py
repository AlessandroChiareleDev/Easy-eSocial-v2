"""Rate limiter simples em memória (sliding window).

Para produção com múltiplos workers, considerar Redis. Para single-host
single-process (caso atual: uvicorn --workers 2 atrás de nginx) já mitiga
brute force razoavelmente — o pior cenário é 2x o limite efetivo.
"""
from __future__ import annotations

import threading
import time
from collections import defaultdict, deque

from fastapi import HTTPException, Request, status


class SlidingWindowLimiter:
    def __init__(self, max_hits: int, window_seconds: float):
        self.max_hits = max_hits
        self.window = window_seconds
        self._buckets: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def check(self, key: str) -> None:
        now = time.monotonic()
        cutoff = now - self.window
        with self._lock:
            q = self._buckets[key]
            while q and q[0] < cutoff:
                q.popleft()
            if len(q) >= self.max_hits:
                retry_in = int(q[0] + self.window - now) + 1
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail=f"muitas tentativas, aguarde {retry_in}s",
                    headers={"Retry-After": str(retry_in)},
                )
            q.append(now)


# Limites por endpoint
login_limiter = SlidingWindowLimiter(max_hits=8, window_seconds=300.0)


def login_rate_limit(request: Request) -> None:
    """Dependência FastAPI: limita por IP."""
    ip = request.client.host if request.client else "unknown"
    login_limiter.check(f"login:{ip}")
