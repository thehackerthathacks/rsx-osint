"""modules/utils/http.py — Shared HTTP helpers with UA rotation and retry"""

import asyncio
import random
import os
import time
import aiohttp
import requests
import urllib3
from typing import Optional

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

_UA_LIST = []


def _load_uas():
    global _UA_LIST
    path = "config/useragents.txt"
    if os.path.exists(path):
        with open(path) as f:
            _UA_LIST = [l.strip() for l in f if l.strip() and not l.startswith("#")]
    if not _UA_LIST:
        _UA_LIST = [
            "Mozilla/5.0 (X11; Linux x86_64; rv:122.0) Gecko/20100101 Firefox/122.0",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/121.0.0.0 Safari/537.36",
        ]


def random_ua() -> str:
    if not _UA_LIST:
        _load_uas()
    return random.choice(_UA_LIST)


def base_headers() -> dict:
    return {
        "User-Agent":      random_ua(),
        "Accept":          "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
        "Accept-Encoding": "gzip, deflate",
        "DNT":             "1",
    }


async def async_get(url: str, proxy: Optional[str] = None,
                    timeout: int = 20, headers: dict = None,
                    retries: int = 2) -> Optional[aiohttp.ClientResponse]:
    hdrs = base_headers()
    if headers:
        hdrs.update(headers)
    connector_kwargs = {}
    if url.startswith("http://") and ".onion" in url:
        pass
    for attempt in range(retries + 1):
        try:
            conn = aiohttp.TCPConnector(ssl=False)
            timeout_obj = aiohttp.ClientTimeout(total=timeout)
            async with aiohttp.ClientSession(
                connector=conn, timeout=timeout_obj, headers=hdrs
            ) as session:
                kwargs = {"allow_redirects": True}
                if proxy:
                    kwargs["proxy"] = proxy
                async with session.get(url, **kwargs) as resp:
                    text = await resp.text(errors="replace")
                    return _FakeResponse(resp.status, text, str(resp.url))
        except asyncio.TimeoutError:
            if attempt == retries:
                return None
            await asyncio.sleep(1)
        except Exception:
            if attempt == retries:
                return None
            await asyncio.sleep(1)
    return None


async def async_get_tor(url: str, tor_proxy: str, timeout: int = 40,
                        headers: dict = None, retries: int = 2) -> Optional["_FakeResponse"]:
    hdrs = base_headers()
    if headers:
        hdrs.update(headers)
    socks_url = f"socks5h://{tor_proxy}"
    for attempt in range(retries + 1):
        try:
            conn = aiohttp.TCPConnector(ssl=False)
            timeout_obj = aiohttp.ClientTimeout(total=timeout)
            async with aiohttp.ClientSession(
                connector=conn, timeout=timeout_obj, headers=hdrs
            ) as session:
                async with session.get(url, proxy=socks_url,
                                       allow_redirects=True) as resp:
                    text = await resp.text(errors="replace")
                    return _FakeResponse(resp.status, text, str(resp.url))
        except asyncio.TimeoutError:
            if attempt == retries:
                return None
            await asyncio.sleep(2)
        except Exception:
            if attempt == retries:
                return None
            await asyncio.sleep(2)
    return None


async def async_post_tor(url: str, tor_proxy: str, data: dict = None,
                         timeout: int = 40) -> Optional["_FakeResponse"]:
    hdrs = base_headers()
    socks_url = f"socks5h://{tor_proxy}"
    try:
        conn = aiohttp.TCPConnector(ssl=False)
        to = aiohttp.ClientTimeout(total=timeout)
        async with aiohttp.ClientSession(connector=conn, timeout=to, headers=hdrs) as s:
            async with s.post(url, proxy=socks_url, data=data,
                              allow_redirects=True) as resp:
                text = await resp.text(errors="replace")
                return _FakeResponse(resp.status, text, str(resp.url))
    except Exception:
        return None


def sync_get(url: str, proxy: Optional[str] = None, timeout: int = 20,
             headers: dict = None, retries: int = 2) -> Optional[requests.Response]:
    hdrs = base_headers()
    if headers:
        hdrs.update(headers)
    proxies = {"http": proxy, "https": proxy} if proxy else {}
    for attempt in range(retries + 1):
        try:
            return requests.get(url, headers=hdrs, proxies=proxies,
                                timeout=timeout, verify=False, allow_redirects=True)
        except Exception:
            if attempt == retries:
                return None
            time.sleep(1)
    return None


class _FakeResponse:
    def __init__(self, status: int, text: str, url: str):
        self.status_code = status
        self.text        = text
        self.url         = url

    def json(self):
        import json
        return json.loads(self.text)


_load_uas()
