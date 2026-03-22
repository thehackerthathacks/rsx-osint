"""modules/utils/proxy.py — Proxy rotation and management"""

import os
import random
import asyncio
from typing import Optional, List


class ProxyManager:
    def __init__(self, cfg: dict):
        self._proxies: List[str] = []
        self._bad:     set       = set()
        self._lock = asyncio.Lock() if False else None  # used sync
        self._cfg  = cfg
        self._idx  = 0
        self._load()

    def _load(self):
        path = self._cfg.get("proxy_file", "config/proxies.txt")
        if os.path.exists(path):
            with open(path) as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#"):
                        self._proxies.append(line)

    def get(self) -> Optional[str]:
        if not self._cfg.get("rotate_proxies", True) or not self._proxies:
            return None
        available = [p for p in self._proxies if p not in self._bad]
        if not available:
            self._bad.clear()
            available = self._proxies[:]
        if not available:
            return None
        proxy = random.choice(available)
        return proxy

    def mark_bad(self, proxy: str):
        self._bad.add(proxy)

    def has_proxies(self) -> bool:
        return bool(self._proxies)

    def count(self) -> int:
        return len(self._proxies)

    def to_aiohttp(self, proxy: Optional[str]) -> Optional[str]:
        return proxy

    def to_requests(self, proxy: Optional[str]) -> Optional[dict]:
        if not proxy:
            return None
        return {"http": proxy, "https": proxy}
