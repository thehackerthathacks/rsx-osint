"""modules/darkweb/engines.py — Dark web search engine scrapers via Tor (paginated)"""

import asyncio
import random
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
        "url":  "https://darksearch.io/api/search?query={q}&page={p}",
        "api":  True,
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
        "url":    "http://pwndb2am4tzkvold.onion/",
        "special": "pwndb",
    },
}


class DarkWebEngine:
    def __init__(self, cfg: dict, tor_proxy: str, store: ResultStore, tui: TUI):
        self.cfg      = cfg
        self.tor      = tor_proxy
        self.store    = store
        self.tui      = tui
        self.enabled  = cfg.get("enabled_dark_engines", list(DARK_ENGINES.keys()))
        self.max_pages = cfg.get("dark_crawl_pages", 5)
        self.timeout  = cfg.get("dark_timeout", 40)
        self.min_d    = cfg.get("dark_min_delay", 2.0)
        self.max_d    = cfg.get("dark_max_delay", 7.0)
        self.max_res  = cfg.get("max_results_per_source", 50)

    async def run(self, query: str, qtype: str):
        self.tui.dark_section("DARK WEB SEARCH ENGINES")
        tasks = []
        for name, cfg in DARK_ENGINES.items():
            if name not in self.enabled:
                continue
            if cfg.get("special") == "pwndb":
                tasks.append(self._run_pwndb(query, qtype))
            elif cfg.get("api"):
                tasks.append(self._run_api_engine(name, cfg, query, qtype))
            else:
                tasks.append(self._run_html_engine(name, cfg, query, qtype))
        await asyncio.gather(*tasks, return_exceptions=True)

    # ── Generic HTML engine ───────────────────────────────────────────────
    async def _run_html_engine(self, name: str, ecfg: dict, query: str, qtype: str):
        self.tui.info(f"[TOR] {name} — searching (up to {self.max_pages} pages)...")
        q        = urllib.parse.quote(query)
        max_p    = min(ecfg.get("pages", 3), self.max_pages)
        found    = 0
        base_url = ecfg.get("onion", ecfg.get("url", ""))
        mul      = ecfg.get("page_multiplier", 1)

        for page in range(max_p):
            page_val = page * mul
            url = base_url.replace("{q}", q).replace("{p}", str(page_val))
            resp = await async_get_tor(url, self.tor, timeout=self.timeout)

            if resp is None:
                self.tui.warn(f"[TOR] {name} p{page+1}: no response"); break
            if resp.status_code != 200:
                self.tui.warn(f"[TOR] {name} p{page+1}: HTTP {resp.status_code}"); break

            soup    = BeautifulSoup(resp.text, "lxml")
            results = self._parse_html_results(soup, ecfg, name)

            if not results:
                break  # no more pages

            for href, title, snippet in results:
                if not href or found >= self.max_res:
                    break
                extra = {"engine": name, "title": title[:80],
                         "snippet": snippet[:120], "page": str(page + 1)}
                if self.store.add(name, qtype, query, href, extra):
                    self.tui.result_card(self.store.count(), name, qtype, href, extra)
                    found += 1

            await self._jitter()

        self.tui.info(f"[TOR] {name} — {found} results collected")

    def _parse_html_results(self, soup: BeautifulSoup,
                            ecfg: dict, name: str) -> List[Tuple[str, str, str]]:
        out = []
        result_sel  = ecfg.get("results",  "li, .result")
        snippet_sel = ecfg.get("snippet",  "p")

        for el in soup.select(result_sel)[:20]:
            a    = el.find("a", href=True)
            snip = el.select_one(snippet_sel)
            if not a:
                continue
            href = a["href"].strip()
            if not href.startswith("http"):
                continue
            title   = a.get_text(strip=True)[:100]
            snippet = snip.get_text(strip=True)[:120] if snip else ""
            out.append((href, title, snippet))

        # Fallback: grab any .onion links on the page
        if not out:
            for a in soup.find_all("a", href=True):
                href = a["href"].strip()
                if ".onion" in href and href.startswith("http"):
                    title = a.get_text(strip=True)[:80]
                    out.append((href, title, ""))
        return out

    # ── DarkSearch JSON API ───────────────────────────────────────────────
    async def _run_api_engine(self, name: str, ecfg: dict, query: str, qtype: str):
        self.tui.info(f"[TOR] {name} API — searching ({self.max_pages} pages)...")
        q     = urllib.parse.quote(query)
        found = 0

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
                    href    = item.get("link", item.get("url", ""))
                    title   = item.get("title", "")[:80]
                    snippet = item.get("description", item.get("snippet", ""))[:120]
                    if not href:
                        continue
                    extra = {"engine": name, "title": title, "snippet": snippet,
                             "page": str(page)}
                    if self.store.add(name, qtype, query, href, extra):
                        self.tui.result_card(self.store.count(), name, qtype, href, extra)
                        found += 1
            except Exception:
                break
            await self._jitter()

        self.tui.info(f"[TOR] {name} — {found} results")

    # ── PwnDB special handler ─────────────────────────────────────────────
    async def _run_pwndb(self, query: str, qtype: str):
        self.tui.info("[TOR] PwnDB — connecting to hidden service...")
        url = "http://pwndb2am4tzkvold.onion/"

        if qtype == "email":
            idx  = query.find("@")
            data = {
                "luser":    query[:idx] if idx > 0 else query,
                "domain":   query[idx+1:] if idx > 0 else "",
                "luseropr": "1", "domainopr": "1", "submitform": "em",
            }
        elif qtype == "username":
            data = {"luser": query, "domain": "",
                    "luseropr": "1", "domainopr": "1", "submitform": "em"}
        elif qtype == "domain":
            data = {"luser": "", "domain": query,
                    "luseropr": "1", "domainopr": "1", "submitform": "em"}
        else:
            self.tui.warn("[TOR] PwnDB: only supports email/username/domain"); return

        resp = await async_post_tor(url, self.tor, data=data, timeout=50)
        if resp is None or resp.status_code != 200:
            self.tui.warn("[TOR] PwnDB: connection failed — is Tor running?"); return

        soup  = BeautifulSoup(resp.text, "lxml")
        count = 0
        SKIP  = {"login", "luser", "password", "user", "pass", "null", "none", ""}

        for row in soup.find_all("tr"):
            cols = row.find_all("td")
            if len(cols) >= 2:
                user = cols[0].get_text(strip=True).lower()
                pw   = cols[1].get_text(strip=True)
                if user not in SKIP and pw and pw.lower() not in SKIP:
                    cred  = f"{cols[0].get_text(strip=True)}:{pw}"
                    extra = {"source": "pwndb .onion hidden service",
                             "username": cols[0].get_text(strip=True),
                             "password": pw}
                    if self.store.add("pwndb", qtype, query, cred, extra):
                        self.tui.result_card(self.store.count(), "pwndb_onion",
                                             qtype, cred, extra)
                        count += 1

        self.tui.info(f"[TOR] PwnDB — {count} credential entries found")

    async def _jitter(self):
        await asyncio.sleep(random.uniform(self.min_d, self.max_d))
