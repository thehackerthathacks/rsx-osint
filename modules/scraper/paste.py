"""modules/scraper/paste.py — Paste site scraping with exact-match filtering"""

import asyncio
import re
import urllib.parse
from bs4 import BeautifulSoup

from modules.utils.http  import async_get
from modules.utils.dedup import ResultStore
from modules.utils.tui   import TUI


PASTE_SOURCES = [
    ("https://psbdmp.ws/api/search/{q}",           "psbdmp",    "json"),
    ("https://pastebin.com/search?q={q}",          "pastebin",  "html"),
    ("https://paste.ee/search?q={q}",              "paste.ee",  "html"),
    ("https://justpaste.it/search?q={q}",          "justpaste", "html"),
    ("https://paste2.org/search?q={q}",            "paste2",    "html"),
    ("https://rentry.co/search?q={q}",             "rentry",    "html"),
    ("https://controlc.com/search.php?search={q}", "controlc",  "html"),
]


class PasteModule:
    def __init__(self, cfg, proxy_mgr, store: ResultStore, tui: TUI):
        self.cfg     = cfg
        self.pm      = proxy_mgr
        self.store   = store
        self.tui     = tui
        self.max_res = cfg.get("max_results_per_source", 50)
        self.timeout = cfg.get("request_timeout", 25)

    async def run(self, query: str, qtype: str):
        self.tui.section("PASTE SITE RECONNAISSANCE", "📋")
        tasks = [self._scrape(query, qtype, url_t, name, fmt)
                 for url_t, name, fmt in PASTE_SOURCES]
        await asyncio.gather(*tasks, return_exceptions=True)

    async def _scrape(self, query, qtype, url_tmpl, source, fmt):
        self.tui.info(f"{source} — searching...")
        proxy = self.pm.get()
        url   = url_tmpl.replace("{q}", urllib.parse.quote(query))
        resp  = await async_get(url, proxy=proxy, timeout=self.timeout)

        if resp is None or resp.status_code != 200:
            self.tui.warn(
                f"{source}: no response / HTTP "
                f"{getattr(resp, 'status_code', '—')}"
            )
            return

        if fmt == "json":
            await self._handle_json(resp, query, qtype, source)
        else:
            await self._handle_html(resp, query, qtype, source, url)

    async def _handle_json(self, resp, query, qtype, source):
        try:
            data  = resp.json()
            items = data if isinstance(data, list) else data.get("data", [])
        except Exception:
            return

        q_lower = query.lower()

        for item in items[:self.max_res]:
            pid     = item.get("id", "")
            snippet = item.get("text", item.get("content", ""))
            link    = f"https://pastebin.com/{pid}" if pid else ""
            raw     = f"https://pastebin.com/raw/{pid}" if pid else ""

            # Fetch the raw paste and scan for exact match
            if raw:
                await asyncio.sleep(0.4)
                raw_resp = await async_get(raw, timeout=12)
                if raw_resp and raw_resp.status_code == 200:
                    self._scan_raw_content(
                        raw_resp.text, query, qtype, source, link
                    )
                    continue

            # Fallback: use snippet if raw not available
            if snippet and q_lower in snippet.lower():
                self._emit_match(query, qtype, source, link,
                                 snippet[:200], raw)

    async def _handle_html(self, resp, query, qtype, source, base_url):
        soup    = BeautifulSoup(resp.text, "lxml")
        q_lower = query.lower()
        sels    = [
            ".search-result a[href]", ".result a[href]",
            "article a[href]", "table tr td a[href]", "li a[href]",
        ]
        links = []
        for sel in sels:
            for a in soup.select(sel)[:self.max_res]:
                href = a.get("href", "")
                text = a.get_text(strip=True)[:100]
                if not href.startswith("http"):
                    from urllib.parse import urlparse
                    p    = urlparse(base_url)
                    href = f"{p.scheme}://{p.netloc}{href}"
                if q_lower in (text + href).lower():
                    links.append((href, text))
            if links:
                break

        for href, text in links[:self.max_res]:
            # Fetch the page and scan content
            await asyncio.sleep(0.3)
            page_resp = await async_get(href, timeout=12)
            if page_resp and page_resp.status_code == 200:
                self._scan_raw_content(page_resp.text, query, qtype,
                                       source, href)
            else:
                # Emit the link itself as a lead even if fetch failed
                if q_lower in text.lower():
                    self._emit_match(query, qtype, source, href, text, "")

    def _scan_raw_content(self, text: str, query: str, qtype: str,
                           source: str, page_url: str):
        q_lower = query.lower()
        if q_lower not in text.lower():
            return

        lines   = text.splitlines()
        matched = 0
        for line in lines:
            line = line.strip()
            if not line or len(line) < 4:
                continue
            if q_lower not in line.lower():
                continue
            if matched >= 30:
                break

            u, _, p = line.partition(":")
            extra = {
                "raw line":   line[:200],
                "email/user": u.strip()[:80],
                "password":   p.strip()[:80] if p else "(empty)",
                "found in":   page_url[:100],
            }
            if self.store.add(source, qtype, query, line[:200], extra):
                self.tui.result_card(self.store.count(), source,
                                     qtype, line[:200], extra)
                matched += 1

    def _emit_match(self, query, qtype, source, url, snippet, raw_url):
        extra = {
            "snippet": snippet[:200],
            "url":     url,
            "raw":     raw_url,
        }
        if self.store.add(source, qtype, query, url, extra):
            self.tui.result_card(self.store.count(), source,
                                 qtype, url, extra)
