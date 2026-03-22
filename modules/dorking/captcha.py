"""modules/dorking/captcha.py — 2captcha / anticaptcha solver integration"""

import asyncio
import aiohttp
import time
from typing import Optional


class CaptchaSolver:
    def __init__(self, cfg: dict):
        self.service = cfg.get("captcha_service", "").lower()
        self.api_key = cfg.get("captcha_api_key", "")
        self.enabled = bool(self.service and self.api_key)

    async def solve_recaptcha(self, site_key: str, page_url: str) -> Optional[str]:
        if not self.enabled:
            return None
        if self.service == "2captcha":
            return await self._2captcha_recaptcha(site_key, page_url)
        elif self.service == "anticaptcha":
            return await self._anticaptcha_recaptcha(site_key, page_url)
        return None

    async def solve_image(self, base64_img: str) -> Optional[str]:
        if not self.enabled:
            return None
        if self.service == "2captcha":
            return await self._2captcha_image(base64_img)
        return None

    # ── 2captcha ──────────────────────────────────────────────────────────
    async def _2captcha_recaptcha(self, site_key: str, page_url: str) -> Optional[str]:
        submit_url = "http://2captcha.com/in.php"
        params = {
            "key":       self.api_key,
            "method":    "userrecaptcha",
            "googlekey": site_key,
            "pageurl":   page_url,
            "json":      1,
        }
        try:
            async with aiohttp.ClientSession() as s:
                async with s.post(submit_url, data=params,
                                  timeout=aiohttp.ClientTimeout(total=15)) as r:
                    data = await r.json()
                    if data.get("status") != 1:
                        return None
                    task_id = data["request"]

            # Poll for result
            for _ in range(24):
                await asyncio.sleep(5)
                result_url = (f"http://2captcha.com/res.php"
                              f"?key={self.api_key}&action=get&id={task_id}&json=1")
                async with aiohttp.ClientSession() as s:
                    async with s.get(result_url,
                                     timeout=aiohttp.ClientTimeout(total=10)) as r:
                        data = await r.json()
                        if data.get("status") == 1:
                            return data.get("request")
                        if data.get("request") == "ERROR_CAPTCHA_UNSOLVABLE":
                            return None
        except Exception:
            return None
        return None

    async def _2captcha_image(self, base64_img: str) -> Optional[str]:
        submit_url = "http://2captcha.com/in.php"
        params = {
            "key":    self.api_key,
            "method": "base64",
            "body":   base64_img,
            "json":   1,
        }
        try:
            async with aiohttp.ClientSession() as s:
                async with s.post(submit_url, data=params,
                                  timeout=aiohttp.ClientTimeout(total=15)) as r:
                    data = await r.json()
                    if data.get("status") != 1:
                        return None
                    task_id = data["request"]

            for _ in range(12):
                await asyncio.sleep(5)
                result_url = (f"http://2captcha.com/res.php"
                              f"?key={self.api_key}&action=get&id={task_id}&json=1")
                async with aiohttp.ClientSession() as s:
                    async with s.get(result_url,
                                     timeout=aiohttp.ClientTimeout(total=10)) as r:
                        data = await r.json()
                        if data.get("status") == 1:
                            return data.get("request")
        except Exception:
            return None
        return None

    # ── AntiCaptcha ───────────────────────────────────────────────────────
    async def _anticaptcha_recaptcha(self, site_key: str, page_url: str) -> Optional[str]:
        create_url = "https://api.anti-captcha.com/createTask"
        payload = {
            "clientKey": self.api_key,
            "task": {
                "type":       "NoCaptchaTaskProxyless",
                "websiteURL": page_url,
                "websiteKey": site_key,
            },
        }
        try:
            async with aiohttp.ClientSession() as s:
                async with s.post(create_url, json=payload,
                                  timeout=aiohttp.ClientTimeout(total=15)) as r:
                    data = await r.json()
                    if data.get("errorId"):
                        return None
                    task_id = data.get("taskId")

            for _ in range(24):
                await asyncio.sleep(5)
                result_payload = {
                    "clientKey": self.api_key,
                    "taskId":    task_id,
                }
                async with aiohttp.ClientSession() as s:
                    async with s.post(
                        "https://api.anti-captcha.com/getTaskResult",
                        json=result_payload,
                        timeout=aiohttp.ClientTimeout(total=10),
                    ) as r:
                        data = await r.json()
                        if data.get("status") == "ready":
                            return data["solution"]["gRecaptchaResponse"]
                        if data.get("errorId"):
                            return None
        except Exception:
            return None
        return None
