#!/usr/bin/env python3

import asyncio
import argparse
import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

from modules.utils.tui        import TUI
from modules.utils.config      import load_config
from modules.utils.export      import Exporter
from modules.utils.proxy       import ProxyManager
from modules.utils.dedup       import ResultStore
from modules.scraper.breach    import BreachModule
from modules.scraper.paste     import PasteModule
from modules.scraper.social    import SocialModule
from modules.scraper.recent    import RecentBreachModule
from modules.dorking.engines   import DorkEngine
from modules.darkweb.engines   import DarkWebEngine
from modules.darkweb.crawler   import OnionCrawler

_tui   = TUI()
_store = ResultStore()
_cfg   = {}
_args  = None


async def run_scan(cfg, args, tui, store):
    proxy_mgr = ProxyManager(cfg)
    exporter  = Exporter(cfg, args.query or "recent", args.type)

    use_clear  = args.clearnet or not args.darkweb
    use_dark   = args.darkweb or args.both
    use_recent = getattr(args, "recent", False) or args.type == "recent"

    if args.both:
        use_clear = True
        use_dark  = True

    tor_proxy = args.tor or cfg.get("tor_proxy", "127.0.0.1:9050")

    if not use_recent:
        tui.print_scan_header(args.query, args.type, use_clear, use_dark, tor_proxy)

    tasks = []

    if use_recent:
        tui.section("RECENT BREACH FEED MODE", "📡")
        tui.info("Fetching latest publicly disclosed breaches — no target query needed")
        tasks.append(RecentBreachModule(cfg, proxy_mgr, store, tui).run())

    else:
        if use_clear:
            tasks += [
                BreachModule(cfg, proxy_mgr, store, tui).run(args.query, args.type),
                PasteModule(cfg, proxy_mgr, store, tui).run(args.query, args.type),
                SocialModule(cfg, proxy_mgr, store, tui).run(args.query, args.type),
                DorkEngine(cfg, proxy_mgr, store, tui).run(args.query, args.type),
            ]
        if use_dark:
            tasks += [
                DarkWebEngine(cfg, tor_proxy, store, tui).run(args.query, args.type),
                OnionCrawler(cfg, tor_proxy, store, tui).run(args.query, args.type),
            ]

    await asyncio.gather(*tasks, return_exceptions=True)

    exporter.save(store.all_results())
    tui.print_summary(store, exporter.outdir)


def parse_args():
    p = argparse.ArgumentParser(
        prog="rsx-osint",
        description="RSX-OSINT — Recon & Search eXtended",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python3 main.py                                         # interactive TUI
  python3 main.py --recent                                # latest breach feed
  python3 main.py -q user@example.com -t email --clearnet
  python3 main.py -q targetuser -t username --both --tor 127.0.0.1:9500
  python3 main.py -q example.com -t domain --clearnet --no-save
        """,
    )
    p.add_argument("-q", "--query")
    p.add_argument("-t", "--type",
                   help="email|username|password|hash|ip|domain|phone|name|recent")
    p.add_argument("--recent",     action="store_true",
                   help="Fetch latest publicly disclosed breaches (no query needed)")
    p.add_argument("--clearnet",   action="store_true")
    p.add_argument("--darkweb",    action="store_true")
    p.add_argument("--both",       action="store_true")
    p.add_argument("--tor",        default=None)
    p.add_argument("--no-save",    action="store_true")
    p.add_argument("--config",     default="config/settings.yaml")
    p.add_argument("--depth",      type=int, default=None)
    p.add_argument("--threads",    type=int, default=None)
    p.add_argument("--proxy-file", default=None)
    return p.parse_args()


async def main():
    global _cfg, _args, _store

    _tui.print_banner()

    args = parse_args()
    cfg  = load_config(args.config)

    if args.depth:      cfg["dark_crawl_depth"] = args.depth
    if args.threads:    cfg["workers"]           = args.threads
    if args.proxy_file: cfg["proxy_file"]        = args.proxy_file
    if args.no_save:    cfg["save_results"]      = False

    if args.recent or args.type == "recent":
        if not args.type:
            args.type  = "recent"
        if not args.query:
            args.query = ""
    elif not args.query or not args.type:
        from modules.utils.menu import InteractiveMenu
        args = InteractiveMenu(_tui, cfg).run()

    _cfg   = cfg
    _args  = args
    _store = ResultStore()

    await run_scan(cfg, args, _tui, _store)


def _save_partial():
    if _store.count() > 0 and _args and _cfg:
        _tui.warn("Interrupted — saving partial results...")
        try:
            Exporter(_cfg, _args.query or "recent",
                     _args.type).save(_store.all_results())
        except Exception:
            pass
        _tui.print_summary(_store, _cfg.get("output_dir", "output/results"))


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        _save_partial()
        sys.exit(0)
