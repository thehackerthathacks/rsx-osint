# RSX-OSINT / Recon & Search eXtended 

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
| **Dark web engines** | Ahmia, Torch, Haystak, DarkSearch, NotEvil, Phobos, Excavator, Kilos, OnionSearchEngine — paginated |
| **Dark web crawl** | Depth-2 breadth-first onion crawler — forum posts, marketplace listings, paste dumps, credential extraction |
| **PwnDB** | Direct hidden-service credential lookup |
| **Output** | JSON + CSV + TXT per scan, saved to `output/results/` |

---

## Project Structure

```
rsx-osint/
├── main.py
├── requirements.txt
├── README.md
├── LICENSE
├── install.sh          Linux / macOS installer
├── install.ps1         Windows installer
├── config/
│   ├── settings.yaml
│   ├── proxies.txt
│   └── useragents.txt
├── modules/
│   ├── utils/          tui · config · proxy · dedup · export · http · menu
│   ├── scraper/        breach · paste · social
│   ├── dorking/        engines · dorks · captcha
│   └── darkweb/        engines · crawler · parser
└── output/
    └── results/
```

---

## Installation

### Prerequisites

- Python 3.10+
- Tor (required for dark web mode only)
- Playwright (optional — for JS-heavy pages)

---

### Windows

**1. Install Python 3.10+**

Download from https://www.python.org/downloads/ — check **"Add Python to PATH"** during install.

**2. Run the installer**

Open PowerShell in the `rsx-osint` folder:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\install.ps1
```

The script will:
- Detect Python 3.10+ from `python3.12` down to `python`
- Create a `venv\` virtualenv and install all pip packages inside it
- Check if Tor is in PATH and test SOCKS5 connectivity on `127.0.0.1:9050`
- Run a module import check to confirm everything is working
- Generate both a `run.bat` (CMD) and `run.ps1` (PowerShell) launcher

**3. Run the tool**

```cmd
.\run.bat
```

Or with flags:

```cmd
.\run.bat -q user@example.com -t email --clearnet
.\run.bat -q targetuser -t username --both --tor 127.0.0.1:9050
```

---

### Linux / macOS

**1. Install Python 3.10+**

```bash
sudo apt install python3 python3-pip   # Debian/Ubuntu/Kali
sudo pacman -S python                  # Arch/Manjaro
sudo dnf install python3               # Fedora
```

**2. Run the installer**

```bash
chmod +x install.sh && ./install.sh
```

The script will:
- Detect your distro (Kali, Debian, Ubuntu, Arch, Fedora) and use the right package manager
- Install Tor and build dependencies via `apt` / `pacman` / `dnf`
- Create a `venv/` virtualenv and install all pip packages inside it
- Attempt to start the Tor service via `systemctl` and verify SOCKS5 connectivity
- Run a module import check to confirm everything is working
- Generate a `run.sh` launcher

**3. Run the tool**

```bash
./run.sh
```

Or with flags:

```bash
./run.sh -q user@example.com -t email --clearnet
./run.sh -q targetuser -t username --both --tor 127.0.0.1:9050
```

---

### Manual install (any OS)

```bash
git clone https://github.com/your-handle/rsx-osint.git
cd rsx-osint
python3 -m venv venv

source venv/bin/activate          # Linux/macOS
venv\Scripts\activate.bat         # Windows CMD
venv\Scripts\Activate.ps1         # Windows PowerShell

pip install -r requirements.txt
python3 main.py
```

---

## Tor Setup

Tor is only required for `--darkweb` and `--both` modes.

### Windows

Download the **Tor Expert Bundle** (not Tor Browser) from:
https://www.torproject.org/download/tor/

Extract it, then run:

```cmd
tor.exe
```

Tor will listen on `127.0.0.1:9050` by default.

### Linux

```bash
sudo apt install tor
sudo systemctl start tor
```

### Verify Tor is working

```bash
curl --socks5-hostname 127.0.0.1:9050 https://check.torproject.org/api/ip
```

Should return `{"IsTor":true,...}`.

### Custom port

```cmd
.\run.bat -q target@email.com -t email --darkweb --tor 127.0.0.1:9500
```

Or set permanently in `config/settings.yaml`:

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

Supported formats: `http://`, `https://`, `socks5://` with or without credentials.

Proxies rotate per request. On a 429 or CAPTCHA the current proxy is marked bad and the next is tried automatically.

For reliable dorking without captcha blocks, use a paid rotating proxy service (Oxylabs, Bright Data, Smartproxy) — enter the gateway as a single line in `proxies.txt`.

---

## Captcha Bypass

### 2captcha

1. Sign up at https://2captcha.com
2. Add to `config/settings.yaml`:

```yaml
captcha_service: "2captcha"
captcha_api_key: "YOUR_KEY"
```

### AntiCaptcha

1. Sign up at https://anti-captcha.com
2. Add to `config/settings.yaml`:

```yaml
captcha_service: "anticaptcha"
captcha_api_key: "YOUR_KEY"
```

---

## API Keys (optional)

Configure in `config/settings.yaml` under `api_keys:`:

| Key | Source | Cost | Enables |
|---|---|---|---|
| `hibp` | https://haveibeenpwned.com/API/Key | $3.50/mo | Full email breach detail |
| `hunter` | https://hunter.io | Free 25/mo | Domain email enumeration |
| `virustotal` | https://virustotal.com | Free tier | IP/domain/hash analysis |
| `snusbase` | https://snusbase.com | Paid | Large password DB search |
| `leakix` | https://leakix.net | Free tier | Leak DB search |
| `breachdirectory` | https://breachdirectory.org | Free tier | Breach credential lookup |

The tool runs with ~70% of sources active without any API keys.

---

## Usage

### Interactive TUI

```cmd
.\run.bat
```

### All CLI flags

```
-q / --query        Target string
-t / --type         email | username | password | hash | ip | domain | phone | name
--clearnet          Surface web only
--darkweb           Dark web (Tor) only
--both              Both surface + dark web
--tor ADDR          Tor SOCKS5 proxy (default: 127.0.0.1:9050)
--no-save           Skip writing output files
--config PATH       Config file path (default: config/settings.yaml)
--depth N           Dark web crawl depth 1-3 (default: 2)
--threads N         Override worker count
--proxy-file PATH   Override proxy file path
```

### Examples

```cmd
.\run.bat -q user@example.com -t email --clearnet
.\run.bat -q targetuser -t username --clearnet
.\run.bat -q example.com -t domain --both --tor 127.0.0.1:9050
.\run.bat -q 1.2.3.4 -t ip --clearnet
.\run.bat -q 5f4dcc3b5aa765d61d8327deb882cf99 -t hash --clearnet
.\run.bat -q target@mail.com -t email --both --depth 2 --no-save
```

---

## Output

Results saved to `output/results/<type>_<query>_<timestamp>/`:

```
output/results/email_user_example_com_20240315_143022/
├── results.json
├── results.csv
└── results.txt
```

---

## Performance Tuning

Edit `config/settings.yaml`:

```yaml
workers:          20    # Surface web concurrent coroutines
dark_workers:     8     # Tor concurrent coroutines
dark_crawl_depth: 2     # Onion crawl hops (1=fast, 3=thorough)
dark_crawl_pages: 5     # Pages per dark web engine
min_delay:        1.2   # Min seconds between surface requests
max_delay:        4.5   # Max seconds between surface requests
dark_min_delay:   2.0   # Min seconds between Tor requests
dark_max_delay:   7.0   # Max seconds between Tor requests
```

A full `--both` scan with defaults takes 4–10 minutes.

---

## Disclaimer

> This tool is for authorised security research, penetration testing, and defensive threat intelligence only.
> You must have explicit permission before investigating any individual or system.
> The author accepts no liability for any misuse of this software.
> Unauthorised use may violate the CFAA, CMA, GDPR, and other laws.

---

## License

MIT — see [LICENSE](LICENSE)
