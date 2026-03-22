"""
modules/darkweb/crawler.py — Depth-2 onion crawler with forum/marketplace parsing.

For each URL found by dark web search engines, this crawler:
  1. Fetches the page through Tor
  2. Extracts all .onion links
  3. Follows those links up to `dark_crawl_depth` hops
  4. On each page it looks for credential patterns, forum posts,
     marketplace listings, and pastes mentioning the query
"""

import asyncio
import random
import re
import urllib.parse
from collections import deque
from typing import Set, Dict, Optional
from bs4 import BeautifulSoup

from modules.utils.http  import async_get_tor
from modules.utils.dedup import ResultStore
from modules.utils.tui   import TUI
from modules.darkweb.parser import PageParser


# Patterns we hunt for on every crawled page
CRED_PATTERN    = re.compile(
    r'[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}\s*[:|]\s*\S+',
    re.IGNORECASE
)
HASH_PATTERN    = re.compile(r'\b[0-9a-fA-F]{32,128}\b')
SSH_KEY_PATTERN = re.compile(r'-----BEGIN\s+(?:RSA|EC|OPENSSH)\s+PRIVATE KEY-----')
API_KEY_PATTERN = re.compile(
    r'(?:api[_-]?key|secret[_-]?key|access[_-]?token|auth[_-]?token)\s*[=:]\s*["\']?([A-Za-z0-9_\-]{16,})',
    re.IGNORECASE
)


class OnionCrawler:
    def __init__(self, cfg: dict, tor_proxy: str, store: ResultStore, tui: TUI):
        self.cfg      = cfg
        self.tor      = tor_proxy
        self.store    = store
        self.tui      = tui
        self.depth    = cfg.get("dark_crawl_depth", 2)
        self.timeout  = cfg.get("dark_timeout", 40)
        self.min_d    = cfg.get("dark_min_delay", 2.0)
        self.max_d    = cfg.get("dark_max_delay", 7.0)
        self.max_res  = cfg.get("max_results_per_source", 50)
        self.parser   = PageParser()
        self._visited: Set[str] = set()
        self._lock    = asyncio.Lock()

    async def run(self, query: str, qtype: str):
        self.tui.dark_section("ONION LINK CRAWLER  (depth-2)")
        self.tui.info(f"[CRAWLER] Starting breadth-first crawl — depth {self.depth}")

        # Seeds: onion URLs already found by the engine module
        seeds = [r["data"] for r in self.store.all_results()
                 if ".onion" in r.get("data","") and r.get("data","").startswith("http")]

        # Add hardcoded entry-point known forums / paste boards
        seeds += self._hardcoded_seeds(query)
        seeds  = list(dict.fromkeys(seeds))[:40]   # deduplicate, cap at 40 seeds

        self.tui.info(f"[CRAWLER] {len(seeds)} seed URLs to crawl")

        sem   = asyncio.Semaphore(self.cfg.get("dark_workers", 6))
        queue = deque([(url, 0) for url in seeds])

        while queue:
            batch = []
            while queue and len(batch) < 8:
                batch.append(queue.popleft())

            tasks = [self._crawl_one(url, depth, query, qtype, sem)
                     for url, depth in batch]
            new_links_list = await asyncio.gather(*tasks, return_exceptions=True)

            for result in new_links_list:
                if isinstance(result, list):
                    for link, d in result:
                        if d <= self.depth:
                            queue.append((link, d))

        total_crawled = len(self._visited)
        self.tui.info(f"[CRAWLER] Finished — crawled {total_crawled} unique onion pages")

    async def _crawl_one(self, url: str, depth: int,
                         query: str, qtype: str,
                         sem: asyncio.Semaphore):
        async with self._lock:
            if url in self._visited:
                return []
            self._visited.add(url)

        if depth > self.depth:
            return []

        async with sem:
            await asyncio.sleep(random.uniform(self.min_d, self.max_d))
            resp = await async_get_tor(url, self.tor, timeout=self.timeout, retries=1)

        if resp is None or resp.status_code != 200:
            return []

        html  = resp.text
        soup  = BeautifulSoup(html, "lxml")
        title = (soup.find("title") or soup.find("h1"))
        title = title.get_text(strip=True)[:100] if title else url

        self.tui.info(f"[CRAWLER] d{depth} — {url[:60]}  [{title[:40]}]")

        # Extract structured content
        page_type, structured = self.parser.detect_and_parse(soup, url, query)

        for item in structured:
            extra = {**item, "page_type": page_type, "depth": str(depth),
                     "source_url": url[:100]}
            val   = item.get("content", item.get("title", url))[:120]
            if self.store.add("onion_crawl", qtype, query, val, extra):
                self.tui.result_card(self.store.count(), "onion_crawl",
                                     qtype, val, extra)

        # Pattern-based extraction from raw text
        self._extract_patterns(html, query, qtype, url, depth)

        # Collect child links for next depth
        new_links = []
        if depth < self.depth:
            for a in soup.find_all("a", href=True):
                href = a["href"].strip()
                href = self._resolve(href, url)
                if href and ".onion" in href and href not in self._visited:
                    new_links.append((href, depth + 1))

        return new_links[:20]  # cap expansion per page

    def _extract_patterns(self, html: str, query: str, qtype: str,
                           src_url: str, depth: int):
        text = html

        # Credential lines (email:password combos)
        for m in CRED_PATTERN.finditer(text):
            line = m.group(0).strip()[:200]
            if query.lower() in line.lower():
                extra = {"pattern": "credential", "depth": str(depth),
                         "source_url": src_url[:100]}
                if self.store.add("onion_crawl", qtype, query, line, extra):
                    self.tui.result_card(self.store.count(), "onion_crawl",
                                         qtype, line, extra)

        # SSH / private keys
        if SSH_KEY_PATTERN.search(text) and query.lower() in text.lower():
            extra = {"pattern": "private_key", "depth": str(depth),
                     "source_url": src_url[:100]}
            val = f"SSH/RSA private key found at {src_url[:80]}"
            if self.store.add("onion_crawl", qtype, query, val, extra):
                self.tui.result_card(self.store.count(), "onion_crawl",
                                     qtype, val, extra)

        # API / secret keys
        for m in API_KEY_PATTERN.finditer(text):
            line = m.group(0)[:120]
            if query.lower() in text.lower():
                extra = {"pattern": "api_key", "value": m.group(1)[:60],
                         "depth": str(depth), "source_url": src_url[:100]}
                if self.store.add("onion_crawl", qtype, query, line, extra):
                    self.tui.result_card(self.store.count(), "onion_crawl",
                                         qtype, line, extra)

    @staticmethod
    def _resolve(href: str, base: str) -> str:
        if href.startswith("http"):
            return href
        if href.startswith("//"):
            return "http:" + href
        if href.startswith("/"):
            p = urllib.parse.urlparse(base)
            return f"{p.scheme}://{p.netloc}{href}"
        return ""

    @staticmethod
    def _hardcoded_seeds(query: str) -> list:
        """Known dark-web forums and paste boards worth seeding."""
        q = urllib.parse.quote(query)
        return [
            # Forums / leak boards
            f"http://breachforums.st/search?q={q}",   # clearnet mirror sometimes up
            f"http://crackingxjmpkfpxvhgua5h4b2shvgkh3tfxb5axuuqv4n4jt6r25wid.onion/search?q={q}",
            # Paste boards on Tor
            f"http://depastedihrn3jtw.onion/search.php?search={q}",
            f"http://zqktlwi4fecvo6ri.onion/wiki/index.php?search={q}",
            # Darknet market search aggregators
            f"http://32rknkty4iim35s6zqjxrkrfehuq47t56ymijtjoyjwkitkukrfhufid.onion/search?q={q}",
            # Dark web Pastebin alternatives
            f"http://pastenow5qhwdtpm.onion/?q={q}",
            f"http://strongerw2ise74v3duebgsvug4mehyhlpa7f6kfwnas7zofs3kov7yd.onion/search?q={q}",
        ]
