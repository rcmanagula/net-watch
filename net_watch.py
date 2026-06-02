#!/usr/bin/env python3
"""
net-watch: alerts you the moment internet connectivity is restored.
Polls fast while down, slow while up. No external dependencies.
"""

import os
import socket
import time
import sys
import re
import platform
import unicodedata
from datetime import datetime

# Hosts to test (host, port). DNS servers on port 53 = reliable, fast, ICMP-independent.
TEST_TARGETS = [
    ("8.8.8.8", 53),    # Google DNS
    ("1.1.1.1", 53),    # Cloudflare DNS
    ("8.8.4.4", 53),    # Google DNS secondary
]

CONNECT_TIMEOUT = 2.0     # seconds per connection attempt
POLL_WHEN_UP = 15         # seconds between checks while internet is up
POLL_WHEN_DOWN = 3        # seconds between checks while down (fast, to catch restore quickly)

VERBOSE = False           # set by -v / --verbose; prints each connectivity probe

# ---------------------------------------------------------------------------
# COLOR (pure ANSI, no dependencies). Disabled automatically when output is
# not a terminal, or via the --no-color flag. Semantic palette:
#   green = online / OK,  red = offline / fail,  yellow = warnings,
#   cyan = headings,      dim = timestamps & detail.
# ---------------------------------------------------------------------------
USE_COLOR = True


class C:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    RED = "\033[91m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    CYAN = "\033[96m"
    GRAY = "\033[90m"


def _enable_windows_ansi():
    """Turn on ANSI escape processing in legacy Windows consoles (conhost)."""
    try:
        import ctypes
        kernel32 = ctypes.windll.kernel32
        # ENABLE_VIRTUAL_TERMINAL_PROCESSING = 0x0004 on STD_OUTPUT_HANDLE (-11)
        kernel32.SetConsoleMode(kernel32.GetStdHandle(-11), 7)
    except Exception:
        pass  # best effort; modern terminals already support ANSI


def color(text, *styles):
    """Wrap text in ANSI styles, or return it plain when color is disabled."""
    if not USE_COLOR or not styles:
        return text
    return "".join(styles) + text + C.RESET


_ANSI_RE = re.compile(r"\033\[[0-9;]*m")


def vis_len(text):
    """Visible column width of text: strips ANSI codes, counts wide glyphs as 2."""
    plain = _ANSI_RE.sub("", text)
    return sum(2 if unicodedata.east_asian_width(ch) in ("W", "F") else 1 for ch in plain)


def vlog(msg, *styles):
    """Print a dim-timestamped line only when verbose mode is on."""
    if VERBOSE:
        ts = color(f"[{datetime.now():%H:%M:%S}]", C.GRAY)
        print(f"{ts} {color(msg, *styles) if styles else msg}")

# ---------------------------------------------------------------------------
# PHONE NOTIFICATION
# Configuration is read from environment variables so no secrets ever live in
# source control. Set them in your shell (or a local .env you do NOT commit).
#
# Pick a backend with NET_WATCH_BACKEND = "ntfy", "telegram", or "" (disabled).
#
# ntfy (recommended, free, no account):
#   1. Install the "ntfy" app (Android Play Store / iOS App Store).
#   2. Set NTFY_TOPIC to something private and random.
#      (Anyone who knows the topic name can read it, so make it unguessable.)
#   3. In the app, tap + and subscribe to that exact topic name.
#
# telegram (free, needs one-time bot setup):
#   1. Message @BotFather, send /newbot, copy the token into TELEGRAM_TOKEN.
#   2. Message your new bot once, then open
#      https://api.telegram.org/bot<TOKEN>/getUpdates to find your chat id.
#
# Example (PowerShell):   $env:TELEGRAM_TOKEN="123456:ABC..."; $env:TELEGRAM_CHAT_ID="987654321"
# Example (bash):         export TELEGRAM_TOKEN="123456:ABC..." TELEGRAM_CHAT_ID="987654321"
# ---------------------------------------------------------------------------
PHONE_BACKEND = os.environ.get("NET_WATCH_BACKEND", "telegram")   # "ntfy", "telegram", or "" to disable

NTFY_SERVER = os.environ.get("NTFY_SERVER", "https://ntfy.sh")
NTFY_TOPIC = os.environ.get("NTFY_TOPIC", "net-watch-CHANGE-ME-x7q2")   # change to something random

# NEVER hardcode real secrets here. Provide them via environment variables.
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN", "")       # e.g. "123456:ABC-DEF..."
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")   # e.g. "987654321"

IS_WINDOWS = platform.system() == "Windows"
if IS_WINDOWS:
    import winsound


def is_online():
    """Return True if any test target is reachable.

    Connectivity is tested by opening a real TCP connection to a DNS server
    on port 53 (not ICMP ping). In verbose mode every probe is logged so you
    can see exactly what network traffic is being sent.
    """
    for host, port in TEST_TARGETS:
        try:
            vlog(f"  {color('probe', C.CYAN)} -> TCP {color(f'{host}:{port}', C.BOLD)} "
                 f"{color(f'(timeout {CONNECT_TIMEOUT}s) ...', C.DIM)}")
            start = time.time()
            with socket.create_connection((host, port), timeout=CONNECT_TIMEOUT):
                ms = (time.time() - start) * 1000
                vlog(f"    {color('OK  ', C.GREEN, C.BOLD)} {host}:{port} reachable in "
                     f"{color(f'{ms:.0f} ms', C.GREEN)}")
                return True
        except OSError as e:
            ms = (time.time() - start) * 1000
            vlog(f"    {color('FAIL', C.RED, C.BOLD)} {host}:{port} after {ms:.0f} ms "
                 f"{color(f'({e})', C.DIM)}")
            continue
    vlog(f"  {color('all targets unreachable -> OFFLINE', C.RED)}")
    return False


def notify_phone(title, message, retries=3):
    """Send a push to the phone. Retries briefly since the link just came back."""
    if not PHONE_BACKEND:
        return
    import urllib.request
    import urllib.parse

    for attempt in range(retries):
        try:
            if PHONE_BACKEND == "ntfy":
                req = urllib.request.Request(
                    f"{NTFY_SERVER}/{NTFY_TOPIC}",
                    data=message.encode("utf-8"),
                    headers={"Title": title, "Priority": "high", "Tags": "white_check_mark"},
                )
                urllib.request.urlopen(req, timeout=10)

            elif PHONE_BACKEND == "telegram":
                params = urllib.parse.urlencode({
                    "chat_id": TELEGRAM_CHAT_ID,
                    "text": f"{title}\n{message}",
                }).encode("utf-8")
                url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
                urllib.request.urlopen(urllib.request.Request(url, data=params), timeout=10)

            print("  (phone notified)")
            return
        except Exception as e:
            if attempt < retries - 1:
                time.sleep(2)
            else:
                print(f"  (phone notify failed after {retries} tries: {e})")


def alert_restored(downtime_seconds):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    mins, secs = divmod(int(downtime_seconds), 60)
    msg = f"INTERNET RESTORED at {ts} (was down ~{mins}m {secs}s)"
    line = color("=" * 60, C.GREEN)
    print("\a" + line)
    print(color("✔ " + msg, C.GREEN, C.BOLD))
    print(line)

    if IS_WINDOWS:
        for freq in (880, 1175, 1568, 1175, 880):
            winsound.Beep(freq, 200)
        _windows_toast("Internet Restored", msg)
    else:
        for _ in range(5):
            sys.stdout.write("\a")
            sys.stdout.flush()
            time.sleep(0.3)

    notify_phone("Internet Restored", msg)


def _windows_toast(title, message):
    import subprocess
    ps = f'''
    [Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType = WindowsRuntime] | Out-Null
    [Windows.UI.Notifications.ToastNotification, Windows.UI.Notifications, ContentType = WindowsRuntime] | Out-Null
    $t = [Windows.UI.Notifications.ToastNotificationManager]::GetTemplateContent([Windows.UI.Notifications.ToastTemplateType]::ToastText02)
    $x = $t.GetElementsByTagName("text")
    $x.Item(0).AppendChild($t.CreateTextNode("{title}")) | Out-Null
    $x.Item(1).AppendChild($t.CreateTextNode("{message}")) | Out-Null
    $toast = [Windows.UI.Notifications.ToastNotification]::new($t)
    [Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier("net-watch").Show($toast)
    '''
    try:
        subprocess.run(["powershell", "-NoProfile", "-Command", ps],
                       capture_output=True, timeout=10)
    except Exception:
        pass  # toast is best-effort; beep already fired


def run_test():
    """Fire a sample alert (local + phone) to verify setup without a real outage."""
    print("Running notification test...")
    print(f"Phone backend: {PHONE_BACKEND or 'disabled'}")
    if PHONE_BACKEND == "ntfy":
        print(f"  ntfy topic: {NTFY_TOPIC}")
    elif PHONE_BACKEND == "telegram":
        ok = bool(TELEGRAM_TOKEN and TELEGRAM_CHAT_ID)
        print(f"  telegram token set: {bool(TELEGRAM_TOKEN)}, chat id set: {bool(TELEGRAM_CHAT_ID)}")
        if not ok:
            print("  WARNING: TELEGRAM_TOKEN / TELEGRAM_CHAT_ID look empty. Fill them in first.")
    print()
    alert_restored(0)
    print("\nTest done. Check your phone for the notification.")


def print_banner(online):
    """Boxed, colored startup banner with a live status line."""
    state = (color("ONLINE", C.GREEN, C.BOLD) if online
             else color("OFFLINE", C.RED, C.BOLD))
    rows = [
        f"{color('⚡ NET-WATCH', C.CYAN, C.BOLD)}   {color('internet restore monitor', C.DIM)}",
        f"status:   {state}",
        f"watching: {color(', '.join(f'{h}:{p}' for h, p in TEST_TARGETS), C.GRAY)}",
    ]

    # Size the box to the longest row so the border always lines up.
    PAD = 2  # spaces of inner margin on each side
    inner = max(vis_len(r) for r in rows) + PAD * 2

    top = color("╔" + "═" * inner + "╗", C.CYAN)
    bot = color("╚" + "═" * inner + "╝", C.CYAN)
    bar = color("║", C.CYAN)

    print(top)
    for content in rows:
        trail = inner - PAD - vis_len(content)
        print(f"{bar}{' ' * PAD}{content}{' ' * max(trail, 0)}{bar}")
    print(bot)
    if VERBOSE:
        print(color("verbose mode ON: every connectivity probe will be printed.", C.YELLOW))
    print(color("Press Ctrl+C to stop.", C.DIM) + "\n")


def main():
    online = is_online()
    print_banner(online)

    down_since = None
    state = color("ONLINE", C.GREEN, C.BOLD) if online else color("OFFLINE", C.RED, C.BOLD)
    ts = color(f"[{datetime.now():%H:%M:%S}]", C.GRAY)
    print(f"{ts} Initial state: {state}")

    try:
        while True:
            current = is_online()

            if current and not online:                       # down -> up
                downtime = time.time() - down_since if down_since else 0
                alert_restored(downtime)
                down_since = None
            elif not current and online:                     # up -> down
                down_since = time.time()
                ts = color(f"[{datetime.now():%H:%M:%S}]", C.GRAY)
                print(f"{ts} {color('✖ Connection LOST.', C.RED, C.BOLD)} "
                      f"{color('Watching for restore...', C.YELLOW)}")

            online = current
            delay = POLL_WHEN_UP if online else POLL_WHEN_DOWN
            st = color("ONLINE", C.GREEN) if online else color("OFFLINE", C.RED)
            vlog(f"  state={st}{color(';', C.DIM)} next check in {color(f'{delay}s', C.CYAN)}")
            time.sleep(delay)

    except KeyboardInterrupt:
        print("\nnet-watch stopped.")


if __name__ == "__main__":
    if "-h" in sys.argv or "--help" in sys.argv:
        print("Usage: net_watch.py [-v|--verbose] [--no-color] [--test]")
        print("  -v, --verbose   print every connectivity probe (target, result, timing)")
        print("  --no-color      disable colored output")
        print("  --test          send a sample alert to verify notifications")
        sys.exit(0)

    VERBOSE = "-v" in sys.argv or "--verbose" in sys.argv

    # Ensure box-drawing chars / emoji print on legacy (cp1252) Windows consoles.
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

    # Color on by default; off if asked, or if output is being piped/redirected.
    USE_COLOR = "--no-color" not in sys.argv and sys.stdout.isatty()
    if USE_COLOR and IS_WINDOWS:
        _enable_windows_ansi()

    if "--test" in sys.argv:
        run_test()
    else:
        main()
