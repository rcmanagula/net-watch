# ⚡ net-watch

> A lightweight, zero-dependency connectivity monitor that pushes an alert to your phone **the moment your internet comes back**.

![Python](https://img.shields.io/badge/python-3.7%2B-blue)
![Dependencies](https://img.shields.io/badge/dependencies-none-success)
![Platform](https://img.shields.io/badge/platform-Windows%20%7C%20Linux%20%7C%20macOS-lightgrey)

```
╔════════════════════════════════════════════════╗
║  ⚡ NET-WATCH   internet restore monitor         ║
║  status:   ONLINE                                ║
║  watching: 8.8.8.8:53, 1.1.1.1:53, 8.8.4.4:53    ║
╚════════════════════════════════════════════════╝
```

---

## What it is

**net-watch** is a small Python program that continuously checks whether your internet
connection is alive. While the connection is up it checks quietly in the background.
The instant the link drops, it switches into fast-polling mode and watches for recovery —
and as soon as the internet is restored it fires off a loud local alert (sound + desktop
toast) **and a push notification to your phone** via Telegram or [ntfy](https://ntfy.sh).

It has **no third-party dependencies** — just the Python standard library — so it runs
anywhere Python runs and starts instantly.

## The problem

If you live in the Philippines, this scenario is painfully familiar:

> Your fiber connection (PLDT, Converge, Globe, Sky…) randomly goes down. Maybe it's a
> cut line, maybe a regional outage, maybe "scheduled maintenance" nobody told you about.
> You have **no idea** how long it'll be out, and **no way to know the moment it's back**.

When the fiber is down, most of us fall back to **mobile data** — which is expensive and
limited. So you're stuck in an annoying loop: every few minutes you toggle Wi-Fi, open a
browser, watch it fail, and switch back to data. You either **waste data** keeping a hotspot
running "just in case," or you **miss the restore window** entirely and stay on data far
longer than you needed to.

For anyone who **works from home and depends on fiber**, this is more than an annoyance —
it directly costs you productivity, billable hours, and mobile-data money. Video calls,
deployments, SSH sessions, and uploads all hinge on knowing the *exact* second your real
connection returns.

## The solution

net-watch removes the guesswork. Instead of you babysitting the connection, **it watches
for you**:

1. **While up** — it quietly probes every 15 seconds, staying out of your way.
2. **While down** — it polls fast (every 3 seconds) so it catches the recovery moment with
   minimal delay.
3. **On restore** — it instantly:
   - 🔊 plays an attention-grabbing sound,
   - 🖥️ pops a desktop notification (Windows toast),
   - 📱 **pushes a notification to your phone**, including how long the outage lasted.

Because the phone alert goes out over the *restored* connection (with brief retries), you
get pinged on your handset the moment fiber is usable again — even if you walked away from
your desk and are on mobile data.

### How it actually checks (not just `ping`)

net-watch does **not** rely on ICMP `ping`, which many networks rate-limit or block. Instead
it opens a **real TCP connection to public DNS servers on port 53** (Google `8.8.8.8`,
Cloudflare `1.1.1.1`). If a TCP handshake to *any* of them succeeds, you genuinely have
working internet — not just a router that's powered on. Run with `-v` to watch every probe,
its target, result, and latency in real time.

## Why it's useful

- **Stop wasting mobile data.** Know the instant fiber is back so you can switch off the
  hotspot immediately instead of "checking every 5 minutes."
- **Reclaim work-from-home productivity.** Get back online the second it's possible — no
  missed restore windows during outages.
- **Zero dependencies, instant setup.** Pure standard-library Python; clone and run.
- **Cross-platform.** Windows (with sound + toast), Linux, and macOS.
- **Secrets stay secret.** All credentials are read from environment variables — nothing
  sensitive is ever committed to the repo.

---

## Installation

```bash
git clone https://github.com/rcmanagula/net-watch.git
cd net-watch
```

Requires **Python 3.7+**. No `pip install` needed.

## Configuration

net-watch reads all settings from **environment variables** (see [`.env.example`](.env.example)
for the full list). Pick one notification backend:

### Option A — Telegram (free, reliable)

1. Open Telegram, message **@BotFather**, send `/newbot`, and copy the bot token.
2. Message your new bot once, then visit
   `https://api.telegram.org/bot<TOKEN>/getUpdates` to find your numeric chat id.
3. Set the variables:

```powershell
# Windows (PowerShell)
$env:NET_WATCH_BACKEND = "telegram"
$env:TELEGRAM_TOKEN    = "123456:ABC-DEF..."
$env:TELEGRAM_CHAT_ID  = "987654321"
```

```bash
# Linux / macOS
export NET_WATCH_BACKEND="telegram"
export TELEGRAM_TOKEN="123456:ABC-DEF..."
export TELEGRAM_CHAT_ID="987654321"
```

### Option B — ntfy (free, no account)

1. Install the **ntfy** app (Android / iOS).
2. Subscribe to a private, random topic name.
3. Configure:

```bash
export NET_WATCH_BACKEND="ntfy"
export NTFY_TOPIC="net-watch-your-random-topic"
```

> 💡 To keep settings between sessions, copy `.env.example` to `.env`, fill it in, and load
> it into your shell before running. `.env` is gitignored, so your secrets never leave your
> machine.

## Usage

```bash
python net_watch.py            # start monitoring (colored banner + quiet output)
python net_watch.py -v         # verbose: print every connectivity probe with timing
python net_watch.py --no-color # plain output (good for log files)
python net_watch.py --test     # send a sample alert to confirm your setup works
python net_watch.py --help     # show all options
```

Press **Ctrl+C** to stop.

### Verbose mode

```
[13:50:16]   probe -> TCP 8.8.8.8:53 (timeout 2.0s) ...
[13:50:16]     OK   8.8.8.8:53 reachable in 56 ms
[13:50:16]   state=ONLINE; next check in 15s
```

Green for healthy probes, red for failures, dim timestamps — so an outage is obvious at a
glance. Colors automatically turn off when output is piped to a file.

## How it works (at a glance)

| State        | Poll interval | Behavior                                            |
|--------------|---------------|-----------------------------------------------------|
| Internet up  | 15 s          | Quiet background checks                              |
| Internet down| 3 s           | Fast polling to catch the restore moment quickly     |
| Restored     | —             | Sound + desktop toast + phone push (with downtime)  |

Tunable constants live at the top of [`net_watch.py`](net_watch.py): `TEST_TARGETS`,
`CONNECT_TIMEOUT`, `POLL_WHEN_UP`, `POLL_WHEN_DOWN`.

## Security notes

This project is part of my security/pentesting portfolio, so it follows basic secure-by-default
hygiene:

- **No hardcoded secrets** — tokens and chat ids come from the environment only.
- **`.gitignore`** excludes `.env` and local scratch notes so credentials can't be committed
  by accident.
- Connectivity checks use **outbound TCP only** — no listening sockets, no elevated
  privileges, no ICMP raw-socket requirements.

## License

MIT — free to use, modify, and share.
