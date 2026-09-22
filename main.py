import tls_client
import requests
import random
import sys
import time
import os
import threading
import string
import itertools
import base64
import colorama
import shutil
import datetime
import json
import re
import urllib3
from typing import Optional, List, Dict, Tuple
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

# Ensure UTF-8 output encoding in Windows terminal
try:
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
    if hasattr(sys.stderr, 'reconfigure'):
        sys.stderr.reconfigure(encoding='utf-8')
except Exception:
    pass

# Disable SSL warnings
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
colorama.init()

if getattr(sys, 'frozen', False):
    SCRIPT_DIR = Path(sys.executable).parent
else:
    SCRIPT_DIR = Path(__file__).parent

LOCK = threading.Lock()
PRINT_LOCK = threading.Lock()
FILE_LOCK = threading.Lock()

DEFAULT_CONFIG = {
    "proxy_mode": False,
    "thread_count": 10,
    "timeout": 10,
    "remove_bad_tokens_from_input": False
}

# Discord client build number - Chrome 131
DISCORD_BUILD_NUMBER = 348978

# =============================================
# STYLING (matches bankroll tools)
# =============================================
class bcolors:
    """Color codes for terminal output"""
    TIME = '\033[90m'
    MAGENTA = '\033[95m'
    CYAN = '\033[96m'
    OKGREEN = '\033[92m'
    FAIL = '\033[91m'
    WARNING = '\033[93m'
    YELLOW = '\033[93m'
    PURPLE = '\033[95m'
    WHITE = '\033[97m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'

def ts() -> str:
    """Return formatted timestamp in grey [HH:MM:SS]"""
    return f"{bcolors.TIME}[{datetime.datetime.now().strftime('%H:%M:%S')}]{bcolors.ENDC}"

def log_input(prompt: str) -> str:
    """Return input prompt with magenta <> prefix"""
    return f"{ts()} {bcolors.MAGENTA}<>{bcolors.ENDC} {prompt}"

def log_info(msg: str):
    """Print info with cyan * prefix"""
    with PRINT_LOCK:
        print(f"{ts()} {bcolors.CYAN}*{bcolors.ENDC} {msg}")

def log_warn(msg: str):
    """Print warning with magenta ! prefix"""
    with PRINT_LOCK:
        print(f"{ts()} {bcolors.MAGENTA}!{bcolors.ENDC} {msg}")

def log_success(msg: str):
    """Print success with green + prefix"""
    with PRINT_LOCK:
        print(f"{ts()} {bcolors.OKGREEN}+{bcolors.ENDC} {msg}")

def log_error(msg: str):
    """Print error with red - prefix"""
    with PRINT_LOCK:
        print(f"{ts()} {bcolors.FAIL}-{bcolors.ENDC} {msg}")

def rgb_to_ansi(r, g, b):
    """Convert RGB to ANSI color code"""
    return f'\033[38;2;{r};{g};{b}m'

def gradient_text(text: str, start_color: Tuple[int, int, int], end_color: Tuple[int, int, int]) -> str:
    """Create gradient text effect"""
    lines = text.split('\n')
    result = []
    for line in lines:
        if not line.strip():
            result.append('')
            continue
        line_length = len(line)
        gradient_line = ""
        for i, char in enumerate(line):
            ratio = i / max(line_length - 1, 1)
            r = int(start_color[0] + (end_color[0] - start_color[0]) * ratio)
            g = int(start_color[1] + (end_color[1] - start_color[1]) * ratio)
            b = int(start_color[2] + (end_color[2] - start_color[2]) * ratio)
            gradient_line += f"{rgb_to_ansi(r, g, b)}{char}"
        result.append(gradient_line + '\033[0m')
    return '\n'.join(result)

BANNER_LINES = [
    r"    __                  __              ____",
    r"   / /_  ____ _____    / /___________  / / /",
    r"  / __ \/ __ `/ __ \  / //_/ ___/ __ \/ / / ",
    r" / /_/ / /_/ / / / / / ,< / /  / /_/ / / /  ",
    r"/_.___/\__,_/_/ /_/ /_/|_/_/   \____/_/_/   "
]

def print_banner():
    """Print clean styled bankroll banner centered in terminal"""
    term_width = shutil.get_terminal_size((80, 20)).columns
    max_len = max(len(l) for l in BANNER_LINES)
    pad = max(0, (term_width - max_len) // 2)
    
    centered_banner = "\n".join(" " * pad + line for line in BANNER_LINES)
    gradient_banner = gradient_text(centered_banner, (147, 112, 219), (0, 206, 209))
    print()
    print(gradient_banner)
    print()

def clear_console():
    """Clear the console window"""
    os.system("cls" if os.name == 'nt' else "clear")

def update_title(valid: int = 0, nitro: int = 0, locked: int = 0, invalid: int = 0):
    """Update console title with current statistics"""
    try:
        import ctypes
        if hasattr(ctypes, 'windll'):
            ctypes.windll.kernel32.SetConsoleTitleW(
                f"bankroll | Token Checker | Valid: {valid} | Nitro: {nitro} | Locked: {locked} | Invalid: {invalid}"
            )
    except Exception:
        pass

def build_super_properties() -> str:
    """Build the x-super-properties header value (base64 encoded client info)"""
    properties = {
        "os": "Windows",
        "browser": "Chrome",
        "device": "",
        "system_locale": "en-US",
        "browser_user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
        "browser_version": "131.0.0.0",
        "os_version": "10",
        "referrer": "",
        "referring_domain": "",
        "referrer_current": "",
        "referring_domain_current": "",
        "release_channel": "stable",
        "client_build_number": DISCORD_BUILD_NUMBER,
        "client_event_source": None,
        "design_id": 0
    }
    return base64.b64encode(json.dumps(properties, separators=(',', ':')).encode()).decode()

def get_discord_headers(token: str) -> dict:
    """Build standard Discord client headers"""
    return {
        "Authorization": token,
        "Content-Type": "application/json",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
        "X-Super-Properties": build_super_properties(),
        "X-Discord-Locale": "en-US",
        "X-Discord-Timezone": "America/New_York",
        "Sec-Ch-Ua": '"Google Chrome";v="131", "Chromium";v="131", "Not_A Brand";v="24"',
        "Sec-Ch-Ua-Mobile": "?0",
        "Sec-Ch-Ua-Platform": '"Windows"',
        "Sec-Fetch-Dest": "empty",
        "Sec-Fetch-Mode": "cors",
        "Sec-Fetch-Site": "same-origin"
    }

def format_proxy(proxy: Optional[str]) -> Optional[str]:
    """Format proxy string properly for tls_client and requests"""
    if not proxy:
        return None
    p = proxy.strip().strip('"').strip("'")
    if not p:
        return None
    if "@" not in p and p.count(":") == 3:
        parts = p.split(":")
        if parts[3].isdigit() and not parts[1].isdigit():
            p = f"{parts[0]}:{parts[1]}@{parts[2]}:{parts[3]}"
        elif parts[1].isdigit() and not parts[3].isdigit():
            p = f"{parts[2]}:{parts[3]}@{parts[0]}:{parts[1]}"
    if p.startswith(('http://', 'https://', 'socks5://')):
        return p
    return f"http://{p}"

# =============================================
# TOKEN PARSER
# =============================================
DISCORD_TOKEN_REGEX = re.compile(
    r'(?:^|[^a-zA-Z0-9_\-\.])(mfa\.[a-zA-Z0-9_\-]{50,120}|[a-zA-Z0-9_\-]{20,38}\.[a-zA-Z0-9_\-]{4,12}\.[a-zA-Z0-9_\-]{25,60})(?:$|[^a-zA-Z0-9_\-\.])'
)
EMAIL_REGEX = re.compile(r'[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+')

def parse_token_line(line: str) -> Optional[Tuple[str, str, str]]:
    """
    Parse a line from token file to extract (raw_token, identifier, original_line).
    Supports all formats including:
      - email:pass:token
      - email:pass:2fa:token
      - email;pass:token
      - token:pass:email
      - raw token
    """
    original_line = line.strip()
    content = original_line.strip('"').strip("'").strip('`').strip()
    if not content or content.startswith("#"):
        return None

    if content.lower().startswith("bot "):
        content = content[4:].strip()
    elif content.lower().startswith("bearer "):
        content = content[7:].strip()

    token_match = DISCORD_TOKEN_REGEX.search(content)
    email_match = EMAIL_REGEX.search(content)

    raw_token = ""
    identifier = ""

    if token_match:
        raw_token = token_match.group(1).strip()

    if email_match:
        identifier = email_match.group(0).strip()

    if not raw_token:
        parts = [p.strip() for p in re.split(r'[:|;]', content) if p.strip()]
        if len(parts) >= 3:
            if "@" in parts[0]:
                identifier = identifier or parts[0]
                raw_token = parts[-1]
            elif "@" in parts[-1]:
                identifier = identifier or parts[-1]
                raw_token = parts[0]
            else:
                raw_token = parts[-1]
                identifier = identifier or parts[0]
        elif len(parts) == 2:
            if "@" in parts[0]:
                identifier = identifier or parts[0]
                raw_token = parts[1]
            else:
                raw_token = parts[0]
                identifier = identifier or parts[1]
        elif len(parts) == 1:
            raw_token = parts[0]

    raw_token = raw_token.strip().strip('"').strip("'").strip('`').strip()
    if not raw_token:
        return None

    if not identifier:
        remaining = content.replace(raw_token, "").strip()
        parts = [p.strip() for p in re.split(r'[:;|]', remaining) if p.strip()]
        if parts and len(parts[0]) > 2:
            identifier = parts[0]
        else:
            identifier = raw_token[:10] + "..." if len(raw_token) > 14 else raw_token

    identifier = identifier.strip().strip('"').strip("'").strip('`').strip()
    return raw_token, identifier, original_line

# =============================================
# SETUP FOLDERS
# =============================================
def setup_folders():
    """Create necessary input and output folders inside token checker"""
    for folder in ["input", "output"]:
        os.makedirs(SCRIPT_DIR / folder, exist_ok=True)
    
    files = {
        "input/tokens.txt": "",
        "input/proxies.txt": "",
        "output/valid.txt": "",
        "output/nitro.txt": "",
        "output/no_nitro.txt": "",
        "output/locked.txt": "",
        "output/invalid.txt": "",
    }
    for file_path, default_content in files.items():
        fp = SCRIPT_DIR / file_path
        if not fp.exists():
            with open(fp, "w", encoding="utf-8") as f:
                f.write(default_content)

    config_path = SCRIPT_DIR / "config.json"
    if not config_path.exists():
        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(DEFAULT_CONFIG, f, indent=4)

def load_proxies() -> List[str]:
    """Load proxy list from input/proxies.txt"""
    proxy_file = SCRIPT_DIR / "input" / "proxies.txt"
    if proxy_file.exists():
        with open(proxy_file, "r", encoding="utf-8") as f:
            return [l.strip() for l in f if l.strip() and not l.startswith("#")]
    return []

def load_config() -> dict:
    """Load configuration from config.json with fallback to default settings"""
    config_file = SCRIPT_DIR / "config.json"
    cfg = dict(DEFAULT_CONFIG)
    if config_file.exists():
        try:
            with open(config_file, "r", encoding="utf-8") as f:
                loaded = json.load(f)
                if isinstance(loaded, dict):
                    cfg.update(loaded)
        except Exception:
            pass
    return cfg

# =============================================
# TOKEN CHECKER CORE
# =============================================
class TokenChecker:
    """Discord Token Validation & Categorization Engine"""

    def __init__(self, config_data: dict):
        self.config = config_data
        self.proxies = load_proxies()
        self.proxy_mode = self.config.get("proxy_mode", False)
        self.thread_count = self.config.get("thread_count", 10)
        self.timeout = self.config.get("timeout", 10)

    def reload_config(self):
        """Reload configuration and proxies from disk"""
        self.config = load_config()
        self.proxies = load_proxies()
        self.proxy_mode = self.config.get("proxy_mode", False)
        self.thread_count = self.config.get("thread_count", 10)
        self.timeout = self.config.get("timeout", 10)

    def load_tokens_from_file(self, file_path: Path) -> List[Tuple[str, str, str]]:
        """Load and parse tokens from file"""
        if not file_path.exists():
            return []
        entries = []
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            for line in f:
                parsed = parse_token_line(line)
                if parsed:
                    entries.append(parsed)
        return entries

    def check_single_token(
        self,
        idx: int,
        entry: Tuple[str, str, str],
        proxy: Optional[str],
        stats: dict,
        stats_lock: threading.Lock
    ):
        """Perform comprehensive Discord API check on a single token with 429 rate limit retry"""
        raw_token, identifier, original_line = entry
        session = tls_client.Session(client_identifier="chrome_131")
        p_url = format_proxy(proxy) if self.proxy_mode else None
        headers = get_discord_headers(raw_token)

        try:
            # 1. Check User Profile Endpoint with 429 auto-retry
            me_res = None
            for _ in range(4):
                if p_url:
                    me_res = session.get("https://discord.com/api/v9/users/@me", headers=headers, proxy=p_url, timeout_seconds=self.timeout)
                else:
                    me_res = session.get("https://discord.com/api/v9/users/@me", headers=headers, timeout_seconds=self.timeout)

                if me_res.status_code == 429:
                    try:
                        r_data = me_res.json()
                        wait_sec = float(r_data.get("retry_after", 2.0))
                    except Exception:
                        wait_sec = 2.0
                    time.sleep(wait_sec + 0.2)
                    continue
                break

            if me_res is None or me_res.status_code == 429:
                with stats_lock:
                    stats["invalid_count"] += 1
                with PRINT_LOCK:
                    print(f"{ts()} {bcolors.FAIL}- [{identifier}] | Rate Limited (429 Max Retries){bcolors.ENDC}")
                return

            # Case A: Invalid Token
            if me_res.status_code == 401:
                with stats_lock:
                    stats["invalid_count"] += 1
                with PRINT_LOCK:
                    print(f"{ts()} {bcolors.FAIL}-{bcolors.ENDC} {bcolors.WHITE}[{identifier}] | {bcolors.ENDC}{bcolors.FAIL}(Invalid){bcolors.ENDC}")
                with FILE_LOCK:
                    with open(SCRIPT_DIR / "output" / "invalid.txt", "a", encoding="utf-8") as f:
                        f.write(original_line + "\n")
                return

            # Case B: Locked / Verification Required
            if me_res.status_code in (403, 400):
                lock_tag = "(Locked)"
                try:
                    err_json = me_res.json()
                    msg = str(err_json.get("message", "")).lower()
                    code = err_json.get("code", 0)
                    if "phone" in msg or code == 40002:
                        lock_tag = "(Locked: Phone Required)"
                    elif "email" in msg:
                        lock_tag = "(Locked: Email Required)"
                except Exception:
                    pass

                with stats_lock:
                    stats["locked_count"] += 1
                with PRINT_LOCK:
                    print(f"{ts()} {bcolors.FAIL}-{bcolors.ENDC} {bcolors.WHITE}[{identifier}] | {bcolors.ENDC}{bcolors.FAIL}{lock_tag}{bcolors.ENDC}")
                with FILE_LOCK:
                    with open(SCRIPT_DIR / "output" / "locked.txt", "a", encoding="utf-8") as f:
                        f.write(original_line + "\n")
                return

            # Case C: Profile returns 200 OK -> verify secondary access for hidden locks
            if me_res.status_code == 200:
                user_data = me_res.json()

                # Check secondary endpoint to ensure token is fully unlocked and not quarantined
                is_locked = False
                lock_tag = "(Locked)"
                guilds_res = None
                try:
                    for _ in range(3):
                        if p_url:
                            guilds_res = session.get("https://discord.com/api/v9/users/@me/guilds", headers=headers, proxy=p_url, timeout_seconds=self.timeout)
                        else:
                            guilds_res = session.get("https://discord.com/api/v9/users/@me/guilds", headers=headers, timeout_seconds=self.timeout)

                        if guilds_res.status_code == 429:
                            try:
                                r_data = guilds_res.json()
                                wait_sec = float(r_data.get("retry_after", 2.0))
                            except Exception:
                                wait_sec = 2.0
                            time.sleep(wait_sec + 0.2)
                            continue
                        break

                    if guilds_res and guilds_res.status_code in (403, 400):
                        is_locked = True
                        g_json = guilds_res.json() if guilds_res.status_code == 400 else {}
                        g_msg = str(g_json.get("message", "")).lower()
                        if "verify" in g_msg or "phone" in g_msg:
                            lock_tag = "(Locked: Phone Required)"
                except Exception:
                    pass

                if is_locked:
                    with stats_lock:
                        stats["locked_count"] += 1
                    with PRINT_LOCK:
                        print(f"{ts()} {bcolors.FAIL}-{bcolors.ENDC} {bcolors.WHITE}[{identifier}] | {bcolors.ENDC}{bcolors.FAIL}{lock_tag}{bcolors.ENDC}")
                    with FILE_LOCK:
                        with open(SCRIPT_DIR / "output" / "locked.txt", "a", encoding="utf-8") as f:
                            f.write(original_line + "\n")
                    return

                # Token is 100% valid and unlocked
                premium_type = user_data.get("premium_type", 0)
                is_nitro = premium_type and premium_type > 0

                # Check Nitro details & Boost Slots if Nitro is active
                unused_slots = 0
                used_slots = 0
                days_left = "N/A"

                if is_nitro:
                    # 1. Fetch expiration from subscriptions
                    try:
                        if p_url:
                            bill_res = session.get(
                                "https://discord.com/api/v9/users/@me/billing/subscriptions",
                                headers=headers,
                                proxy=p_url,
                                timeout_seconds=self.timeout
                            )
                        else:
                            bill_res = session.get(
                                "https://discord.com/api/v9/users/@me/billing/subscriptions",
                                headers=headers,
                                timeout_seconds=self.timeout
                            )
                        if bill_res.status_code == 200:
                            sub_data = bill_res.json()
                            if isinstance(sub_data, list) and sub_data:
                                end_time = sub_data[0].get("current_period_end") or sub_data[0].get("trial_ends_at")
                                if end_time:
                                    cleaned = end_time.replace("Z", "+00:00")
                                    end_dt = datetime.datetime.fromisoformat(cleaned)
                                    now_dt = datetime.datetime.now(datetime.timezone.utc)
                                    diff = (end_dt - now_dt).total_seconds()
                                    if diff > 0:
                                        days = int(diff // 86400)
                                        days_left = f"{days}d"
                                    else:
                                        days_left = "0d"
                    except Exception:
                        pass

                    # 2. Fetch server boost slots (unused vs used)
                    try:
                        if p_url:
                            slots_res = session.get(
                                "https://discord.com/api/v9/users/@me/guilds/premium/subscription-slots",
                                headers=headers,
                                proxy=p_url,
                                timeout_seconds=self.timeout
                            )
                        else:
                            slots_res = session.get(
                                "https://discord.com/api/v9/users/@me/guilds/premium/subscription-slots",
                                headers=headers,
                                timeout_seconds=self.timeout
                            )
                        if slots_res.status_code == 200:
                            slots_data = slots_res.json()
                            if isinstance(slots_data, list):
                                unused_slots = sum(1 for s in slots_data if not s.get("premium_guild_subscription"))
                                used_slots = sum(1 for s in slots_data if s.get("premium_guild_subscription"))
                    except Exception:
                        pass

                    with stats_lock:
                        stats["valid_count"] += 1
                        stats["nitro_count"] += 1
                        stats["total_unused_boosts"] += unused_slots
                        stats["total_used_boosts"] += used_slots

                    with PRINT_LOCK:
                        print(f"{ts()} {bcolors.PURPLE}+{bcolors.ENDC} {bcolors.WHITE}[{identifier}] | {bcolors.OKGREEN}(Valid){bcolors.ENDC} {bcolors.PURPLE}(Nitro){bcolors.ENDC} {bcolors.WHITE}| Boosts: {unused_slots} Unused, {used_slots} Used | Expires: {days_left}{bcolors.ENDC}")

                    with FILE_LOCK:
                        with open(SCRIPT_DIR / "output" / "valid.txt", "a", encoding="utf-8") as f:
                            f.write(original_line + "\n")
                        with open(SCRIPT_DIR / "output" / "nitro.txt", "a", encoding="utf-8") as f:
                            f.write(f"{original_line} | Nitro | Boosts: {unused_slots} Unused, {used_slots} Used | Expires: {days_left}\n")

                else:
                    # Valid Non-Nitro Token
                    with stats_lock:
                        stats["valid_count"] += 1
                        stats["no_nitro_count"] += 1

                    with PRINT_LOCK:
                        print(f"{ts()} {bcolors.OKGREEN}+{bcolors.ENDC} {bcolors.WHITE}[{identifier}] | {bcolors.OKGREEN}(Valid){bcolors.ENDC} {bcolors.YELLOW}(No Nitro){bcolors.ENDC}")

                    with FILE_LOCK:
                        with open(SCRIPT_DIR / "output" / "valid.txt", "a", encoding="utf-8") as f:
                            f.write(original_line + "\n")
                        with open(SCRIPT_DIR / "output" / "no_nitro.txt", "a", encoding="utf-8") as f:
                            f.write(original_line + "\n")

            else:
                # Unexpected status code -> Invalid
                with stats_lock:
                    stats["invalid_count"] += 1
                with PRINT_LOCK:
                    print(f"{ts()} {bcolors.FAIL}-{bcolors.ENDC} {bcolors.WHITE}[{identifier}] | {bcolors.FAIL}(Invalid: HTTP {me_res.status_code}){bcolors.ENDC}")
                with FILE_LOCK:
                    with open(SCRIPT_DIR / "output" / "invalid.txt", "a", encoding="utf-8") as f:
                        f.write(original_line + "\n")

        except Exception as e:
            with stats_lock:
                stats["invalid_count"] += 1
            with PRINT_LOCK:
                print(f"{ts()} {bcolors.FAIL}-{bcolors.ENDC} {bcolors.WHITE}[{identifier}] | {bcolors.FAIL}(Invalid: {e}){bcolors.ENDC}")
            with FILE_LOCK:
                with open(SCRIPT_DIR / "output" / "invalid.txt", "a", encoding="utf-8") as f:
                    f.write(original_line + "\n")

    def run_check(self, token_file: Path):
        """Execute multithreaded token checking against a file"""
        self.reload_config()
        token_entries = self.load_tokens_from_file(token_file)
        if not token_entries:
            log_error(f"No valid tokens found in {token_file}")
            input(log_input("Press Enter to return..."))
            return

        log_info(f"Loaded {len(token_entries)} tokens from {token_file.name}")
        
        thread_input = input(log_input(f"Enter thread count (default {self.thread_count}): ")).strip()
        threads = int(thread_input) if thread_input.isdigit() and int(thread_input) > 0 else self.thread_count
        threads = max(1, min(threads, 50))

        if self.proxy_mode:
            self.proxies = load_proxies()
            if self.proxies:
                log_info(f"Proxy mode enabled — loaded {len(self.proxies)} proxies")
            else:
                log_warn("Proxy mode enabled but input/proxies.txt is empty; continuing direct")

        # Clear/initialize output files for fresh run
        for out_name in ["valid.txt", "nitro.txt", "no_nitro.txt", "locked.txt", "invalid.txt"]:
            out_path = SCRIPT_DIR / "output" / out_name
            with open(out_path, "w", encoding="utf-8") as f:
                pass

        print()
        log_info(f"Checking {len(token_entries)} tokens with {threads} threads...")
        print()

        stats = {
            "valid_count": 0,
            "nitro_count": 0,
            "no_nitro_count": 0,
            "locked_count": 0,
            "invalid_count": 0,
            "total_unused_boosts": 0,
            "total_used_boosts": 0
        }
        stats_lock = threading.Lock()

        proxy_cycle = itertools.cycle(self.proxies) if self.proxy_mode and self.proxies else None

        with ThreadPoolExecutor(max_workers=threads) as executor:
            futures = []
            for idx, entry in enumerate(token_entries, 1):
                proxy = next(proxy_cycle, None) if proxy_cycle else None
                futures.append(
                    executor.submit(
                        self.check_single_token,
                        idx,
                        entry,
                        proxy,
                        stats,
                        stats_lock
                    )
                )
                time.sleep(0.05)

            for future in as_completed(futures):
                try:
                    future.result(timeout=120)
                except Exception:
                    pass
                with stats_lock:
                    update_title(
                        valid=stats["valid_count"],
                        nitro=stats["nitro_count"],
                        locked=stats["locked_count"],
                        invalid=stats["invalid_count"]
                    )

        print()
        log_success(
            f"Done | Total: {len(token_entries)} | Valid: {stats['valid_count']} "
            f"(Nitro: {stats['nitro_count']}, No Nitro: {stats['no_nitro_count']}) | "
            f"Locked: {stats['locked_count']} | Invalid: {stats['invalid_count']} | "
            f"Unused Boosts: {stats['total_unused_boosts']}"
        )
        log_info(f"Results categorized and saved in {SCRIPT_DIR / 'output'}")

        if self.config.get("remove_bad_tokens_from_input", False):
            try:
                valid_path = SCRIPT_DIR / "output" / "valid.txt"
                if valid_path.exists():
                    with open(valid_path, "r", encoding="utf-8") as vf:
                        valid_content = vf.read()
                    with open(token_file, "w", encoding="utf-8") as tf:
                        tf.write(valid_content)
                    log_info(f"Updated {token_file.name} (removed invalid/locked tokens)")
            except Exception as e:
                log_warn(f"Could not update {token_file.name}: {e}")

        input(log_input("Press Enter to return..."))


def display_menu(proxy_mode: bool) -> str:
    """Display clean bankroll token checker menu"""
    term_width = shutil.get_terminal_size((80, 20)).columns
    subtitle = "Bankroll | Advanced Token & Nitro Checker"
    pad = max(0, (term_width - len(subtitle)) // 2)
    proxy_status = f"{bcolors.OKGREEN}ENABLED{bcolors.ENDC}" if proxy_mode else f"{bcolors.FAIL}DISABLED{bcolors.ENDC}"
    print(f"{bcolors.TIME}{' ' * pad}{subtitle}{bcolors.ENDC}")
    print()
    print(f"{bcolors.MAGENTA}[1]{bcolors.ENDC} Check Default File (input/tokens.txt)")
    print(f"{bcolors.MAGENTA}[2]{bcolors.ENDC} Check Custom File")
    print(f"{bcolors.MAGENTA}[3]{bcolors.ENDC} Toggle Proxy Mode (Current: {proxy_status})")
    print(f"{bcolors.MAGENTA}[0]{bcolors.ENDC} Exit")
    print()
    return input(log_input("Choice: ")).strip()


def main():
    """Main application loop"""
    setup_folders()
    cfg = load_config()
    checker = TokenChecker(cfg)

    while True:
        clear_console()
        print_banner()
        choice = display_menu(checker.proxy_mode)

        if choice == "0":
            break
        elif choice == "1":
            checker.run_check(SCRIPT_DIR / "input" / "tokens.txt")
        elif choice == "2":
            custom_path = input(log_input("Enter tokens file path: ")).strip().strip('"').strip("'")
            if custom_path:
                checker.run_check(Path(custom_path))
            else:
                log_error("Invalid file path")
                input(log_input("Press Enter to return..."))
        elif choice == "3":
            cfg = load_config()
            cfg["proxy_mode"] = not cfg.get("proxy_mode", False)
            with open(SCRIPT_DIR / "config.json", "w", encoding="utf-8") as f:
                json.dump(cfg, f, indent=4)
            checker.reload_config()
            status_str = "ENABLED" if checker.proxy_mode else "DISABLED"
            log_info(f"Proxy Mode is now {status_str}")
            time.sleep(1)


if __name__ == "__main__":
    main()
