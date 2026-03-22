"""
modules/utils/tui.py — Rich-based terminal UI for RSX-OSINT
"""

import time
import threading
from datetime import datetime
from typing import Optional

from rich.console import Console
from rich.panel   import Panel
from rich.table   import Table
from rich.text    import Text
from rich.live    import Live
from rich.spinner import Spinner
from rich.rule    import Rule
from rich.align   import Align
from rich.columns import Columns
from rich import box

console = Console(highlight=False)

BANNER_ART = r"""
  ██████╗ ███████╗██╗  ██╗       ██████╗ ███████╗██╗███╗   ██╗████████╗
  ██╔══██╗██╔════╝╚██╗██╔╝      ██╔═══██╗██╔════╝██║████╗  ██║╚══██╔══╝
  ██████╔╝███████╗ ╚███╔╝       ██║   ██║███████╗██║██╔██╗ ██║   ██║   
  ██╔══██╗╚════██║ ██╔██╗       ██║   ██║╚════██║██║██║╚██╗██║   ██║   
  ██║  ██║███████║██╔╝ ██╗      ╚██████╔╝███████║██║██║ ╚████║   ██║   
  ╚═╝  ╚═╝╚══════╝╚═╝  ╚═╝       ╚═════╝ ╚══════╝╚═╝╚═╝  ╚═══╝   ╚═╝  
"""

SUBTITLE = "Advanced Breach & Dark Web Intelligence Framework  v2.0"
TAGLINE  = "For authorized security research and ethical hacking only"


class TUI:
    def __init__(self):
        self._lock = threading.Lock()
        self._spinner_active = False
        self._live: Optional[Live] = None

    # ── Banner ────────────────────────────────────────────────────────────────
    def print_banner(self):
        console.print()
        art = Text(BANNER_ART, style="bold red", justify="center")
        console.print(art)

        sub_text = Text(SUBTITLE, style="bold cyan", justify="center")
        console.print(sub_text)

        tag_text = Text(TAGLINE, style="dim italic", justify="center")
        console.print(tag_text)
        console.print()

        notice = Panel(
            Text.from_markup(
                "[bold red]⚠  LEGAL NOTICE[/bold red]\n"
                "[white]This tool is for [bold]authorised security research only.[/bold]\n"
                "Unauthorised use may violate computer crime laws in your jurisdiction.\n"
                "The author accepts no liability for misuse.[/white]"
            ),
            border_style="red",
            expand=False,
        )
        console.print(Align.center(notice))
        console.print()

    # ── Scan header ───────────────────────────────────────────────────────────
    def print_scan_header(self, query, qtype, clearnet, darkweb, tor_proxy):
        tbl = Table(box=box.SIMPLE_HEAVY, show_header=False, border_style="cyan")
        tbl.add_column("key",   style="bold yellow", no_wrap=True)
        tbl.add_column("value", style="white")
        tbl.add_row("Target",    query)
        tbl.add_row("Type",      qtype.upper())
        tbl.add_row("Clearnet",  "[green]✔ enabled[/green]" if clearnet else "[dim]disabled[/dim]")
        tbl.add_row("Dark web",  f"[red]✔ enabled[/red]  [dim]({tor_proxy})[/dim]" if darkweb else "[dim]disabled[/dim]")
        tbl.add_row("Started",   datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        console.print(Panel(tbl, title="[bold cyan]⟨ Scan Configuration ⟩[/bold cyan]", border_style="cyan"))
        console.print()

    # ── Logging ───────────────────────────────────────────────────────────────
    def info(self, msg: str):
        with self._lock:
            console.print(f"  [cyan][*][/cyan] [dim]{_ts()}[/dim]  {msg}")

    def found(self, msg: str):
        with self._lock:
            console.print(f"  [bold green][+][/bold green] [dim]{_ts()}[/dim]  [bold white]{msg}[/bold white]")

    def warn(self, msg: str):
        with self._lock:
            console.print(f"  [yellow][!][/yellow] [dim]{_ts()}[/dim]  [yellow]{msg}[/yellow]")

    def error(self, msg: str):
        with self._lock:
            console.print(f"  [red][-][/red] [dim]{_ts()}[/dim]  [red]{msg}[/red]")

    def section(self, title: str, icon: str = "●"):
        console.print()
        console.print(Rule(f"[bold magenta]{icon}  {title}[/bold magenta]", style="magenta"))

    def dark_section(self, title: str):
        console.print()
        console.print(Rule(f"[bold red]🧅  {title}[/bold red]", style="red"))

    # ── Result card ───────────────────────────────────────────────────────────
    def result_card(self, index: int, source: str, qtype: str, data: str, extra: dict):
        SOURCE_STYLES = {
            "haveibeenpwned":  "bold red",
            "breachdirectory": "bold yellow",
            "proxynova":       "bold cyan",
            "pastebin":        "bold green",
            "google_dork":     "bold blue",
            "bing_dork":       "bold blue",
            "ddg_dork":        "bold blue",
            "startpage_dork":  "bold blue",
            "leakix":          "bold magenta",
            "intelx":          "bold yellow",
            "pwndb_onion":     "bold red",
            "ahmia":           "bold magenta",
            "torch":           "bold red",
            "haystak":         "bold red",
            "darksearch":      "bold red",
            "notevil":         "bold red",
            "phobos":          "bold red",
            "onion_crawl":     "bold red",
            "github_dork":     "bold green",
            "emailrep":        "bold yellow",
            "whatsmyname":     "bold green",
            "shodan":          "bold red",
            "virustotal":      "bold yellow",
            "urlscan":         "bold cyan",
            "crt_sh":          "bold green",
            "ghostproject":    "bold magenta",
            "leakcheck":       "bold cyan",
        }
        style = SOURCE_STYLES.get(source.lower(), "bold white")

        tbl = Table(box=box.MINIMAL, show_header=False, padding=(0, 1))
        tbl.add_column("k", style="dim", no_wrap=True, width=14)
        tbl.add_column("v", style="white", overflow="fold")

        data_str = str(data)
        if ":" in data_str and qtype in ("email", "username", "password"):
            u, _, p = data_str.partition(":")
            tbl.add_row("Credential",
                f"[cyan]{u}[/cyan][dim]:[/dim][bold yellow]{p}[/bold yellow]")
        else:
            tbl.add_row("Data", data_str[:120])

        for k, v in (extra or {}).items():
            if v and str(v).strip():
                tbl.add_row(k.replace("_"," ").capitalize(), str(v)[:120])

        panel = Panel(
            tbl,
            title=f"[{style}]◉ {source.upper().replace('_',' ')}[/{style}]  "
                  f"[dim]#{index}[/dim]",
            border_style="dim",
            expand=False,
        )
        with self._lock:
            console.print(panel)

    # ── Summary ───────────────────────────────────────────────────────────────
    def print_summary(self, store, outdir: str):
        console.print()
        console.print(Rule("[bold cyan]Scan Complete[/bold cyan]", style="cyan"))

        stats = store.stats()
        total = store.count()

        tbl = Table(title="Results by Source", box=box.ROUNDED, border_style="cyan",
                    show_lines=False)
        tbl.add_column("Source",  style="yellow", no_wrap=True)
        tbl.add_column("Hits",    style="green",  justify="right")
        tbl.add_column("Bar",     style="green",  no_wrap=True)

        mx = max(stats.values(), default=1)
        for src, cnt in sorted(stats.items(), key=lambda x: -x[1]):
            bar = "█" * int(cnt / mx * 30)
            tbl.add_row(src.replace("_"," ").upper(), str(cnt), bar)

        summary_tbl = Table(box=box.SIMPLE, show_header=False)
        summary_tbl.add_column("k", style="bold yellow")
        summary_tbl.add_column("v", style="white")
        summary_tbl.add_row("Total results", str(total))
        summary_tbl.add_row("Output dir",    outdir)
        summary_tbl.add_row("Finished",      datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

        pw_count = sum(1 for r in store.all_results()
                       if r.get("extra", {}).get("password") or
                       (":" in str(r.get("data","")) and r.get("type") in ("email","username")))
        if pw_count:
            summary_tbl.add_row("[bold red]Credentials[/bold red]",
                                f"[bold red]{pw_count} entries with credential data[/bold red]")

        console.print(Columns([
            Panel(summary_tbl, title="Summary",        border_style="cyan"),
            Panel(tbl,          title="Source Breakdown", border_style="magenta"),
        ]))
        console.print()


def _ts() -> str:
    return datetime.now().strftime("%H:%M:%S")
