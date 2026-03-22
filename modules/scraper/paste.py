"""modules/scraper/paste.py — Paste site scraping with raw-content credential extraction"""

import asyncio
import re
import urllib.parse
from bs4 import BeautifulSoup

from modules.utils.http  import async_get
from modules.utils.dedup import ResultStore
from modules.utils.tui   import TUI


PASTE_SOURCES = [
    ("https://psbdmp.ws/api/search/{q}",              "psbdmp",    "json"),
    ("https://pastebin.com/search?q={q}",             "pastebin",  "html"),
    ("https://paste.ee/search?q={q}",                 "paste.ee",  "html"),
    ("https://justpaste.it/search?q={q}",             "justpaste", "html"),
    ("https://paste2.org/search?q={q}",               "paste2",    "html"),
    ("https://rentry.co/search?q={q}",                "rentry",    "html"),
    ("https://controlc.com/search.php?search={q}",    "controlc",  "html"),
]

CRED_RE = re.compile(
    r'[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}\s*[:|]\s*\S+', re.I)


class PasteModule:
    def __init__(self, cfg, proxy_mgr, store: ResultStore, tui: TUI):
        self.cfg     = cfg
        self.pm      = proxy_mgr
        self.store   = store
        self.tui     = tui
        self.limit   = cfg.get("max_results_per_source", 50)
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
            self.tui.warn(f"{source}: no response / HTTP {getattr(resp,'status_code','—')}"); return

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
        for item in items[:self.limit]:
            pid     = item.get("id", "")
            snippet = item.get("text", item.get("content", ""))[:140]
            link    = f"https://pastebin.com/{pid}" if pid else ""
            raw     = f"https://pastebin.com/raw/{pid}" if pid else ""
            extra   = {"snippet": snippet, "raw url": raw,
                       "added": item.get("time", item.get("date", ""))}
            if link and self.store.add(source, qtype, query, link, extra):
                self.tui.result_card(self.store.count(), source, qtype, link, extra)
            if raw:
                await asyncio.sleep(0.4)
                raw_resp = await async_get(raw, timeout=10)
                if raw_resp and raw_resp.status_code == 200:
                    self._extract_from_raw(raw_resp.text, query, qtype,
                                           source + "_content")

    async def _handle_html(self, resp, query, qtype, source, base_url):
        soup  = BeautifulSoup(resp.text, "lxml")
        sels  = [".search-result a[href]", ".result a[href]",
                 "article a[href]", "table tr td a[href]", "li a[href]"]
        links = []
        for sel in sels:
            for a in soup.select(sel)[:self.limit]:
                href = a.get("href", "")
                text = a.get_text(strip=True)[:100]
                if not href.startswith("http"):
                    from urllib.parse import urlparse
                    p    = urlparse(base_url)
                    href = f"{p.scheme}://{p.netloc}{href}"
                if query.lower() in (text + href).lower():
                    links.append((href, text))
            if links:
                break

        for href, text in links[:self.limit]:
            extra = {"snippet": text, "site": source}
            if self.store.add(source, qtype, query, href, extra):
                self.tui.result_card(self.store.count(), source, qtype, href, extra)
            await asyncio.sleep(0.3)

    def _extract_from_raw(self, text: str, query: str, qtype: str, source: str):
        for m in CRED_RE.finditer(text):
            line = m.group(0).strip()[:200]
            if query.lower() in line.lower():
                extra = {"context": "credential extracted from paste raw content"}
                if self.store.add(source, qtype, query, line, extra):
                    self.tui.result_card(self.store.count(), source, qtype, line, extra)
