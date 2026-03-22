"""
modules/scraper/recent.py — Recent & latest breach intelligence feed.

Pulls the most recently disclosed public breaches from multiple sources
and displays them regardless of the search query — useful for staying
on top of what just got leaked.

Sources:
  - HaveIBeenPwned  /api/v3/breaches  (full public list, no key needed)
  - BreachDirectory recent feed
  - IntelX latest pastes/dumps
  - LeakIX latest leak events
  - DataBreaches.net scrape (news site)
  - BreachForums latest threads (clearnet mirror)
  - GitHub breach-data topic repositories (recently updated)
"""

import asyncio
import re
import urllib.parse
from datetime import datetime, timezone
from bs4 import BeautifulSoup

from modules.utils.http  import async_get
from modules.utils.dedup import ResultStore
from modules.utils.tui   import TUI


HIBP_BREACHES_URL     = "https://haveibeenpwned.com/api/v3/breaches"
LEAKIX_LATEST_URL     = "https://leakix.net/api/events?page=0&limit=20"
DATABREACHES_URL      = "https://www.databreaches.net/category/breach-reports/"
BREACHFORUMS_URL      = "https://breachforums.st/Forum-Databases-Leaks"
GH_BREACH_SEARCH_URL  = (
    "https://api.github.com/search/repositories"
    "?q=topic:data-breach+topic:leaked&sort=updated&order=desc&per_page=15"
)
REDDIT_NETSEC_URL     = (
    "https://www.reddit.com/r/netsec/search.json"
    "?q=data+breach&sort=new&limit=15&t=week"
)


class RecentBreachModule:
    def __init__(self, cfg: dict, proxy_mgr, store: ResultStore, tui: TUI):
        self.cfg     = cfg
        self.pm      = proxy_mgr
        self.store   = store
        self.tui     = tui
        self.timeout = cfg.get("request_timeout", 25)
        self.max_res = cfg.get("max_results_per_source", 30)

    async def run(self, query: str = "", qtype: str = "recent"):
        self.tui.section("RECENT BREACH INTELLIGENCE FEED", "📡")
        self.tui.info("Fetching latest disclosed breaches across all sources...")

        await asyncio.gather(
            self._hibp_latest(),
            self._leakix_latest(),
            self._databreaches_net(),
            self._breachforums_latest(),
            self._github_breach_repos(),
            self._reddit_netsec(),
            return_exceptions=True,
        )

    # ── HIBP full breach list (sorted by AddedDate desc) ─────────────────
    async def _hibp_latest(self):
        self.tui.info("HIBP — fetching full breach list...")
        resp = await async_get(
            HIBP_BREACHES_URL,
            headers={"User-Agent": "rsx-osint"},
            timeout=self.timeout,
        )
        if resp is None or resp.status_code != 200:
            self.tui.warn(f"HIBP breaches: HTTP {getattr(resp,'status_code','timeout')}")
            return
        try:
            breaches = resp.json()
            # Sort by AddedDate descending — most recent first
            breaches.sort(
                key=lambda b: b.get("AddedDate", ""),
                reverse=True,
            )
            shown = 0
            for b in breaches:
                if shown >= self.max_res:
                    break
                desc  = re.sub(r"<[^>]+>", "", b.get("Description", ""))[:120]
                extra = {
                    "breach date":   b.get("BreachDate", ""),
                    "added to HIBP": b.get("AddedDate", "")[:10],
                    "records":       f"{b.get('PwnCount', 0):,}",
                    "data exposed":  ", ".join(b.get("DataClasses", []))[:100],
                    "verified":      str(b.get("IsVerified", False)),
                    "fabricated":    str(b.get("IsFabricated", False)),
                    "domain":        b.get("Domain", ""),
                    "description":   desc,
                }
                val = f"{b.get('Name','?')}  —  {b.get('BreachDate','?')}"
                if self.store.add("hibp_recent", "recent", "", val, extra):
                    self.tui.result_card(self.store.count(), "hibp_recent",
                                         "recent", val, extra)
                    shown += 1

            self.tui.info(f"HIBP: {len(breaches)} total breaches in DB — showing {shown} latest")
        except Exception as e:
            self.tui.warn(f"HIBP recent: parse error {e}")

    # ── LeakIX latest events ──────────────────────────────────────────────
    async def _leakix_latest(self):
        self.tui.info("LeakIX — fetching latest leak events...")
        key  = self.cfg.get("api_keys", {}).get("leakix", "")
        hdrs = {"Accept": "application/json"}
        if key:
            hdrs["api-key"] = key
        resp = await async_get(LEAKIX_LATEST_URL, headers=hdrs, timeout=self.timeout)
        if resp is None or resp.status_code != 200:
            self.tui.warn(f"LeakIX: HTTP {getattr(resp,'status_code','timeout')}")
            return
        try:
            for item in resp.json()[:self.max_res]:
                extra = {
                    "host":     item.get("host", ""),
                    "summary":  item.get("summary", "")[:120],
                    "severity": item.get("severity", ""),
                    "date":     item.get("time", "")[:10],
                    "tags":     ", ".join(item.get("tags", [])),
                    "plugin":   item.get("event_source", ""),
                }
                val = f"{item.get('event_source','?')}  —  {item.get('host','?')}"
                if self.store.add("leakix_recent", "recent", "", val, extra):
                    self.tui.result_card(self.store.count(), "leakix_recent",
                                         "recent", val, extra)
        except Exception as e:
            self.tui.warn(f"LeakIX recent: {e}")

    # ── DataBreaches.net news scrape ──────────────────────────────────────
    async def _databreaches_net(self):
        self.tui.info("DataBreaches.net — scraping breach news...")
        resp = await async_get(DATABREACHES_URL, timeout=self.timeout)
        if resp is None or resp.status_code != 200:
            self.tui.warn(f"DataBreaches.net: HTTP {getattr(resp,'status_code','timeout')}")
            return
        try:
            soup    = BeautifulSoup(resp.text, "lxml")
            shown   = 0
            # Article listings
            for article in soup.select("article, .post, .entry")[:self.max_res]:
                title_el = (article.find("h2") or article.find("h3")
                            or article.find("h1"))
                date_el  = article.find(class_=re.compile(r"date|time|posted"))
                link_el  = article.find("a", href=True)
                if not title_el:
                    continue
                title = title_el.get_text(strip=True)[:120]
                date  = date_el.get_text(strip=True)[:30] if date_el else ""
                href  = link_el["href"] if link_el else ""
                if not href.startswith("http"):
                    href = "https://www.databreaches.net" + href
                extra = {
                    "title":    title,
                    "date":     date,
                    "source":   "databreaches.net",
                    "url":      href,
                }
                if self.store.add("databreaches_net", "recent", "", title, extra):
                    self.tui.result_card(self.store.count(), "databreaches_net",
                                         "recent", title, extra)
                    shown += 1

            if shown == 0:
                # Fallback: just grab all article links
                for a in soup.find_all("a", href=True)[:30]:
                    text = a.get_text(strip=True)
                    href = a["href"]
                    if (len(text) > 20 and
                            "breach" in text.lower() or "leak" in text.lower() or
                            "hack" in text.lower()):
                        if not href.startswith("http"):
                            href = "https://www.databreaches.net" + href
                        extra = {"title": text[:120], "url": href,
                                 "source": "databreaches.net"}
                        if self.store.add("databreaches_net", "recent", "",
                                          text[:120], extra):
                            self.tui.result_card(self.store.count(),
                                                 "databreaches_net",
                                                 "recent", text[:120], extra)
                            shown += 1
                            if shown >= self.max_res:
                                break
        except Exception as e:
            self.tui.warn(f"DataBreaches.net: {e}")

    # ── BreachForums latest threads (clearnet mirror) ─────────────────────
    async def _breachforums_latest(self):
        self.tui.info("BreachForums — scraping latest database threads...")
        resp = await async_get(
            BREACHFORUMS_URL,
            headers={"User-Agent": "Mozilla/5.0 (X11; Linux x86_64; rv:122.0) Gecko/20100101 Firefox/122.0"},
            timeout=self.timeout,
        )
        if resp is None or resp.status_code != 200:
            self.tui.warn(f"BreachForums: HTTP {getattr(resp,'status_code','timeout')}")
            return
        try:
            soup  = BeautifulSoup(resp.text, "lxml")
            shown = 0
            # Thread rows in forum listing
            for row in soup.select(
                "tr.inline_row, .thread, .subject, [class*='thread']"
            )[:self.max_res]:
                title_el = (row.find("a", class_=re.compile(r"subject|title|thread"))
                            or row.find("a", href=re.compile(r"thread|showthread")))
                if not title_el:
                    continue
                title = title_el.get_text(strip=True)[:120]
                href  = title_el.get("href", "")
                if not href.startswith("http"):
                    href = "https://breachforums.st" + href

                date_el  = row.find(class_=re.compile(r"date|time|lastpost"))
                author_el = row.find(class_=re.compile(r"author|user|poster"))
                extra = {
                    "title":  title,
                    "url":    href,
                    "date":   date_el.get_text(strip=True)[:30]   if date_el   else "",
                    "author": author_el.get_text(strip=True)[:40] if author_el else "",
                    "source": "breachforums.st",
                }
                if self.store.add("breachforums", "recent", "", title, extra):
                    self.tui.result_card(self.store.count(), "breachforums",
                                         "recent", title, extra)
                    shown += 1

            self.tui.info(f"BreachForums: {shown} threads found")
        except Exception as e:
            self.tui.warn(f"BreachForums: {e}")

    # ── GitHub breach repos (recently updated) ────────────────────────────
    async def _github_breach_repos(self):
        self.tui.info("GitHub — searching recently updated breach/leak repos...")
        resp = await async_get(
            GH_BREACH_SEARCH_URL,
            headers={"Accept": "application/vnd.github.v3+json",
                     "User-Agent": "rsx-osint"},
            timeout=self.timeout,
        )
        if resp is None or resp.status_code != 200:
            self.tui.warn(f"GitHub: HTTP {getattr(resp,'status_code','timeout')}")
            return
        try:
            items = resp.json().get("items", [])
            for repo in items[:self.max_res]:
                extra = {
                    "repo":        repo.get("full_name", ""),
                    "description": (repo.get("description") or "")[:100],
                    "stars":       str(repo.get("stargazers_count", 0)),
                    "updated":     repo.get("updated_at", "")[:10],
                    "url":         repo.get("html_url", ""),
                    "topics":      ", ".join(repo.get("topics", [])),
                }
                val = repo.get("full_name", "?")
                if self.store.add("github_breach_repo", "recent", "", val, extra):
                    self.tui.result_card(self.store.count(), "github_breach_repo",
                                         "recent", val, extra)
        except Exception as e:
            self.tui.warn(f"GitHub breach repos: {e}")

    # ── Reddit r/netsec recent breach posts ───────────────────────────────
    async def _reddit_netsec(self):
        self.tui.info("Reddit r/netsec — scanning recent breach posts...")
        resp = await async_get(
            REDDIT_NETSEC_URL,
            headers={"User-Agent": "rsx-osint/2.0"},
            timeout=self.timeout,
        )
        if resp is None or resp.status_code != 200:
            self.tui.warn(f"Reddit: HTTP {getattr(resp,'status_code','timeout')}")
            return
        try:
            posts = resp.json().get("data", {}).get("children", [])
            for post in posts[:self.max_res]:
                d     = post.get("data", {})
                title = d.get("title", "")[:120]
                url   = d.get("url", "")
                score = d.get("score", 0)
                date  = datetime.fromtimestamp(
                    d.get("created_utc", 0), tz=timezone.utc
                ).strftime("%Y-%m-%d")
                extra = {
                    "title":  title,
                    "url":    url,
                    "date":   date,
                    "score":  str(score),
                    "reddit": f"https://reddit.com{d.get('permalink','')}",
                }
                if self.store.add("reddit_netsec", "recent", "", title, extra):
                    self.tui.result_card(self.store.count(), "reddit_netsec",
                                         "recent", title, extra)
        except Exception as e:
            self.tui.warn(f"Reddit: {e}")
