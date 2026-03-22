"""modules/utils/dedup.py — Thread-safe result store with deduplication"""

import threading
import hashlib
from typing import List, Dict


class ResultStore:
    def __init__(self):
        self._results: List[Dict] = []
        self._seen:    set        = set()
        self._lock = threading.Lock()
        self._counter = 0

    def add(self, source: str, qtype: str, query: str, data: str,
            extra: dict = None) -> bool:
        key = hashlib.md5(f"{source}|{data}".encode()).hexdigest()
        with self._lock:
            if key in self._seen:
                return False
            self._seen.add(key)
            self._counter += 1
            self._results.append({
                "index":  self._counter,
                "source": source,
                "type":   qtype,
                "query":  query,
                "data":   str(data),
                "extra":  extra or {},
            })
            return True

    def all_results(self) -> List[Dict]:
        with self._lock:
            return list(self._results)

    def count(self) -> int:
        with self._lock:
            return self._counter

    def stats(self) -> Dict[str, int]:
        with self._lock:
            out: Dict[str, int] = {}
            for r in self._results:
                out[r["source"]] = out.get(r["source"], 0) + 1
            return out
