# RSX-OSINT

> **Advanced Breach & Dark Web Intelligence Framework**  
> For authorised security research and ethical penetration testing only.

```
  ██████╗ ███████╗██╗  ██╗     ██████╗ ███████╗██╗███╗   ██╗████████╗
  ██╔══██╗██╔════╝╚██╗██╔╝    ██╔═══██╗██╔════╝██║████╗  ██║╚══██╔══╝
  ██████╔╝███████╗ ╚███╔╝     ██║   ██║███████╗██║██╔██╗ ██║   ██║
  ██╔══██╗╚════██║ ██╔██╗     ██║   ██║╚════██║██║██║╚██╗██║   ██║
  ██║  ██║███████║██╔╝ ██╗    ╚██████╔╝███████║██║██║ ╚████║   ██║
  ╚═╝  ╚═╝╚══════╝╚═╝  ╚═╝    ╚═════╝ ╚══════╝╚═╝╚═╝  ╚═══╝   ╚═╝
```

---

## Features

| Layer | What it does |
|---|---|
| **Breach DBs** | HIBP (k-anon + API), BreachDirectory, ProxyNova COMB, LeakCheck, GhostProject, Snusbase, IntelX |
| **Reputation** | EmailRep, Hunter.io, URLScan, VirusTotal, Shodan InternetDB, crt.sh |
| **Paste sites** | Pastebin (psbdmp API), paste.ee, JustPaste.it, paste2, rentry, controlc — raw-content credential extraction |
| **Code search** | GitHub code dork across multiple query patterns |
| **Surface dorking** | Google, Bing, DuckDuckGo, Startpage, Yahoo — proxy rotation, UA randomisation, 2captcha/anticaptcha |
| **Social/phone** | WhatsMyName (150+ platforms), NumVerify/AbstractAPI |
| **Dark web engines** | Ahmia, Torch, Haystak, DarkSearch (API), NotEvil, Phobos, Excavator, Kilos, OnionSearchEngine — paginated (up to 5 pages each) |
| **Dark web crawl** | Depth-2 breadth-first onion crawler — forum posts, marketplace listings, paste dumps, credential pattern extraction |
| **PwnDB** | Direct hidden-service credential lookup |
| **Output** | JSON + CSV + TXT per scan, saved to `output/results/` |

---

## Project Structure

```
rsx-osint/
├── main.py                     # Entry point
├── requirements.txt
├── README.md
├── LICENSE
├── config/
│   ├── settings.yaml           # All configuration
│   ├── proxies.txt             # One proxy per line
│   └── useragents.txt          # UA rotation list
├── modules/
│   ├── utils/
│   │   ├── tui.py              # Rich terminal UI
│   │   ├── config.py           # YAML loader
│   │   ├── proxy.py            # Proxy manager
│   │   ├── dedup.py            # Thread-safe result store
│   │   ├── export.py           # JSON/CSV/TXT writer
│   │   ├── http.py             # Async HTTP helpers + UA rotation
│   │   └── menu.py             # Interactive prompt menu
│   ├── scraper/
│   │   ├── breach.py           # HIBP, ProxyNova, Snusbase, etc.
│   │   ├── paste.py            # Pastebin + raw content extraction
│   │   └── social.py           # GitHub dorks, Hunter.io
│   ├── dorking/
│   │   ├── engines.py          # Google/Bing/DDG/Startpage with captcha bypass
│   │   ├── dorks.py            # Dork template library
│   │   └── captcha.py          # 2captcha / anticaptcha integration
│   └── darkweb/
│       ├── engines.py          # Onion search engines (paginated)
│       ├── crawler.py          # Depth-2 breadth-first onion crawler
│       └── parser.py           # Forum/market/paste page type detector
└── output/
    └── results/                # Scan output (JSON + CSV + TXT)
```

---

## Installation

### Prerequisites

- Python 3.10+
- Tor (for dark web mode)
- Playwright (optional, for JS-heavy pages)

### 1. Clone and set up virtualenv

```bash
git clone https://github.com/your-handle/rsx-osint.git
cd rsx-osint
python3 -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Install Playwright browser (optional)

Only needed if `use_playwright: true` is set in `config/settings.yaml`.

```bash
playwright install firefox
```

---

## Tor Setup

RSX-OSINT routes all dark web requests through Tor's SOCKS5 proxy.

### Kali / Debian / Ubuntu

```bash
sudo apt install tor
sudo systemctl start tor
# Default SOCKS5: 127.0.0.1:9050
```

### Verify Tor is running

```bash
curl --socks5-hostname 127.0.0.1:9050 https://check.torproject.org/api/ip
# Should return {"IsTor":true,...}
```

### Custom Tor port

If your Tor instance uses a non-default port (e.g. 9500), pass it at runtime:

```bash
python3 main.py -q target@email.com -t email --darkweb --tor 127.0.0.1:9500
```

Or set it in `config/settings.yaml`:

```yaml
tor_proxy: "127.0.0.1:9500"
```

---

## Proxy Configuration

Add proxies to `config/proxies.txt` — one per line:

```
http://45.77.123.45:3128
socks5://192.168.1.100:1080
http://user:pass@gate.example.com:8000
```

**Supported formats:** `http://`, `https://`, `socks5://` — with or without credentials.

Proxies are rotated per request. On a 429 or CAPTCHA response the current proxy is
marked bad and the next one is tried automatically.

**Recommended sources for free proxies:**
- https://free-proxy-list.net
- https://www.proxyscrape.com/free-proxy-list

**For reliable dorking without captcha blocks**, use a paid rotating proxy service
(Oxylabs, Bright Data, Smartproxy) — enter the gateway URL as a single proxy in
`proxies.txt`.

---

## Captcha Bypass

RSX-OSINT supports automatic captcha solving via third-party services.

### 2captcha

1. Sign up at https://2captcha.com ($3 per 1000 solves)
2. Add to `config/settings.yaml`:

```yaml
captcha_service: "2captcha"
captcha_api_key: "YOUR_2CAPTCHA_KEY"
```

### AntiCaptcha

1. Sign up at https://anti-captcha.com
2. Add to `config/settings.yaml`:

```yaml
captcha_service: "anticaptcha"
captcha_api_key: "YOUR_ANTICAPTCHA_KEY"
```

When a search engine triggers a reCAPTCHA, the tool will automatically submit it
for solving and retry the request with the returned token.

---

## API Keys (optional but recommended)

Configure in `config/settings.yaml` under `api_keys:`:

| Key | Source | Cost | Enables |
|---|---|---|---|
| `hibp` | https://haveibeenpwned.com/API/Key | $3.50/mo | Full email breach detail |
| `hunter` | https://hunter.io | Free (25/mo) | Domain email enumeration |
| `virustotal` | https://virustotal.com | Free tier | IP/domain/hash analysis |
| `snusbase` | https://snusbase.com | Paid | Large password DB search |
| `leakix` | https://leakix.net | Free tier | Leak DB search |
| `breachdirectory` | https://breachdirectory.org | Free tier | Breach credential lookup |

Without API keys the tool still runs with ~70% of sources active.

---

## Usage

### Interactive TUI (recommended)

```bash
python3 main.py
```

Follow the prompts to select search type, query, network mode, and optional API keys.

### CLI flags

```bash
# Surface web only — email
python3 main.py -q user@example.com -t email --clearnet

# Username across all surfaces
python3 main.py -q targetuser -t username --clearnet

# Dark web only (Tor required)
python3 main.py -q target@example.com -t email --darkweb --tor 127.0.0.1:9050

# Both surface + dark web
python3 main.py -q example.com -t domain --both --tor 127.0.0.1:9050

# IP recon
python3 main.py -q 1.2.3.4 -t ip --clearnet

# Hash lookup (HIBP k-anon, VirusTotal)
python3 main.py -q 5f4dcc3b5aa765d61d8327deb882cf99 -t hash --clearnet

# Suppress file output
python3 main.py -q target -t username --clearnet --no-save

# Override crawl depth
python3 main.py -q target@mail.com -t email --both --depth 2

# Override proxy list
python3 main.py -q target -t username --clearnet --proxy-file /path/to/proxies.txt
```

### All flags

```
-q / --query        Target string
-t / --type         email | username | password | hash | ip | domain | phone | name
--clearnet          Surface web only
--darkweb           Dark web (Tor) only
--both              Both surface + dark web
--tor ADDR          Tor SOCKS5 proxy address (default: 127.0.0.1:9050)
--no-save           Skip writing output files
--config PATH       Config file path (default: config/settings.yaml)
--depth N           Dark web crawl depth 1-3 (default: 2)
--threads N         Override worker count
--proxy-file PATH   Override proxy file path
```

---

## Output

Results are saved to `output/results/<type>_<query>_<timestamp>/`:

```
output/results/email_user_example_com_20240315_143022/
├── results.json    # Full structured data
├── results.csv     # Flat table (importable to Excel/LibreOffice)
└── results.txt     # Human-readable report
```

---

## Performance Tuning

Edit `config/settings.yaml`:

```yaml
workers:          20    # Surface web concurrent coroutines
dark_workers:     8     # Tor concurrent coroutines (keep low)
dark_crawl_depth: 2     # Onion crawl hops (1=fast, 3=thorough)
dark_crawl_pages: 5     # Pages per dark web engine
min_delay:        1.2   # Min seconds between surface requests
max_delay:        4.5   # Max seconds between surface requests
dark_min_delay:   2.0   # Min seconds between Tor requests
dark_max_delay:   7.0   # Max seconds between Tor requests
```

A full `--both` scan with defaults takes **4–10 minutes**. Increase delays if you
hit excessive captchas. Decrease `dark_workers` if Tor circuits time out frequently.

---

## Disclaimer

> **This tool is for authorised security research, penetration testing, and
> defensive threat intelligence only.**
>
> - You must have explicit permission before investigating any individual or system.
> - Use in accordance with applicable laws in your jurisdiction.
> - The author accepts no liability for any misuse of this software.
> - Unauthorised use may violate the Computer Fraud and Abuse Act (CFAA),
>   the Computer Misuse Act (CMA), GDPR, and other laws.

---

## License

MIT — see [LICENSE](LICENSE)
