"""
modules/darkweb/engines.py

Dark web search strategy:
  1. Search each onion engine using broad breach/leak discovery terms
     (not the target query directly — that rarely works on onion engines).
  2. Collect all result URLs from those searches.
  3. Fetch each result page and scan the full text for the target query.
  4. Extract and display any lines / blocks that contain it.
"""

import asyncio
import random
import re
import urllib.parse
from bs4 import BeautifulSoup
from typing import List, Tuple, Optional

from modules.utils.http  import async_get_tor, async_post_tor
from modules.utils.dedup import ResultStore
from modules.utils.tui   import TUI


DARK_ENGINES = {
    "ahmia": {
        "url":     "https://ahmia.fi/search/?q={q}&page={p}",
        "onion":   "http://juhanurmihxlp77nkq76byazcldy2hlmovfu2epvl5ankdibsot4csyd.onion/search/?q={q}&page={p}",
        "results": "li.result",
        "link":    "a",
        "snippet": "p",
        "pages":   5,
    },
    "torch": {
        "url":     "http://torchdeedp3i2jigzjdmfpn5ttjhthh5wbmda2rr3jvqjg5p77c54dqd.onion/search?query={q}&action=search&page={p}",
        "results": ".result-block, .searchresult, tr",
        "link":    "a",
        "snippet": "p, td",
        "pages":   5,
    },
    "haystak": {
        "url":     "http://haystak5njsmn2hqkewecpaxetahtwhsbsa64jom2k22z5afxhnpxfid.onion/?q={q}&p={p}",
        "results": ".result, li, .searchresult",
        "link":    "a",
        "snippet": "p, span.url",
        "pages":   5,
    },
    "darksearch": {
        "url":   "https://darksearch.io/api/search?query={q}&page={p}",
        "api":   True,
        "pages": 5,
    },
    "notevil": {
        "url":     "http://notevilmtxkakyam.onion/?q={q}&t=0&sa=0&p={p}",
        "results": ".result, li, tr",
        "link":    "a",
        "snippet": "p, span",
        "pages":   4,
    },
    "phobos": {
        "url":     "http://phobosxilamwcg75ywyi47marznuwp3jp4o76nxckb7bcf4ot674kkid.onion/search?q={q}&p={p}",
        "results": ".result, .searchresult",
        "link":    "a",
        "snippet": "p",
        "pages":   4,
    },
    "excavator": {
        "url":     "http://2fd6cemt4gmccflhm6imvdfvli3nf7zn6rfrwpsy7uhxrgbypvwf5fad.onion/search/?q={q}&start={p}",
        "results": "li.result, .result",
        "link":    "a",
        "snippet": "p",
        "pages":   4,
        "page_multiplier": 10,
    },
    "kilos": {
        "url":     "http://mlyusr6htlxsyc7t2f4z53wdxh3win7q3qpxcrbam6jn3neoericfbyd.onion/search?q={q}&page={p}",
        "results": ".item, .listing, .result, .product",
        "link":    "a",
        "snippet": ".description, p, .title",
        "pages":   4,
    },
    "onionsearchengine": {
        "url":     "http://3fzh7yuupdfyjhwt3ugzqqof6ulbcl27ecev33knxe3u7goi3vfn2qqd.onion/search.php?q={q}&page={p}",
        "results": ".result, li, table tr",
        "link":    "a",
        "snippet": "p, td",
        "pages":   4,
    },
    "pwndb": {
        "url":     "http://pwndb2am4tzkvold.onion/",
        "special": "pwndb",
    },
}

# Broad terms used to discover breach/leak pages on dark web engines.
# The real target query is then searched *within* the fetched pages.
DISCOVERY_TERMS = {
    "email":    ["data breach email dump", "leaked credentials", "combo list", "email password database"],
    "username": ["leaked accounts", "credential dump", "username password list", "account database"],
    "password": ["password dump", "combo list leak", "credential database", "plaintext passwords"],
    "hash":     ["hash dump", "password hashes", "cracked hashes", "hash database"],
    "ip":       ["ip address leak", "server logs dump", "ip database", "access logs"],
    "domain":   ["database dump", "site breach", "sql dump", "leaked data"],
    "phone":    ["phone number leak", "mobile database", "dox database", "personal info dump"],
    "name":     ["personal data leak", "dox database", "personal info dump", "identity data"],
    "default":  ["data breach", "leaked data", "credential dump", "database leak"],
}

CRED_LINE_RE = re.compile(
    r'[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}\s*[:|]\s*\S+|'
    r'\S+\s*[:|]\s*\S{4,}',
    re.IGNORECASE,
)


class DarkWebEngine:
    def __init__(self, cfg: dict, tor_proxy: str, store: ResultStore, tui: TUI):
        self.cfg       = cfg
        self.tor       = tor_proxy
        self.store     = store
        self.tui       = tui
        self.enabled   = cfg.get("enabled_dark_engines", list(DARK_ENGINES.keys()))
        self.max_pages = cfg.get("dark_crawl_pages", 5)
        self.timeout   = cfg.get("dark_timeout", 40)
        self.min_d     = cfg.get("dark_min_delay", 2.0)
        self.max_d     = cfg.get("dark_max_delay", 7.0)
        self.max_res   = cfg.get("max_results_per_source", 50)
        self._fetched_urls: set = set()
        self._url_lock = asyncio.Lock()

    async def run(self, query: str, qtype: str):
        self.tui.dark_section("DARK WEB SEARCH ENGINES")

        discovery_queries = DISCOVERY_TERMS.get(qtype, DISCOVERY_TERMS["default"])
        self.tui.info(
            f"[TOR] Strategy: search for {len(discovery_queries)} breach discovery terms, "
            f"then scan result pages for '{query}'"
        )

        # Phase 1 — collect result URLs from all engines using discovery terms
        collected_urls: List[Tuple[str, str]] = []  # (url, source_engine)
        collect_tasks = []

        for name, ecfg in DARK_ENGINES.items():
            if name not in self.enabled:
                continue
            if ecfg.get("special") == "pwndb":
                continue
            for dq in discovery_queries[:2]:
                if ecfg.get("api"):
                    collect_tasks.append(
                        self._collect_api(name, ecfg, dq, collected_urls)
                    )
                else:
                    collect_tasks.append(
                        self._collect_html(name, ecfg, dq, collected_urls)
                    )

        await asyncio.gather(*collect_tasks, return_exceptions=True)

        unique_urls = list(dict.fromkeys(u for u, _ in collected_urls))
        self.tui.info(f"[TOR] Phase 1 complete — {len(unique_urls)} unique pages to scan")

        # Phase 2 — fetch each page and scan for the target query
        if unique_urls:
            self.tui.info(f"[TOR] Phase 2 — scanning pages for: {query}")
            sem        = asyncio.Semaphore(self.cfg.get("dark_workers", 6))
            scan_tasks = [
                self._scan_page(url, query, qtype, sem)
                for url in unique_urls[:80]
            ]
            await asyncio.gather(*scan_tasks, return_exceptions=True)

        # Phase 3 — PwnDB direct query (still useful, targeted)
        if "pwndb" in self.enabled:
            await self._run_pwndb(query, qtype)

    # ── Phase 1: collect URLs ─────────────────────────────────────────────

    async def _collect_html(self, name: str, ecfg: dict,
                             discovery_query: str, out: list):
        q        = urllib.parse.quote(discovery_query)
        base_url = ecfg.get("onion", ecfg.get("url", ""))
        mul      = ecfg.get("page_multiplier", 1)
        max_p    = min(ecfg.get("pages", 3), self.max_pages)

        for page in range(max_p):
            url  = base_url.replace("{q}", q).replace("{p}", str(page * mul))
            resp = await async_get_tor(url, self.tor, timeout=self.timeout)

            if resp is None or resp.status_code != 200:
                break

            soup    = BeautifulSoup(resp.text, "lxml")
            results = self._parse_html_results(soup, ecfg)

            if not results:
                break

            for href, _, _ in results:
                out.append((href, name))

            await self._jitter()

    async def _collect_api(self, name: str, ecfg: dict,
                            discovery_query: str, out: list):
        q = urllib.parse.quote(discovery_query)

        for page in range(1, self.max_pages + 1):
            url  = ecfg["url"].replace("{q}", q).replace("{p}", str(page))
            resp = await async_get_tor(url, self.tor, timeout=self.timeout)

            if resp is None:
                break
            try:
                data = resp.json()
                hits = data.get("data", data.get("results", []))
                if not hits:
                    break
                for item in hits:
                    href = item.get("link", item.get("url", ""))
                    if href:
                        out.append((href, name))
            except Exception:
                break

            await self._jitter()

    # ── Phase 2: scan pages for target ───────────────────────────────────

    async def _scan_page(self, url: str, query: str, qtype: str,
                         sem: asyncio.Semaphore):
        async with self._url_lock:
            if url in self._fetched_urls:
                return
            self._fetched_urls.add(url)

        async with sem:
            await asyncio.sleep(random.uniform(self.min_d, self.max_d))
            resp = await async_get_tor(url, self.tor, timeout=self.timeout, retries=1)

        if resp is None or resp.status_code != 200:
            return

        text = resp.text
        if query.lower() not in text.lower():
            return

        # Found the target on this page — extract context
        self.tui.info(f"[TOR] HIT on {url[:70]}")
        soup  = BeautifulSoup(text, "lxml")
        lines = soup.get_text(separator="\n").splitlines()

        hits_on_page = 0
        for i, line in enumerate(lines):
            line = line.strip()
            if not line or len(line) < 4:
                continue
            if query.lower() not in line.lower():
                continue

            # Get surrounding context (1 line before, 1 after)
            before  = lines[i - 1].strip() if i > 0 else ""
            after   = lines[i + 1].strip() if i < len(lines) - 1 else ""
            context = " | ".join(filter(None, [before, line, after]))[:300]

            extra = {
                "found on":  url[:100],
                "raw line":  line[:200],
                "context":   context,
            }

            # Try to detect if it's a credential pair
            if ":" in line and hits_on_page < self.max_res:
                parts = line.split(":", 1)
                extra["left"]  = parts[0].strip()[:80]
                extra["right"] = parts[1].strip()[:80]

            if self.store.add("onion_page_scan", qtype, query, line[:200], extra):
                self.tui.result_card(
                    self.store.count(), "onion_page_scan", qtype, line[:200], extra
                )
                hits_on_page += 1

            if hits_on_page >= 30:
                break

    # ── HTML result parser ────────────────────────────────────────────────

    def _parse_html_results(self, soup: BeautifulSoup,
                            ecfg: dict) -> List[Tuple[str, str, str]]:
        out        = []
        result_sel = ecfg.get("results", "li, .result")
        snip_sel   = ecfg.get("snippet", "p")

        for el in soup.select(result_sel)[:25]:
            a    = el.find("a", href=True)
            snip = el.select_one(snip_sel)
            if not a:
                continue
            href = a["href"].strip()
            if not href.startswith("http"):
                continue
            title   = a.get_text(strip=True)[:100]
            snippet = snip.get_text(strip=True)[:120] if snip else ""
            out.append((href, title, snippet))

        if not out:
            for a in soup.find_all("a", href=True):
                href = a["href"].strip()
                if ".onion" in href and href.startswith("http"):
                    out.append((href, a.get_text(strip=True)[:80], ""))
        return out

    # ── PwnDB direct query ────────────────────────────────────────────────

    async def _run_pwndb(self, query: str, qtype: str):
        self.tui.info("[TOR] PwnDB — direct credential lookup...")
        url = "http://pwndb2am4tzkvold.onion/"

        if qtype == "email":
            idx  = query.find("@")
            data = {
                "luser":    query[:idx] if idx > 0 else query,
                "domain":   query[idx + 1:] if idx > 0 else "",
                "luseropr": "1", "domainopr": "1", "submitform": "em",
            }
        elif qtype == "username":
            data = {"luser": query, "domain": "",
                    "luseropr": "1", "domainopr": "1", "submitform": "em"}
        elif qtype == "domain":
            data = {"luser": "", "domain": query,
                    "luseropr": "1", "domainopr": "1", "submitform": "em"}
        else:
            self.tui.warn("[TOR] PwnDB: supports email/username/domain only")
            return

        resp = await async_post_tor(url, self.tor, data=data, timeout=50)
        if resp is None or resp.status_code != 200:
            self.tui.warn("[TOR] PwnDB: connection failed — is Tor running?")
            return

        soup  = BeautifulSoup(resp.text, "lxml")
        SKIP  = {"login", "luser", "password", "user", "pass", "null", "none", ""}
        count = 0

        for row in soup.find_all("tr"):
            cols = row.find_all("td")
            if len(cols) >= 2:
                user = cols[0].get_text(strip=True)
                pw   = cols[1].get_text(strip=True)
                if user.lower() not in SKIP and pw and pw.lower() not in SKIP:
                    cred  = f"{user}:{pw}"
                    extra = {
                        "source":   "pwndb .onion",
                        "username": user,
                        "password": pw,
                    }
                    if self.store.add("pwndb_onion", qtype, query, cred, extra):
                        self.tui.result_card(
                            self.store.count(), "pwndb_onion", qtype, cred, extra
                        )
                        count += 1

        self.tui.info(f"[TOR] PwnDB — {count} credential entries")

    async def _jitter(self):
        await asyncio.sleep(random.uniform(self.min_d, self.max_d))
