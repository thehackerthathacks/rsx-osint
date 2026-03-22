"""modules/scraper/breach.py — Breach database lookup module"""

import asyncio
import hashlib
import re
import urllib.parse
from typing import Optional

from modules.utils.http  import async_get, base_headers
from modules.utils.dedup import ResultStore
from modules.utils.tui   import TUI


class BreachModule:
    def __init__(self, cfg: dict, proxy_mgr, store: ResultStore, tui: TUI):
        self.cfg     = cfg
        self.pm      = proxy_mgr
        self.store   = store
        self.tui     = tui
        self.keys    = cfg.get("api_keys", {})
        self.enabled = cfg.get("enabled_breach_sources", [])
        self.timeout = cfg.get("request_timeout", 25)
        self.max_res = cfg.get("max_results_per_source", 50)

    async def run(self, query: str, qtype: str):
        self.tui.section("BREACH DATABASE RECONNAISSANCE", "🔓")
        e = self.enabled
        tasks = []

        if "haveibeenpwned" in e:
            tasks.append(self._hibp(query, qtype))
        if "breachdirectory" in e and qtype in ("email","username","password","hash"):
            tasks.append(self._breachdirectory(query, qtype))
        if "proxynova" in e and qtype in ("email","username","password"):
            tasks.append(self._proxynova(query, qtype))
        if "leakcheck" in e and qtype in ("email","username","password","hash"):
            tasks.append(self._leakcheck(query, qtype))
        if "ghostproject" in e and qtype in ("email","username"):
            tasks.append(self._ghostproject(query, qtype))
        if "snusbase" in e and qtype in ("email","username","password","hash"):
            tasks.append(self._snusbase(query, qtype))
        if "intelx" in e:
            tasks.append(self._intelx(query, qtype))
        if "leakix" in e and qtype in ("email","domain","ip","username"):
            tasks.append(self._leakix(query, qtype))
        if "emailrep" in e and qtype == "email":
            tasks.append(self._emailrep(query))
        if "whatsmyname" in e and qtype == "username":
            tasks.append(self._whatsmyname(query))
        if "shodan" in e and qtype == "ip":
            tasks.append(self._shodan(query))
        if "virustotal" in e and qtype in ("ip","domain","hash"):
            tasks.append(self._virustotal(query, qtype))
        if "urlscan" in e and qtype in ("domain","ip","email"):
            tasks.append(self._urlscan(query, qtype))
        if "crtsh" in e and qtype in ("domain","email"):
            tasks.append(self._crtsh(query, qtype))
        if "numverify" in e and qtype == "phone":
            tasks.append(self._numverify(query))

        await asyncio.gather(*tasks, return_exceptions=True)

    # ── HaveIBeenPwned ────────────────────────────────────────────────────
    async def _hibp(self, query: str, qtype: str):
        self.tui.info("HIBP — probing...")
        key = self.keys.get("hibp", "")

        if qtype == "email":
            url  = (f"https://haveibeenpwned.com/api/v3/breachedaccount/"
                    f"{urllib.parse.quote(query)}?truncateResponse=false")
            hdrs = {"hibp-api-key": key, "User-Agent": "rsx-osint"} if key \
                   else {"User-Agent": "rsx-osint"}
            resp = await async_get(url, headers=hdrs, timeout=self.timeout)
            if resp is None:
                self.tui.warn("HIBP: no response"); return
            if resp.status_code == 200:
                try:
                    for b in resp.json():
                        desc  = re.sub(r"<[^>]+>", "", b.get("Description", ""))[:100]
                        extra = {
                            "breach name":   b.get("Name", ""),
                            "breach date":   b.get("BreachDate", ""),
                            "records":       f"{b.get('PwnCount', 0):,}",
                            "data exposed":  ", ".join(b.get("DataClasses", []))[:80],
                            "verified":      str(b.get("IsVerified", False)),
                            "description":   desc,
                        }
                        val = f"{b.get('Name')} — {b.get('BreachDate','?')}"
                        if self.store.add("haveibeenpwned", qtype, query, val, extra):
                            self.tui.result_card(self.store.count(), "haveibeenpwned",
                                                 qtype, val, extra)
                except Exception: pass
            elif resp.status_code == 401:
                self.tui.warn("HIBP: API key required — using public fallback")
                await self._hibp_public(query, qtype)
            elif resp.status_code == 404:
                self.tui.info("HIBP: email not found in any known breach")
            elif resp.status_code == 429:
                self.tui.warn("HIBP: rate limited")

        elif qtype in ("password", "hash"):
            raw  = qtype == "hash" and len(query) == 40 and \
                   all(c in "0123456789abcdefABCDEF" for c in query)
            sha1 = query.upper() if raw else hashlib.sha1(query.encode()).hexdigest().upper()
            prefix, suffix = sha1[:5], sha1[5:]
            resp = await async_get(f"https://api.pwnedpasswords.com/range/{prefix}",
                                   timeout=self.timeout)
            if resp and resp.status_code == 200:
                for line in resp.text.splitlines():
                    h, cnt = line.split(":")
                    if h == suffix:
                        sev   = "CRITICAL" if int(cnt) > 10000 else \
                                "HIGH"     if int(cnt) > 1000  else "MEDIUM"
                        extra = {"severity": sev, "method": "k-anonymity SHA1 range",
                                 "occurrences": f"{int(cnt):,}"}
                        val   = f"Found in {int(cnt):,} breach records"
                        if self.store.add("haveibeenpwned", qtype, query, val, extra):
                            self.tui.result_card(self.store.count(), "haveibeenpwned",
                                                 qtype, val, extra)
                        return
                self.tui.info("HIBP: not found in password corpus")

    async def _hibp_public(self, query: str, qtype: str):
        resp = await async_get(
            f"https://haveibeenpwned.com/unifiedsearch/{urllib.parse.quote(query)}",
            timeout=self.timeout,
        )
        if resp and resp.status_code == 200:
            try:
                for b in resp.json().get("Breaches", []):
                    extra = {"data": ", ".join(b.get("DataClasses", []))[:80],
                             "date": b.get("BreachDate", "")}
                    val   = f"{b.get('Name')} ({b.get('BreachDate','?')})"
                    if self.store.add("haveibeenpwned", qtype, query, val, extra):
                        self.tui.result_card(self.store.count(), "haveibeenpwned",
                                             qtype, val, extra)
            except Exception: pass

    # ── BreachDirectory ───────────────────────────────────────────────────
    async def _breachdirectory(self, query: str, qtype: str):
        self.tui.info("BreachDirectory — querying...")
        key  = self.keys.get("breachdirectory", "")
        url  = f"https://breachdirectory.org/api?func=auto&term={urllib.parse.quote(query)}"
        hdrs = {"x-api-key": key} if key else {}
        resp = await async_get(url, headers=hdrs, timeout=self.timeout)
        if resp is None:
            self.tui.warn("BreachDirectory: no response"); return
        if resp.status_code == 200:
            try:
                data = resp.json()
                if data.get("found"):
                    for r in data.get("result", [])[:self.max_res]:
                        pw    = r.get("password") or "(hashed only)"
                        extra = {
                            "password":      pw,
                            "breach source": r.get("sources", ""),
                            "sha1":          r.get("sha1", ""),
                            "plaintext":     str(bool(r.get("password"))),
                        }
                        if self.store.add("breachdirectory", qtype, query, pw, extra):
                            self.tui.result_card(self.store.count(), "breachdirectory",
                                                 qtype, pw, extra)
                else:
                    self.tui.info("BreachDirectory: not found")
            except Exception: pass
        elif resp.status_code == 429:
            self.tui.warn("BreachDirectory: rate limited")

    # ── ProxyNova COMB ────────────────────────────────────────────────────
    async def _proxynova(self, query: str, qtype: str):
        self.tui.info("ProxyNova COMB — searching...")
        q_lower = query.lower()
        matched = 0
        start   = 0
        limit   = 100

        while matched < self.max_res:
            url  = (f"https://api.proxynova.com/comb"
                    f"?query={urllib.parse.quote(query)}&start={start}&limit={limit}")
            resp = await async_get(url, timeout=self.timeout)
            if resp is None or resp.status_code != 200:
                break
            try:
                data  = resp.json()
                lines = data.get("lines", [])
                total = data.get("count", 0)
                if not lines:
                    break

                if start == 0:
                    self.tui.info(
                        f"ProxyNova: {total:,} raw entries — "
                        f"filtering exact matches for '{query}'"
                    )

                for raw_line in lines:
                    raw_line = raw_line.strip()
                    if not raw_line:
                        continue
                    # Strict: only lines that contain the exact query string
                    if q_lower not in raw_line.lower():
                        continue
                    u, _, p = raw_line.partition(":")
                    u = u.strip()
                    p = p.strip()
                    extra = {
                        "email / user": u,
                        "password":     p if p else "(empty)",
                        "source":       "COMB — Collection Of Many Breaches",
                    }
                    if self.store.add("proxynova", qtype, query, raw_line, extra):
                        self.tui.result_card(self.store.count(), "proxynova",
                                             qtype, raw_line, extra)
                        matched += 1

                if len(lines) < limit:
                    break
                start += limit

            except Exception:
                break

        if matched == 0:
            self.tui.info("ProxyNova: no exact matches found")

    # ── LeakCheck ─────────────────────────────────────────────────────────
    async def _leakcheck(self, query: str, qtype: str):
        self.tui.info("LeakCheck — querying...")
        url  = f"https://leakcheck.io/api/public?check={urllib.parse.quote(query)}"
        resp = await async_get(url, timeout=self.timeout)
        if resp and resp.status_code == 200:
            try:
                data = resp.json()
                if data.get("found"):
                    for src in data.get("sources", []):
                        extra = {
                            "breach name": src.get("name", ""),
                            "breach date": src.get("date", ""),
                            "records":     str(src.get("entries", "")),
                        }
                        val = src.get("name", "Unknown breach")
                        if self.store.add("leakcheck", qtype, query, val, extra):
                            self.tui.result_card(self.store.count(), "leakcheck",
                                                 qtype, val, extra)
                else:
                    self.tui.info("LeakCheck: not found")
            except Exception: pass
        else:
            self.tui.warn(f"LeakCheck: HTTP {resp.status_code if resp else 'timeout'}")

    # ── GhostProject ──────────────────────────────────────────────────────
    async def _ghostproject(self, query: str, qtype: str):
        self.tui.info("GhostProject — scraping...")
        q_lower = query.lower()
        from bs4 import BeautifulSoup
        url  = f"https://ghostproject.fr/?s={urllib.parse.quote(query)}"
        resp = await async_get(url, timeout=self.timeout)
        if resp and resp.status_code == 200:
            soup = BeautifulSoup(resp.text, "lxml")
            for row in soup.select("table tr")[1:51]:
                cols = row.find_all("td")
                if len(cols) < 2:
                    continue
                user = cols[0].get_text(strip=True)
                pw   = cols[1].get_text(strip=True)
                if not user or q_lower not in user.lower():
                    continue
                cred  = f"{user}:{pw}"
                extra = {"email / user": user, "password": pw}
                if self.store.add("ghostproject", qtype, query, cred, extra):
                    self.tui.result_card(self.store.count(), "ghostproject",
                                         qtype, cred, extra)

    # ── Snusbase ──────────────────────────────────────────────────────────
    async def _snusbase(self, query: str, qtype: str):
        self.tui.info("Snusbase — querying...")
        key = self.keys.get("snusbase", "")
        if not key:
            self.tui.warn("Snusbase: API key not set — skipping"); return
        import aiohttp
        q_lower = query.lower()
        stype   = qtype if qtype != "hash" else "hash"
        payload = {"terms": [query], "types": [stype]}
        try:
            async with aiohttp.ClientSession(
                headers={"Auth": key, "Content-Type": "application/json"}
            ) as s:
                async with s.post("https://api.snusbase.com/data/search",
                                  json=payload, ssl=False,
                                  timeout=aiohttp.ClientTimeout(total=self.timeout)) as r:
                    if r.status == 200:
                        data = await r.json()
                        for db, entries in data.get("results", {}).items():
                            for entry in entries[:self.max_res]:
                                user = entry.get("email") or entry.get("username") or ""
                                if q_lower not in user.lower():
                                    continue
                                pw    = entry.get("password", "")
                                extra = {
                                    "email / user": user,
                                    "password":     pw if pw else "(not available)",
                                    "hash":         entry.get("hash", ""),
                                    "database":     db,
                                    "ip":           entry.get("ip", ""),
                                }
                                val = f"{user}:{pw}" if pw else user
                                if self.store.add("snusbase", qtype, query, val, extra):
                                    self.tui.result_card(self.store.count(), "snusbase",
                                                         qtype, val, extra)
        except Exception as e:
            self.tui.warn(f"Snusbase: {e}")

    # ── IntelX ────────────────────────────────────────────────────────────
    async def _intelx(self, query: str, qtype: str):
        self.tui.info("IntelX — querying...")
        import aiohttp
        base = "https://2.intelx.io"
        key  = self.keys.get("intelx", "")
        hdrs = {"x-key": key} if key else {}
        payload = {"term": query, "maxresults": 20, "media": 0,
                   "sort": 4, "terminate": []}
        try:
            async with aiohttp.ClientSession(headers=hdrs) as s:
                async with s.post(f"{base}/intelligent/search", json=payload,
                                  ssl=False,
                                  timeout=aiohttp.ClientTimeout(total=15)) as r:
                    if r.status == 200:
                        sid = (await r.json()).get("id")
                        if sid:
                            await asyncio.sleep(3)
                            async with s.get(
                                f"{base}/intelligent/search/result"
                                f"?id={sid}&limit=20&offset=0",
                                ssl=False,
                            ) as r2:
                                if r2.status == 200:
                                    for rec in (await r2.json()).get("records", []):
                                        extra = {
                                            "date":   rec.get("date", "")[:10],
                                            "bucket": rec.get("bucket", ""),
                                            "size":   str(rec.get("size", "")),
                                        }
                                        val = rec.get("name", "record")
                                        if self.store.add("intelx", qtype, query,
                                                          val, extra):
                                            self.tui.result_card(
                                                self.store.count(), "intelx",
                                                qtype, val, extra,
                                            )
        except Exception as e:
            self.tui.warn(f"IntelX: {e}")

    # ── LeakIX ────────────────────────────────────────────────────────────
    async def _leakix(self, query: str, qtype: str):
        self.tui.info("LeakIX — querying...")
        key  = self.keys.get("leakix", "")
        hdrs = {"Accept": "application/json"}
        if key:
            hdrs["api-key"] = key
        url  = (f"https://leakix.net/search"
                f"?scope=leak&q={urllib.parse.quote(query)}&page=0")
        resp = await async_get(url, headers=hdrs, timeout=self.timeout)
        if resp and resp.status_code == 200:
            try:
                for item in resp.json()[:15]:
                    extra = {
                        "summary":  item.get("summary", "")[:100],
                        "host":     item.get("host", ""),
                        "date":     item.get("time", "")[:10],
                        "severity": item.get("severity", ""),
                    }
                    val = item.get("event_source", "leak entry")
                    if self.store.add("leakix", qtype, query, val, extra):
                        self.tui.result_card(self.store.count(), "leakix",
                                             qtype, val, extra)
            except Exception: pass

    # ── EmailRep ──────────────────────────────────────────────────────────
    async def _emailrep(self, query: str):
        self.tui.info("EmailRep — querying...")
        resp = await async_get(
            f"https://emailrep.io/{urllib.parse.quote(query)}",
            headers={"User-Agent": "rsx-osint"},
            timeout=self.timeout,
        )
        if resp and resp.status_code == 200:
            try:
                d     = resp.json()
                flags = d.get("details", {})
                extra = {
                    "reputation":        d.get("reputation", "?").upper(),
                    "suspicious":        str(d.get("suspicious", False)),
                    "blacklisted":       str(flags.get("blacklisted", False)),
                    "malicious activity":str(flags.get("malicious_activity", False)),
                    "data breach":       str(flags.get("data_breach", False)),
                    "spam":              str(flags.get("spam", False)),
                    "profiles":          ", ".join(flags.get("profiles", [])),
                    "first seen":        flags.get("first_seen", ""),
                    "last seen":         flags.get("last_seen", ""),
                }
                val = (f"Reputation: {d.get('reputation','?').upper()}  |  "
                       f"Suspicious: {d.get('suspicious', False)}")
                if self.store.add("emailrep", "email", query, val, extra):
                    self.tui.result_card(self.store.count(), "emailrep",
                                         "email", val, extra)
            except Exception: pass

    # ── WhatsMyName ───────────────────────────────────────────────────────
    async def _whatsmyname(self, query: str):
        self.tui.info("WhatsMyName — checking 150+ platforms...")
        resp = await async_get(
            "https://raw.githubusercontent.com/WebBreacher/WhatsMyName/main/wmn-data.json",
            timeout=30,
        )
        if resp is None or resp.status_code != 200:
            self.tui.warn("WhatsMyName: could not fetch site DB"); return
        try:
            sites = resp.json().get("sites", [])
        except Exception:
            return

        sem   = asyncio.Semaphore(30)

        async def check(site):
            uri = site.get("uri_check", "").replace(
                "{account}", urllib.parse.quote(query)
            )
            if not uri:
                return
            async with sem:
                r = await async_get(uri, timeout=8, retries=0)
            if r is None:
                return
            estring = site.get("e_string", "")
            ecode   = site.get("e_code", 200)
            if r.status_code == ecode and (not estring or estring in r.text):
                extra = {
                    "platform": site.get("name", "?"),
                    "category": site.get("cat", ""),
                    "url":      uri,
                }
                if self.store.add("whatsmyname", "username", query, uri, extra):
                    self.tui.result_card(self.store.count(), "whatsmyname",
                                         "username", uri, extra)

        await asyncio.gather(*[check(s) for s in sites[:200]],
                             return_exceptions=True)

    # ── Shodan InternetDB ─────────────────────────────────────────────────
    async def _shodan(self, query: str):
        self.tui.info("Shodan InternetDB — querying...")
        resp = await async_get(
            f"https://internetdb.shodan.io/{urllib.parse.quote(query)}",
            timeout=self.timeout,
        )
        if resp and resp.status_code == 200:
            try:
                d     = resp.json()
                ports = ", ".join(str(p) for p in d.get("ports", []))
                extra = {
                    "open ports": ports or "none",
                    "hostnames":  ", ".join(d.get("hostnames", [])),
                    "cves":       ", ".join(d.get("vulns", [])),
                    "tags":       ", ".join(d.get("tags", [])),
                    "cpes":       ", ".join(d.get("cpes", [])[:3]),
                }
                val = f"Open ports: {ports or 'none'}"
                if self.store.add("shodan", "ip", query, val, extra):
                    self.tui.result_card(self.store.count(), "shodan",
                                         "ip", val, extra)
            except Exception: pass

    # ── VirusTotal ────────────────────────────────────────────────────────
    async def _virustotal(self, query: str, qtype: str):
        self.tui.info("VirusTotal — querying...")
        key = self.keys.get("virustotal", "")
        if not key:
            self.tui.warn("VirusTotal: API key not set — skipping"); return
        ep  = {"ip": "ip_addresses", "domain": "domains",
               "hash": "files"}.get(qtype)
        if not ep:
            return
        url  = (f"https://www.virustotal.com/api/v3/{ep}/"
                f"{urllib.parse.quote(query)}")
        resp = await async_get(url, headers={"x-apikey": key},
                               timeout=self.timeout)
        if resp and resp.status_code == 200:
            try:
                attr  = resp.json().get("data", {}).get("attributes", {})
                stats = attr.get("last_analysis_stats", {})
                extra = {
                    "malicious": str(stats.get("malicious", 0)),
                    "total engines": str(sum(stats.values())),
                    "reputation": str(attr.get("reputation", "")),
                    "country":   attr.get("country", ""),
                    "as_owner":  attr.get("as_owner", ""),
                    "tags":      ", ".join(attr.get("tags", [])),
                }
                val = (f"Malicious: {stats.get('malicious',0)}"
                       f"/{sum(stats.values())} engines")
                if self.store.add("virustotal", qtype, query, val, extra):
                    self.tui.result_card(self.store.count(), "virustotal",
                                         qtype, val, extra)
            except Exception: pass

    # ── URLScan ───────────────────────────────────────────────────────────
    async def _urlscan(self, query: str, qtype: str):
        self.tui.info("URLScan.io — querying...")
        url  = (f"https://urlscan.io/api/v1/search/"
                f"?q={urllib.parse.quote(query)}&size=10")
        resp = await async_get(url, timeout=self.timeout)
        if resp and resp.status_code == 200:
            try:
                for r in resp.json().get("results", [])[:10]:
                    page  = r.get("page", {})
                    extra = {
                        "url":       page.get("url", ""),
                        "ip":        page.get("ip", ""),
                        "country":   page.get("country", ""),
                        "server":    page.get("server", ""),
                        "scan date": r.get("task", {}).get("time", "")[:10],
                    }
                    val = page.get("url", "")
                    if val and self.store.add("urlscan", qtype, query, val, extra):
                        self.tui.result_card(self.store.count(), "urlscan",
                                             qtype, val, extra)
            except Exception: pass

    # ── crt.sh ────────────────────────────────────────────────────────────
    async def _crtsh(self, query: str, qtype: str):
        self.tui.info("crt.sh — certificate transparency...")
        url  = f"https://crt.sh/?q={urllib.parse.quote(query)}&output=json"
        resp = await async_get(url, timeout=self.timeout)
        if resp and resp.status_code == 200:
            try:
                seen = set()
                for cert in resp.json()[:30]:
                    name = (cert.get("common_name", "")
                            or cert.get("name_value", ""))
                    for n in name.split("\n"):
                        n = n.strip()
                        if n and n not in seen:
                            seen.add(n)
                            extra = {
                                "issuer":      cert.get("issuer_name", "")[:60],
                                "valid from":  cert.get("not_before", "")[:10],
                                "valid until": cert.get("not_after", "")[:10],
                            }
                            if self.store.add("crt_sh", qtype, query, n, extra):
                                self.tui.result_card(self.store.count(), "crt_sh",
                                                     qtype, n, extra)
            except Exception: pass

    # ── NumVerify ─────────────────────────────────────────────────────────
    async def _numverify(self, query: str):
        self.tui.info("Phone validation — querying...")
        import re as _re
        phone = _re.sub(r"[^\d+]", "", query)
        key   = self.keys.get("numverify", "")
        url   = (f"http://apilayer.net/api/validate"
                 f"?access_key={key}&number={phone}&format=1") if key \
                else (f"https://phonevalidation.abstractapi.com/v1/"
                      f"?api_key=free&phone={phone}")
        resp  = await async_get(url, timeout=self.timeout)
        if resp and resp.status_code == 200:
            try:
                d     = resp.json()
                extra = {
                    "valid":     str(d.get("valid", "")),
                    "country":   d.get("country_name", "") or d.get("country", ""),
                    "location":  d.get("location", ""),
                    "line type": d.get("line_type", "") or d.get("type", ""),
                    "carrier":   d.get("carrier", ""),
                }
                val = f"{phone}  —  {d.get('carrier', '?')}"
                if self.store.add("numverify", "phone", query, val, extra):
                    self.tui.result_card(self.store.count(), "numverify",
                                         "phone", val, extra)
            except Exception: pass
