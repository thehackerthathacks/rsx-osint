"""modules/utils/config.py — YAML config loader"""

import os
import yaml


DEFAULTS = {
    "tor_proxy":           "127.0.0.1:9050",
    "tor_control_port":    9051,
    "tor_password":        "",
    "workers":             20,
    "dark_workers":        8,
    "dark_crawl_depth":    2,
    "dark_crawl_pages":    5,
    "request_timeout":     25,
    "dark_timeout":        40,
    "min_delay":           1.2,
    "max_delay":           4.5,
    "dark_min_delay":      2.0,
    "dark_max_delay":      7.0,
    "proxy_file":          "config/proxies.txt",
    "rotate_proxies":      True,
    "proxy_on_captcha":    True,
    "captcha_service":     "",
    "captcha_api_key":     "",
    "use_playwright":      False,
    "playwright_browser":  "firefox",
    "playwright_headless": True,
    "save_results":        True,
    "output_dir":          "output/results",
    "output_formats":      ["json", "csv", "txt"],
    "max_results_per_source": 50,
    "api_keys":            {},
    "enabled_dork_engines": ["google","bing","duckduckgo","startpage"],
    "enabled_dark_engines": ["ahmia","torch","haystak","darksearch","notevil","phobos","excavator","kilos","onionsearchengine"],
    "enabled_breach_sources": ["haveibeenpwned","breachdirectory","proxynova","leakcheck","ghostproject","snusbase","intelx","leakix","emailrep","whatsmyname","shodan","virustotal","urlscan","crtsh","numverify"],
}


def load_config(path: str = "config/settings.yaml") -> dict:
    cfg = DEFAULTS.copy()
    if os.path.exists(path):
        with open(path, "r") as f:
            loaded = yaml.safe_load(f) or {}
        _deep_merge(cfg, loaded)
    return cfg


def _deep_merge(base: dict, override: dict):
    for k, v in override.items():
        if k in base and isinstance(base[k], dict) and isinstance(v, dict):
            _deep_merge(base[k], v)
        else:
            base[k] = v
