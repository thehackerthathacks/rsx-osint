"""modules/dorking/engines.py — Surface web dork engine with proxy rotation & captcha bypass"""

import asyncio
import random
import urllib.parse
import re
from typing import List, Optional
from bs4 import BeautifulSoup

from modules.utils.http   import async_get, base_headers, random_ua
from modules.utils.dedup  import ResultStore
from modules.utils.tui    import TUI
from modules.dorking.dorks   import get_dorks
from modules.dorking.captcha import CaptchaSolver


CAPTCHA_SIGNALS = [
    "captcha", "unusual traffic", "robot", "automated", "please verify",
    "are you human", "security check", "challenge", "recaptcha",
    "access denied", "403 forbidden",
]


class DorkEngine:
    def __init__(self, cfg: dict, proxy_mgr, store: ResultStore, tui: TUI):
        self.cfg     = cfg
        self.pm      = proxy_mgr
        self.store   = store
        self.tui     = tui
        self.solver  = CaptchaSolver(cfg)
        self.engines = cfg.get("enabled_dork_engines",
                               ["google", "bing", "duckduckgo", "startpage"])
        self.timeout = cfg.get("request_timeout", 25)
        self.min_d   = cfg.get("min_delay", 1.2)
        self.max_d   = cfg.get("max_delay", 4.5)
        self.max_res = cfg.get("max_results_per_source", 50)

    async def run(self, query: str, qtype: str):
        self.tui.section("SURFACE WEB DORK ENGINE", "🔍")
        dorks = get_dorks(qtype, query)
        self.tui.info(f"Dork engine — {len(dorks)} dork templates × {len(self.engines)} engines")

        tasks = []
        if "google"     in self.engines:
            tasks.append(self._run_engine("google",     query, qtype, dorks))
        if "bing"       in self.engines:
            tasks.append(self._run_engine("bing",       query, qtype, dorks))
        if "duckduckgo" in self.engines:
            tasks.append(self._run_engine("duckduckgo", query, qtype, dorks))
        if "startpage"  in self.engines:
            tasks.append(self._run_engine("startpage",  query, qtype, dorks))
        if "yahoo"      in self.engines:
            tasks.append(self._run_engine("yahoo",      query, qtype, dorks))

        await asyncio.gather(*tasks, return_exceptions=True)

    # ── Per-engine runner ─────────────────────────────────────────────────
    async def _run_engine(self, engine: str, query: str,
                          qtype: str, dorks: List[str]):
        self.tui.info(f"{engine.capitalize()} — starting dork sweep ({len(dorks)} queries)...")
        consecutive_blocks = 0

        for dork in dorks:
            if consecutive_blocks >= 3:
                self.tui.warn(f"{engine}: too many blocks — pausing 30s then continuing")
                await asyncio.sleep(30)
                consecutive_blocks = 0

            proxy = self.pm.get()
            resp  = await self._query_engine(engine, dork, proxy)

            if resp is None:
                self.tui.warn(f"{engine}: no response for dork — skipping")
                await self._jitter()
                continue

            # Captcha / block detection
            if self._is_blocked(resp):
                consecutive_blocks += 1
                self.tui.warn(f"{engine}: block/captcha detected (attempt {consecutive_blocks})")

                # Try captcha solving
                token = await self._attempt_captcha_solve(engine, resp, dork)
                if token:
                    self.tui.info(f"{engine}: captcha solved — retrying with token")
                    resp = await self._query_engine(engine, dork, proxy,
                                                    captcha_token=token)

                if resp is None or self._is_blocked(resp):
                    # Rotate proxy and retry once
                    if proxy:
                        self.pm.mark_bad(proxy)
                    proxy = self.pm.get()
                    await asyncio.sleep(random.uniform(5, 12))
                    resp = await self._query_engine(engine, dork, proxy)

                if resp is None or self._is_blocked(resp):
                    await asyncio.sleep(random.uniform(15, 30))
                    continue

            consecutive_blocks = 0
            results = self._parse_engine(engine, resp.text, dork)
            for href, snippet in results:
                src_name = f"{engine}_dork"
                extra    = {"dork": dork[:80], "snippet": snippet[:100],
                            "engine": engine}
                if self.store.add(src_name, qtype, query, href, extra):
                    self.tui.result_card(self.store.count(), src_name,
                                         qtype, href, extra)

            await self._jitter()

    # ── Engine query builders ─────────────────────────────────────────────
    async def _query_engine(self, engine: str, dork: str, proxy: Optional[str],
                            page: int = 0,
                            captcha_token: Optional[str] = None) -> Optional[object]:
        q = urllib.parse.quote(dork)
        ua = random_ua()
        hdrs = base_headers()
        hdrs["User-Agent"] = ua

        if engine == "google":
            start = page * 10
            url   = f"https://www.google.com/search?q={q}&num=10&start={start}&hl=en&safe=off"
            if captcha_token:
                url += f"&g-recaptcha-response={captcha_token}"
            hdrs["Referer"] = "https://www.google.com/"

        elif engine == "bing":
            first = page * 10 + 1
            url   = f"https://www.bing.com/search?q={q}&first={first}&count=10"
            hdrs["Referer"] = "https://www.bing.com/"

        elif engine == "duckduckgo":
            url  = f"https://html.duckduckgo.com/html/?q={q}"
            hdrs["Referer"] = "https://duckduckgo.com/"

        elif engine == "startpage":
            url  = f"https://www.startpage.com/sp/search?q={q}&page={page+1}"
            hdrs["Referer"] = "https://www.startpage.com/"

        elif engine == "yahoo":
            b    = page * 10 + 1
            url  = f"https://search.yahoo.com/search?p={q}&b={b}&count=10"
            hdrs["Referer"] = "https://search.yahoo.com/"

        else:
            return None

        return await async_get(url, proxy=proxy, headers=hdrs, timeout=self.timeout)

    # ── Result parsers per engine ─────────────────────────────────────────
    def _parse_engine(self, engine: str, html: str, dork: str) -> List[tuple]:
        soup    = BeautifulSoup(html, "lxml")
        results = []

        if engine == "google":
            for g in soup.select("div.g, div[data-hveid]")[:10]:
                a = g.select_one("a[href]")
                s = g.select_one(".VwiC3b, .s3v9rd, .st, span.aCOpRe")
                if a:
                    href = self._clean_google_url(a.get("href",""))
                    if href and "google.com" not in href:
                        snip = s.get_text(strip=True)[:120] if s else ""
                        results.append((href, snip))

        elif engine == "bing":
            for li in soup.select("li.b_algo, .b_algo")[:10]:
                a = li.select_one("h2 a, a[href]")
                s = li.select_one("p, .b_caption p")
                if a:
                    href = a.get("href","")
                    if href.startswith("http") and "bing.com" not in href:
                        snip = s.get_text(strip=True)[:120] if s else ""
                        results.append((href, snip))

        elif engine == "duckduckgo":
            for r in soup.select(".result, .web-result")[:10]:
                a = r.select_one(".result__a, a.result__url")
                s = r.select_one(".result__snippet, .result__body")
                if a:
                    href = a.get("href","")
                    if not href.startswith("http"):
                        href = "https://duckduckgo.com" + href
                    # DDG uses redirects — extract actual URL
                    parsed = urllib.parse.urlparse(href)
                    qs     = urllib.parse.parse_qs(parsed.query)
                    href   = qs.get("uddg", qs.get("u", [href]))[0]
                    if href.startswith("http") and "duckduckgo.com" not in href:
                        snip = s.get_text(strip=True)[:120] if s else ""
                        results.append((href, snip))

        elif engine == "startpage":
            for r in soup.select(".result, .w-gl__result")[:10]:
                a = r.select_one("a.result-link, a[href]")
                s = r.select_one("p.description, p.w-gl__description")
                if a:
                    href = a.get("href","")
                    if href.startswith("http") and "startpage.com" not in href:
                        snip = s.get_text(strip=True)[:120] if s else ""
                        results.append((href, snip))

        elif engine == "yahoo":
            for r in soup.select("div.Sr, .algo, li[class*='algo']")[:10]:
                a = r.select_one("a[href]")
                s = r.select_one("p, .compText")
                if a:
                    href = a.get("href","")
                    if href.startswith("http") and "yahoo.com" not in href:
                        snip = s.get_text(strip=True)[:120] if s else ""
                        results.append((href, snip))

        return results

    # ── Helpers ───────────────────────────────────────────────────────────
    def _is_blocked(self, resp) -> bool:
        if resp is None:
            return True
        if resp.status_code in (403, 429, 503):
            return True
        low = resp.text.lower()
        return any(sig in low for sig in CAPTCHA_SIGNALS)

    async def _attempt_captcha_solve(self, engine: str,
                                     resp, dork: str) -> Optional[str]:
        if not self.solver.enabled:
            return None
        html = resp.text
        # Extract recaptcha site key if present
        match = re.search(r'data-sitekey=["\']([^"\']+)["\']', html)
        if match:
            site_key = match.group(1)
            self.tui.info(f"{engine}: attempting recaptcha solve via {self.solver.service}...")
            token = await self.solver.solve_recaptcha(site_key, resp.url)
            return token
        return None

    def _clean_google_url(self, href: str) -> str:
        if href.startswith("/url?"):
            qs  = urllib.parse.parse_qs(urllib.parse.urlparse(href).query)
            return qs.get("q", qs.get("url", [href]))[0]
        return href if href.startswith("http") else ""

    async def _jitter(self):
        delay = random.uniform(self.min_d, self.max_d)
        await asyncio.sleep(delay)
