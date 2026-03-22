"""modules/scraper/social.py — GitHub code dorks, Hunter.io, misc social surface"""

import asyncio
import urllib.parse
from bs4 import BeautifulSoup

from modules.utils.http  import async_get, base_headers
from modules.utils.dedup import ResultStore
from modules.utils.tui   import TUI


GITHUB_DORKS = {
    "email":    ["{q} password", "{q} secret", "{q} api_key", "{q} credentials"],
    "username": ["{q} password", "{q} token", "{q} ssh"],
    "password": ['password "{q}"', 'passwd "{q}"'],
    "hash":     ['"{q}"'],
    "domain":   ["{q} credentials", "{q} password", "{q} smtp"],
    "ip":       ['"{q}"', "{q} server"],
    "name":     ['"{q}" email password'],
    "phone":    ['"{q}"'],
}


class SocialModule:
    def __init__(self, cfg, proxy_mgr, store: ResultStore, tui: TUI):
        self.cfg     = cfg
        self.pm      = proxy_mgr
        self.store   = store
        self.tui     = tui
        self.timeout = cfg.get("request_timeout", 25)
        self.max     = cfg.get("max_results_per_source", 50)
        self.keys    = cfg.get("api_keys", {})

    async def run(self, query: str, qtype: str):
        self.tui.section("SOCIAL / CODE RECONNAISSANCE", "🔎")
        tasks = [self._github_dorks(query, qtype)]
        if qtype in ("email", "domain") and self.keys.get("hunter"):
            tasks.append(self._hunter(query, qtype))
        await asyncio.gather(*tasks, return_exceptions=True)

    # ── GitHub code search ─────────────────────────────────────────────────
    async def _github_dorks(self, query: str, qtype: str):
        self.tui.info("GitHub code search — dorking...")
        dorks = [d.replace("{q}", query)
                 for d in GITHUB_DORKS.get(qtype, [f'"{query}"'])][:3]

        gh_headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                          "AppleWebKit/537.36 (KHTML, like Gecko) "
                          "Chrome/121.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        }

        for dork in dorks:
            url  = f"https://github.com/search?q={urllib.parse.quote(dork)}&type=code"
            resp = await async_get(url, headers=gh_headers,
                                   proxy=self.pm.get(), timeout=self.timeout)
            if resp is None:
                continue
            if resp.status_code == 200:
                soup = BeautifulSoup(resp.text, "lxml")
                for r in soup.select(
                    ".code-list-item, [data-testid='results-list'] > div, .search-result"
                )[:8]:
                    a = r.find("a", href=True)
                    snip_el = r.find("p") or r.find(".text-small")
                    if a:
                        href = a["href"]
                        if not href.startswith("http"):
                            href = "https://github.com" + href
                        snip = snip_el.get_text(strip=True)[:100] if snip_el else ""
                        extra = {"dork": dork, "snippet": snip}
                        if self.store.add("github_dork", qtype, query, href, extra):
                            self.tui.result_card(self.store.count(), "github_dork",
                                                 qtype, href, extra)
            await asyncio.sleep(2)

    # ── Hunter.io ─────────────────────────────────────────────────────────
    async def _hunter(self, query: str, qtype: str):
        self.tui.info("Hunter.io — querying...")
        key = self.keys.get("hunter", "")
        if not key:
            self.tui.warn("Hunter.io: no API key — skipping"); return

        if qtype == "email":
            url  = (f"https://api.hunter.io/v2/email-verifier"
                    f"?email={urllib.parse.quote(query)}&api_key={key}")
            resp = await async_get(url, timeout=self.timeout)
            if resp and resp.status_code == 200:
                try:
                    d = resp.json().get("data", {})
                    extra = {"status": d.get("status",""),
                             "deliverable": str(d.get("result","")),
                             "score": str(d.get("score","")),
                             "mx_records": str(d.get("mx_records", False))}
                    val = f"Status: {d.get('status','?')}  Score: {d.get('score','?')}"
                    if self.store.add("hunter", qtype, query, val, extra):
                        self.tui.result_card(self.store.count(), "hunter", qtype, val, extra)
                except Exception: pass

        elif qtype == "domain":
            url  = (f"https://api.hunter.io/v2/domain-search"
                    f"?domain={urllib.parse.quote(query)}&api_key={key}&limit=25")
            resp = await async_get(url, timeout=self.timeout)
            if resp and resp.status_code == 200:
                try:
                    for em in resp.json().get("data", {}).get("emails", [])[:25]:
                        extra = {"type": em.get("type",""),
                                 "confidence": str(em.get("confidence","")),
                                 "name": (f"{em.get('first_name','')} "
                                          f"{em.get('last_name','')}").strip(),
                                 "position": em.get("position","")}
                        val = em.get("value","")
                        if val and self.store.add("hunter", qtype, query, val, extra):
                            self.tui.result_card(self.store.count(), "hunter",
                                                 qtype, val, extra)
                except Exception: pass
