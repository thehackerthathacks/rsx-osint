"""modules/utils/tui.py — Rich-based terminal UI for RSX-OSINT"""

import time
import threading
from datetime import datetime
from typing import Optional

from rich.console import Console
from rich.panel   import Panel
from rich.table   import Table
from rich.text    import Text
from rich.rule    import Rule
from rich.align   import Align
from rich.columns import Columns
from rich         import box

console = Console(highlight=False)

BANNER_ART = r"""
  ██████╗ ███████╗██╗  ██╗       ██████╗ ███████╗██╗███╗   ██╗████████╗
  ██╔══██╗██╔════╝╚██╗██╔╝      ██╔═══██╗██╔════╝██║████╗  ██║╚══██╔══╝
  ██████╔╝███████╗ ╚███╔╝       ██║   ██║███████╗██║██╔██╗ ██║   ██║   
  ██╔══██╗╚════██║ ██╔██╗       ██║   ██║╚════██║██║██║╚██╗██║   ██║   
  ██║  ██║███████║██╔╝ ██╗      ╚██████╔╝███████║██║██║ ╚████║   ██║   
  ╚═╝  ╚═╝╚══════╝╚═╝  ╚═╝       ╚═════╝ ╚══════╝╚═╝╚═╝  ╚═══╝   ╚═╝  
"""

SUBTITLE = "Recon & Search eXtended  —  Breach & Dark Web Intelligence  v2.0"
TAGLINE  = "For authorized security research and ethical hacking only"

SOURCE_STYLES = {
    "haveibeenpwned":    "bold red",
    "hibp_recent":       "bold red",
    "breachdirectory":   "bold yellow",
    "proxynova":         "bold cyan",
    "pastebin":          "bold green",
    "pastebin_content":  "bold green",
    "paste.ee":          "bold green",
    "justpaste":         "bold green",
    "paste2":            "bold green",
    "rentry":            "bold green",
    "psbdmp":            "bold green",
    "psbdmp_content":    "bold green",
    "google_dork":       "bold blue",
    "bing_dork":         "bold blue",
    "duckduckgo_dork":   "bold blue",
    "startpage_dork":    "bold blue",
    "yahoo_dork":        "bold blue",
    "leakix":            "bold magenta",
    "leakix_recent":     "bold magenta",
    "intelx":            "bold yellow",
    "pwndb_onion":       "bold red",
    "pwndb":             "bold red",
    "onion_page_scan":   "bold red",
    "onion_crawl":       "bold red",
    "ahmia":             "bold magenta",
    "torch":             "bold red",
    "haystak":           "bold red",
    "darksearch":        "bold red",
    "notevil":           "bold red",
    "phobos":            "bold red",
    "excavator":         "bold red",
    "kilos":             "bold red",
    "github_dork":       "bold green",
    "github_breach_repo":"bold green",
    "emailrep":          "bold yellow",
    "whatsmyname":       "bold green",
    "shodan":            "bold red",
    "virustotal":        "bold yellow",
    "urlscan":           "bold cyan",
    "crt_sh":            "bold green",
    "ghostproject":      "bold magenta",
    "leakcheck":         "bold cyan",
    "snusbase":          "bold red",
    "databreaches_net":  "bold yellow",
    "breachforums":      "bold red",
    "reddit_netsec":     "bold cyan",
    "numverify":         "bold cyan",
    "hunter":            "bold cyan",
}

# Fields that contain actual leaked plaintext — always shown prominently
PLAINTEXT_FIELDS = {"password", "email / user", "email/user", "hash", "raw line",
                    "credential", "left", "right", "phone", "address", "name",
                    "ssn", "dob", "ip", "username"}

# Fields that are URLs to where data can be found
LINK_FIELDS = {"url", "raw url", "raw", "found in", "found on", "source url",
               "reddit", "link", "href"}


class TUI:
    def __init__(self):
        self._lock = threading.Lock()

    def print_banner(self):
        console.print()
        console.print(Text(BANNER_ART, style="bold red", justify="center"))
        console.print(Text(SUBTITLE,   style="bold cyan",   justify="center"))
        console.print(Text(TAGLINE,    style="dim italic",  justify="center"))
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

    def print_scan_header(self, query, qtype, clearnet, darkweb, tor_proxy):
        tbl = Table(box=box.SIMPLE_HEAVY, show_header=False, border_style="cyan")
        tbl.add_column("key",   style="bold yellow", no_wrap=True)
        tbl.add_column("value", style="white")
        tbl.add_row("Target",   query)
        tbl.add_row("Type",     qtype.upper())
        tbl.add_row("Clearnet", "[green]✔ enabled[/green]" if clearnet else "[dim]disabled[/dim]")
        tbl.add_row("Dark web", f"[red]✔ enabled[/red]  [dim]({tor_proxy})[/dim]"
                                if darkweb else "[dim]disabled[/dim]")
        tbl.add_row("Started",  datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        console.print(Panel(tbl,
                            title="[bold cyan]⟨ Scan Configuration ⟩[/bold cyan]",
                            border_style="cyan"))
        console.print()

    def info(self, msg: str):
        with self._lock:
            console.print(f"  [cyan][*][/cyan] [dim]{_ts()}[/dim]  {msg}")

    def found(self, msg: str):
        with self._lock:
            console.print(f"  [bold green][+][/bold green] [dim]{_ts()}[/dim]  "
                          f"[bold white]{msg}[/bold white]")

    def warn(self, msg: str):
        with self._lock:
            console.print(f"  [yellow][!][/yellow] [dim]{_ts()}[/dim]  [yellow]{msg}[/yellow]")

    def error(self, msg: str):
        with self._lock:
            console.print(f"  [red][-][/red] [dim]{_ts()}[/dim]  [red]{msg}[/red]")

    def section(self, title: str, icon: str = "●"):
        console.print()
        console.print(Rule(f"[bold magenta]{icon}  {title}[/bold magenta]",
                           style="magenta"))

    def dark_section(self, title: str):
        console.print()
        console.print(Rule(f"[bold red]🧅  {title}[/bold red]", style="red"))

    # ── Result card ───────────────────────────────────────────────────────
    def result_card(self, index: int, source: str, qtype: str,
                    data: str, extra: dict):
        style    = SOURCE_STYLES.get(source.lower(), "bold white")
        extra    = extra or {}
        data_str = str(data).strip()

        tbl = Table(box=box.MINIMAL, show_header=False, padding=(0, 1))
        tbl.add_column("k", style="dim", no_wrap=True, width=16)
        tbl.add_column("v", overflow="fold")

        # ── Plaintext credential display ──────────────────────────────────
        pw   = (extra.get("password") or extra.get("right") or "").strip()
        user = (extra.get("email / user") or extra.get("email/user") or
                extra.get("username") or extra.get("left") or "").strip()

        if pw and pw not in ("(empty)", "(hashed only)", "(not available)"):
            # We have a real plaintext password — show prominently
            tbl.add_row(
                "🔑 [bold green]PLAINTEXT[/bold green]",
                f"[cyan]{user}[/cyan][dim]:[/dim][bold bright_yellow]{pw}[/bold bright_yellow]"
                if user else f"[bold bright_yellow]{pw}[/bold bright_yellow]",
            )
        elif pw in ("(hashed only)",):
            # Hashed — show it but label clearly
            hash_val = extra.get("sha1") or extra.get("hash") or pw
            tbl.add_row(
                "🔐 [yellow]HASHED[/yellow]",
                f"[dim]{user}[/dim][dim]:[/dim][yellow]{hash_val}[/yellow]"
                if user else f"[yellow]{hash_val}[/yellow]",
            )
        elif ":" in data_str and qtype in ("email", "username", "password", "recent"):
            # Raw credential line from a paste/dump
            u, _, p = data_str.partition(":")
            if p.strip():
                tbl.add_row(
                    "🔑 [bold green]PLAINTEXT[/bold green]",
                    f"[cyan]{u.strip()}[/cyan][dim]:[/dim]"
                    f"[bold bright_yellow]{p.strip()}[/bold bright_yellow]",
                )
            else:
                tbl.add_row("[dim]Data[/dim]", f"[white]{data_str[:150]}[/white]")
        else:
            tbl.add_row("[dim]Data[/dim]", f"[white]{data_str[:150]}[/white]")

        # ── Extra fields — sorted: plaintext first, links last ────────────
        plaintext_rows = []
        link_rows      = []
        meta_rows      = []

        SKIP = {"password", "email / user", "email/user", "left", "right",
                "username", "sha1", "hash"}

        for k, v in extra.items():
            v = str(v).strip()
            if not v or k in SKIP:
                continue
            k_low = k.lower().replace(" ", "_")
            if k_low in PLAINTEXT_FIELDS:
                plaintext_rows.append((k, v))
            elif k_low in LINK_FIELDS:
                link_rows.append((k, v))
            else:
                meta_rows.append((k, v))

        for k, v in plaintext_rows:
            tbl.add_row(
                f"[green]{k.capitalize()}[/green]",
                f"[bright_green]{v[:200]}[/bright_green]",
            )

        for k, v in meta_rows:
            tbl.add_row(
                f"[dim]{k.capitalize()}[/dim]",
                f"[white]{v[:150]}[/white]",
            )

        for k, v in link_rows:
            if v.startswith("http"):
                # Distinguish clearnet vs onion
                if ".onion" in v:
                    tbl.add_row(
                        f"[red]🧅 {k.capitalize()}[/red]",
                        f"[red]{v[:200]}[/red]",
                    )
                else:
                    tbl.add_row(
                        f"[cyan]🌐 {k.capitalize()}[/cyan]",
                        f"[cyan]{v[:200]}[/cyan]",
                    )
            else:
                tbl.add_row(f"[dim]{k.capitalize()}[/dim]",
                            f"[white]{v[:150]}[/white]")

        # If no plaintext and no links at all, show a fallback where to look
        has_links      = any(str(v).strip().startswith("http") for _, v in link_rows)
        has_plaintext  = bool(pw and pw not in ("(empty)","(hashed only)","(not available)"))
        if not has_plaintext and not has_links:
            ref = _source_reference(source)
            if ref:
                tbl.add_row(
                    "[cyan]🌐 Find data at[/cyan]",
                    f"[cyan]{ref}[/cyan]",
                )

        panel = Panel(
            tbl,
            title=(f"[{style}]◉ {source.upper().replace('_',' ')}[/{style}]  "
                   f"[dim]#{index}[/dim]"),
            border_style="dim",
            expand=False,
        )
        with self._lock:
            console.print(panel)

    # ── Summary ───────────────────────────────────────────────────────────
    def print_summary(self, store, outdir: str):
        console.print()
        console.print(Rule("[bold cyan]Scan Complete[/bold cyan]", style="cyan"))

        stats = store.stats()
        total = store.count()

        src_tbl = Table(title="Results by Source", box=box.ROUNDED,
                        border_style="cyan", show_lines=False)
        src_tbl.add_column("Source",  style="yellow", no_wrap=True)
        src_tbl.add_column("Hits",    style="green",  justify="right")
        src_tbl.add_column("Bar",     style="green",  no_wrap=True)

        mx = max(stats.values(), default=1)
        for src, cnt in sorted(stats.items(), key=lambda x: -x[1]):
            bar = "█" * int(cnt / mx * 30)
            src_tbl.add_row(src.replace("_"," ").upper(), str(cnt), bar)

        sum_tbl = Table(box=box.SIMPLE, show_header=False)
        sum_tbl.add_column("k", style="bold yellow")
        sum_tbl.add_column("v", style="white")
        sum_tbl.add_row("Total results", str(total))
        sum_tbl.add_row("Output dir",    outdir)
        sum_tbl.add_row("Finished",      datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

        # Count how many results had actual plaintext passwords
        pw_count = 0
        for r in store.all_results():
            ex = r.get("extra", {})
            pw = (ex.get("password") or ex.get("right") or "").strip()
            if pw and pw not in ("(empty)", "(hashed only)", "(not available)"):
                pw_count += 1
            elif ":" in str(r.get("data", "")) and r.get("type") in (
                "email", "username", "password"
            ):
                pw_count += 1

        if pw_count:
            sum_tbl.add_row(
                "[bold green]Plaintext creds[/bold green]",
                f"[bold green]{pw_count} entries[/bold green]",
            )

        console.print(Columns([
            Panel(sum_tbl,  title="Summary",          border_style="cyan"),
            Panel(src_tbl,  title="Source Breakdown",  border_style="magenta"),
        ]))
        console.print()


def _source_reference(source: str) -> str:
    """Return a direct URL to the source where a user can look up data manually."""
    refs = {
        "haveibeenpwned":   "https://haveibeenpwned.com",
        "hibp_recent":      "https://haveibeenpwned.com/breaches",
        "breachdirectory":  "https://breachdirectory.org",
        "proxynova":        "https://www.proxynova.com/tools/comb",
        "leakcheck":        "https://leakcheck.io",
        "ghostproject":     "https://ghostproject.fr",
        "snusbase":         "https://snusbase.com",
        "intelx":           "https://intelx.io",
        "leakix":           "https://leakix.net",
        "databreaches_net": "https://www.databreaches.net",
        "breachforums":     "https://breachforums.st",
        "pwndb_onion":      "http://pwndb2am4tzkvold.onion  [TOR]",
        "pwndb":            "http://pwndb2am4tzkvold.onion  [TOR]",
        "onion_page_scan":  "[TOR] — see 'found on' field",
        "shodan":           "https://www.shodan.io",
        "virustotal":       "https://www.virustotal.com",
        "urlscan":          "https://urlscan.io",
        "crt_sh":           "https://crt.sh",
        "emailrep":         "https://emailrep.io",
        "whatsmyname":      "https://whatsmyname.app",
        "github_dork":      "https://github.com/search?type=code",
        "github_breach_repo": "https://github.com/search?q=topic:data-breach",
        "reddit_netsec":    "https://reddit.com/r/netsec",
    }
    return refs.get(source.lower(), "")


def _ts() -> str:
    return datetime.now().strftime("%H:%M:%S")
