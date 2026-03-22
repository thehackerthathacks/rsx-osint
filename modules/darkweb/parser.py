"""
modules/darkweb/parser.py — Generic page type detection and content extraction.

Handles: forum threads, marketplace listings, paste dumps, index pages.
"""

import re
from typing import Tuple, List, Dict
from bs4 import BeautifulSoup


# ── Heuristics to identify page type ─────────────────────────────────────────
FORUM_SIGNALS     = ["thread", "post", "reply", "forum", "topic", "member",
                      "registered", "joined", "board", "subforum", "quote"]
MARKET_SIGNALS    = ["vendor", "listing", "price", "btc", "xmr", "monero",
                      "bitcoin", "add to cart", "shipping", "escrow", "product"]
PASTE_SIGNALS     = ["paste", "raw", "bin", "dump", "leak", "combo"]
INDEX_SIGNALS     = [".onion", "hidden wiki", "link list", "directory"]


class PageParser:
    def detect_and_parse(self, soup: BeautifulSoup, url: str,
                         query: str) -> Tuple[str, List[Dict]]:
        text_low = soup.get_text().lower()

        score = {
            "forum":     sum(1 for s in FORUM_SIGNALS  if s in text_low),
            "market":    sum(1 for s in MARKET_SIGNALS if s in text_low),
            "paste":     sum(1 for s in PASTE_SIGNALS  if s in text_low),
            "index":     sum(1 for s in INDEX_SIGNALS  if s in text_low),
        }
        page_type = max(score, key=score.get)

        if score[page_type] == 0:
            page_type = "generic"

        parsers = {
            "forum":   self._parse_forum,
            "market":  self._parse_market,
            "paste":   self._parse_paste,
            "index":   self._parse_index,
            "generic": self._parse_generic,
        }
        items = parsers[page_type](soup, url, query)
        return page_type, items

    # ── Forum ─────────────────────────────────────────────────────────────
    def _parse_forum(self, soup: BeautifulSoup, url: str,
                     query: str) -> List[Dict]:
        results = []
        post_selectors = [
            ".post", ".message", ".postbody", "[class*='post']",
            "article", ".content", "blockquote",
            "td.postbody", "td.message",
        ]
        for sel in post_selectors:
            posts = soup.select(sel)
            if posts:
                for post in posts[:20]:
                    text = post.get_text(separator=" ", strip=True)
                    if len(text) < 30:
                        continue
                    # Only include posts mentioning the query
                    if query.lower() in text.lower():
                        author_el = (post.find(class_=re.compile(r"user|author|member|poster")) or
                                     post.find("cite") or post.find("strong"))
                        date_el   = (post.find(class_=re.compile(r"date|time|post-date")) or
                                     post.find("time"))
                        results.append({
                            "content": text[:300],
                            "title":   "Forum post",
                            "author":  author_el.get_text(strip=True)[:40] if author_el else "",
                            "date":    date_el.get_text(strip=True)[:30]   if date_el   else "",
                            "url":     url,
                        })
                break

        # Thread titles
        for a in soup.find_all("a", href=True):
            text = a.get_text(strip=True)
            if query.lower() in text.lower() and len(text) > 10:
                href = a["href"]
                if not href.startswith("http"):
                    continue
                results.append({
                    "content": text[:120],
                    "title":   "Thread link",
                    "url":     href,
                })
        return results

    # ── Marketplace ───────────────────────────────────────────────────────
    def _parse_market(self, soup: BeautifulSoup, url: str,
                      query: str) -> List[Dict]:
        results = []
        listing_sels = [
            ".listing", ".product", ".item", ".card",
            "[class*='listing']", "[class*='product']",
        ]
        for sel in listing_sels:
            for listing in soup.select(sel)[:15]:
                text = listing.get_text(separator=" ", strip=True)
                if query.lower() not in text.lower():
                    continue
                title_el = (listing.find("h1") or listing.find("h2") or
                            listing.find("h3") or listing.find(".title"))
                price_el = listing.find(class_=re.compile(r"price|cost|btc|xmr"))
                vendor_el = listing.find(class_=re.compile(r"vendor|seller|shop"))
                results.append({
                    "content": text[:250],
                    "title":   title_el.get_text(strip=True)[:80]  if title_el  else "Listing",
                    "price":   price_el.get_text(strip=True)[:40]  if price_el  else "",
                    "vendor":  vendor_el.get_text(strip=True)[:40] if vendor_el else "",
                    "url":     url,
                })
        return results

    # ── Paste / dump ──────────────────────────────────────────────────────
    def _parse_paste(self, soup: BeautifulSoup, url: str,
                     query: str) -> List[Dict]:
        results = []
        code_blocks = soup.find_all(["pre", "code", "textarea", ".paste-content",
                                     "#content", ".content"])
        for block in code_blocks[:5]:
            text = block.get_text(separator="\n", strip=True)
            if query.lower() not in text.lower():
                continue
            # Extract lines containing the query
            matching_lines = [l.strip() for l in text.splitlines()
                              if query.lower() in l.lower() and len(l.strip()) > 5]
            for line in matching_lines[:30]:
                results.append({
                    "content":   line[:200],
                    "title":     "Paste content",
                    "context":   f"{len(matching_lines)} matching lines total",
                    "url":       url,
                })
        return results

    # ── Link index / Hidden Wiki ──────────────────────────────────────────
    def _parse_index(self, soup: BeautifulSoup, url: str,
                     query: str) -> List[Dict]:
        results = []
        for a in soup.find_all("a", href=True):
            href = a["href"].strip()
            text = a.get_text(strip=True)
            if not href.startswith("http"):
                continue
            if query.lower() in (text + href).lower():
                parent = a.find_parent(["li", "td", "p", "div"])
                desc   = parent.get_text(strip=True)[:120] if parent else ""
                results.append({
                    "content": href,
                    "title":   text[:80],
                    "description": desc,
                    "url":     href,
                })
        return results

    # ── Generic fallback ─────────────────────────────────────────────────
    def _parse_generic(self, soup: BeautifulSoup, url: str,
                       query: str) -> List[Dict]:
        results = []
        text = soup.get_text(separator="\n")
        for line in text.splitlines():
            line = line.strip()
            if query.lower() in line.lower() and 10 < len(line) < 300:
                results.append({
                    "content": line[:200],
                    "title":   "Page match",
                    "url":     url,
                })
        return results[:20]
