#!/usr/bin/env python3
"""
RSX-OSINT  —  Advanced Breach & Dark Web Intelligence Framework
Author   : RSX / Hacker
License  : MIT
GitHub   : https://github.com/your-handle/rsx-osint
Usage    : python3 main.py [options]  or  python3 main.py  (interactive TUI)
"""

import asyncio
import argparse
import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

from modules.utils.tui       import TUI
from modules.utils.config     import load_config
from modules.utils.export     import Exporter
from modules.utils.proxy      import ProxyManager
from modules.utils.dedup      import ResultStore
from modules.scraper.breach   import BreachModule
from modules.scraper.paste    import PasteModule
from modules.scraper.social   import SocialModule
from modules.dorking.engines  import DorkEngine
from modules.darkweb.engines  import DarkWebEngine
from modules.darkweb.crawler  import OnionCrawler


async def run_scan(cfg, args, tui: TUI, store: ResultStore):
    proxy_mgr = ProxyManager(cfg)
    exporter  = Exporter(cfg, args.query, args.type)

    use_clear = args.clearnet or not args.darkweb
    use_dark  = args.darkweb or args.both
    if args.both:
        use_clear = True
        use_dark  = True

    tor_proxy = args.tor or cfg.get("tor_proxy", "127.0.0.1:9050")

    tui.print_scan_header(args.query, args.type, use_clear, use_dark, tor_proxy)

    tasks = []

    if use_clear:
        breach = BreachModule(cfg, proxy_mgr, store, tui)
        paste  = PasteModule(cfg, proxy_mgr, store, tui)
        social = SocialModule(cfg, proxy_mgr, store, tui)
        dork   = DorkEngine(cfg, proxy_mgr, store, tui)

        tasks += [
            breach.run(args.query, args.type),
            paste.run(args.query, args.type),
            social.run(args.query, args.type),
            dork.run(args.query, args.type),
        ]

    if use_dark:
        dw      = DarkWebEngine(cfg, tor_proxy, store, tui)
        crawler = OnionCrawler(cfg, tor_proxy, store, tui)
        tasks += [
            dw.run(args.query, args.type),
            crawler.run(args.query, args.type),
        ]

    await asyncio.gather(*tasks, return_exceptions=True)

    exporter.save(store.all_results())
    tui.print_summary(store, exporter.outdir)


def parse_args():
    p = argparse.ArgumentParser(
        prog="rsx-osint",
        description="RSX-OSINT — Advanced Breach & Dark Web Intelligence",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python3 main.py                                    # interactive TUI
  python3 main.py -q user@example.com -t email --clearnet
  python3 main.py -q targetuser -t username --both --tor 127.0.0.1:9500
  python3 main.py -q example.com -t domain --clearnet --no-save
  python3 main.py -q 1.2.3.4 -t ip --clearnet
        """,
    )
    p.add_argument("-q", "--query",    help="Target query string")
    p.add_argument("-t", "--type",     help="Query type: email|username|password|hash|ip|domain|phone|name")
    p.add_argument("--clearnet",       action="store_true", help="Surface web only")
    p.add_argument("--darkweb",        action="store_true", help="Dark web (Tor) only")
    p.add_argument("--both",           action="store_true", help="Both surface and dark web")
    p.add_argument("--tor",            default=None,        help="Tor SOCKS5 proxy (default: 127.0.0.1:9050)")
    p.add_argument("--no-save",        action="store_true", help="Do not write output files")
    p.add_argument("--config",         default="config/settings.yaml", help="Config file path")
    p.add_argument("--depth",          type=int, default=None, help="Dark web crawl depth (1-3)")
    p.add_argument("--threads",        type=int, default=None, help="Override concurrent workers")
    p.add_argument("--proxy-file",     default=None, help="Path to proxies.txt override")
    return p.parse_args()


def interactive_menu(tui: TUI, cfg: dict) -> argparse.Namespace:
    from modules.utils.menu import InteractiveMenu
    menu = InteractiveMenu(tui, cfg)
    return menu.run()


async def main():
    tui = TUI()
    tui.print_banner()

    args = parse_args()
    cfg  = load_config(args.config)

    if args.depth:
        cfg["dark_crawl_depth"] = args.depth
    if args.threads:
        cfg["workers"] = args.threads
    if args.proxy_file:
        cfg["proxy_file"] = args.proxy_file
    if args.no_save:
        cfg["save_results"] = False

    if not args.query or not args.type:
        args = interactive_menu(tui, cfg)

    store = ResultStore()

    try:
        await run_scan(cfg, args, tui, store)
    except KeyboardInterrupt:
        tui.warn("Interrupted — saving partial results...")
        if store.count() > 0:
            Exporter(cfg, args.query, args.type).save(store.all_results())
        tui.print_summary(store, "output/results")
        sys.exit(0)


if __name__ == "__main__":
    asyncio.run(main())
