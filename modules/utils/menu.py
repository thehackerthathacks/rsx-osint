"""modules/utils/menu.py — Interactive TUI menu"""

import argparse
from rich.console import Console
from rich.prompt  import Prompt, Confirm
from rich.table   import Table
from rich         import box

console = Console()

SEARCH_TYPES = {
    "1": ("email",    "Email address"),
    "2": ("username", "Username / handle"),
    "3": ("password", "Plaintext password"),
    "4": ("hash",     "Hash (MD5/SHA1/SHA256/bcrypt)"),
    "5": ("name",     "Full name"),
    "6": ("ip",       "IP address"),
    "7": ("domain",   "Domain / website"),
    "8": ("phone",    "Phone number"),
}


class InteractiveMenu:
    def __init__(self, tui, cfg: dict):
        self.tui = tui
        self.cfg = cfg

    def run(self) -> argparse.Namespace:
        args = argparse.Namespace()

        # Search type
        tbl = Table(box=box.SIMPLE_HEAVY, show_header=False, border_style="cyan")
        tbl.add_column("key",   style="bold yellow", width=4)
        tbl.add_column("type",  style="bold white")
        for k, (v, label) in SEARCH_TYPES.items():
            tbl.add_row(f"[{k}]", label)
        console.print(tbl)

        while True:
            choice = Prompt.ask("\n  [green]>[/green] Select type [1-8]")
            if choice in SEARCH_TYPES:
                args.type = SEARCH_TYPES[choice][0]
                break
            console.print("  [red]Invalid — enter 1-8[/red]")

        args.query = Prompt.ask(f"\n  [green]>[/green] Enter {args.type} to investigate").strip()
        if not args.query:
            console.print("[red]No query provided.[/red]")
            import sys; sys.exit(1)

        # Network mode
        console.print("\n  [cyan][1][/cyan] Clearnet only")
        console.print("  [cyan][2][/cyan] Dark web (Tor) only")
        console.print("  [cyan][3][/cyan] Both")

        while True:
            mode = Prompt.ask("\n  [green]>[/green] Mode [1-3]")
            if mode in ("1","2","3"):
                break
            console.print("  [red]Invalid[/red]")

        args.clearnet = mode in ("1","3")
        args.darkweb  = mode in ("2","3")
        args.both     = mode == "3"

        if args.darkweb:
            default_tor = self.cfg.get("tor_proxy","127.0.0.1:9050")
            tor = Prompt.ask(f"  [green]>[/green] Tor proxy",
                             default=default_tor)
            args.tor = tor
        else:
            args.tor = None

        # API keys
        if Confirm.ask("\n  Configure API keys?", default=False):
            args = self._prompt_apis(args)

        args.no_save = not Confirm.ask("  Save results to disk?", default=True)
        return args

    def _prompt_apis(self, args) -> argparse.Namespace:
        keys_cfg = self.cfg.get("api_keys", {})
        prompts = [
            ("hibp",            "HaveIBeenPwned (paid)"),
            ("hunter",          "Hunter.io (free 25/mo)"),
            ("virustotal",      "VirusTotal (free)"),
            ("snusbase",        "Snusbase (paid)"),
            ("breachdirectory", "BreachDirectory (free)"),
            ("leakix",          "LeakIX (free)"),
        ]
        for key, label in prompts:
            existing = keys_cfg.get(key, "")
            val = Prompt.ask(f"  [yellow]{label}[/yellow]",
                             default=existing or "", show_default=bool(existing))
            if val:
                keys_cfg[key] = val
        self.cfg["api_keys"] = keys_cfg
        return args
