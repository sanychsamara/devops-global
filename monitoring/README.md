# Homelab monitoring (lightweight, agentless)

Non-critical resource monitoring for the VM/host inventory — **no dashboard, no
database, no SaaS**. Collects per-host CPU / memory / disk / network / uptime,
writes a daily JSON snapshot, and produces a plain-English right-sizing report
(should I add RAM/CPU/disk to a VM?).

## How it collects (cheapest source per host)

| Host(s) | Source | Agent? |
|---------|--------|--------|
| Proxmox VMs (`scrape-research`, `betbot`) | Proxmox API **RRD week average** + QEMU guest agent (in-guest disk) | none |
| Synology `homenas` (also runs Home Assistant + aperil-bot) | **SNMPv3** (SHA, authNoPriv) | native DSM SNMP |
| Other Linux hosts (`manus-sandbox`) | **SSH** one-shot metrics (loadavg/mem/disk/uptime) | none — needs non-interactive SSH |

> **SSH hosts** are set in `MON_SNMP`-style `MON_SSH_HOSTS=name=user@host`. The monitor VM
> must reach them over SSH **without an interactive prompt**. For Tailscale SSH hosts in
> check-mode (e.g. `manus-sandbox`), a headless node can't complete the browser check — add
> a Tailscale ACL `ssh` rule with `"action": "accept"` (no check) for the monitor node →
> host. Container metrics (loadavg/mem) may reflect the host, not cgroup limits.

- Proxmox gives true week **averages + peaks** (sampled ~every 30 min). Synology
  SNMP is **point-in-time** at each run — the daily snapshots build the trend.
- `aperil-bot` is a container on `homenas` with its own Tailscale node; it does not
  answer SNMP, so it shares `homenas` host metrics (no per-container figures).
- `betbot` has no QEMU guest agent yet, so only its *allocated* disk is known
  (host-side CPU/RAM/net still come from Proxmox).

## Usage

```bash
pip install -r monitoring/requirements.txt   # one-time, for the Synology SNMP part
python monitoring/monitor.py alert     # collect; Telegram ONLY if something is off (default)
python monitoring/monitor.py report    # collect + ALWAYS post the full report to Telegram
python monitoring/monitor.py check     # alias of report (always posts)
python monitoring/monitor.py snapshot  # collect to data/ only, no report, no Telegram
```

Every mode writes a daily snapshot to `data/`. `alert` is the default so accidental/manual
runs never spam the chat — they only message when there's an actionable finding.

Outputs:
- `monitoring/data/YYYY-MM-DD.json` — raw normalized snapshot (history; no DB).
- `monitoring/reports/YYYY-MM-DD.md` — human-readable report + recommendations.

## Deployment — the `monitor` VM (vmid 102)

The homelab is reachable **only on the Tailscale tailnet** (a cloud runner can't reach
it), so collection runs unattended on a tiny always-on VM on the tailnet:
`monitor.flamingo-banjo.ts.net` (1 vCPU / 1 GB / 10 GB, built by the factory).

On the VM:
- `~/mon/{monitor.py,snmp.py,client.py,.env}` + a `~/mon/venv` (with `pysnmp`).
- `crontab`: daily **`alert`** (08:00 UTC — Telegram only if something is off) and weekly
  **`analyze.py`** (Mon 08:10 UTC — LLM narrative report → Telegram). Logs to `~/mon/cron.log`.

Update the code on the VM after changing it here:
```bash
scp monitoring/monitor.py monitoring/snmp.py proxmox/proxmox-devops/client.py \
    ubuntu@monitor.flamingo-banjo.ts.net:~/mon/
```

## Delivery — Telegram

Two channels only — no per-run spam: the **daily `alert`** posts to the `MON_TELEGRAM_CHAT`
group *only when something is off* (RAM tight, disk high, host unreachable, …), and the
**weekly LLM narrative** (`analyze.py`, Mondays) is the regular report. `monitor.py report`
posts the full rules-based report on demand. Full detail always lands in `reports/*.md`.
Bot token is `MON_TELEGRAM_TOKEN`.

## Weekly LLM analysis

`analyze.py` (weekly, after `check`) reads the last ~7 daily snapshots, asks an Anthropic
model **via OpenRouter** for a concise right-sizing narrative, and posts it to Telegram.
Auth: `OPENROUTER_API_KEY` (read from the environment, or from `.env`). Model defaults to
`anthropic/claude-haiku-4.5` (cheap — set `MON_LLM_MODEL` to override). Stdlib HTTP, no
SDK; skips silently if the key is unset.

## Config & secrets

In `proxmox/.env` (gitignored):
- `MON_SNMP_USER`, `MON_SNMP_AUTH` — Synology SNMPv3 credentials.
- `MON_SNMP_HOSTS` — comma-separated `name=ip` (Tailscale IPs), e.g. `homenas=100.85.234.68`.

## Thresholds (edit in `monitor.py`)

- RAM: ≥80% avg (or ≥90% peak) → increase; ≥70% → watch; ≤30% → over-provisioned.
- CPU: ≥60% avg (or ≥90% peak) → add vCPU; ≤5% → over-provisioned.
- Disk: ≥90% → grow soon; ≥80% → watch.

## Roadmap / TODO

- [ ] git-push snapshots from the VM for versioned history (optional; needs a GitHub token on the VM).
- [ ] Install QEMU guest agent on `betbot` for in-guest free disk + guest-level RAM (needs VM shell access).
