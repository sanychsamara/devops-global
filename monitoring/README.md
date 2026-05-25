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

- Proxmox gives true week **averages + peaks** (sampled ~every 30 min). Synology
  SNMP is **point-in-time** at each run — the daily snapshots build the trend.
- `aperil-bot` is a container on `homenas` with its own Tailscale node; it does not
  answer SNMP, so it shares `homenas` host metrics (no per-container figures).
- `betbot` has no QEMU guest agent yet, so only its *allocated* disk is known
  (host-side CPU/RAM/net still come from Proxmox).

## Usage

```bash
pip install -r monitoring/requirements.txt        # one-time, for the Synology SNMP part
python monitoring/monitor.py check                # snapshot + report
python monitoring/monitor.py snapshot             # data/YYYY-MM-DD.json only
python monitoring/monitor.py report               # reports/YYYY-MM-DD.md only
```

Outputs:
- `monitoring/data/YYYY-MM-DD.json` — raw normalized snapshot (history; no DB).
- `monitoring/reports/YYYY-MM-DD.md` — human-readable report + recommendations.

## Deployment — the `monitor` VM (vmid 102)

The homelab is reachable **only on the Tailscale tailnet** (a cloud runner can't reach
it), so collection runs unattended on a tiny always-on VM on the tailnet:
`monitor.flamingo-banjo.ts.net` (1 vCPU / 1 GB / 10 GB, built by the factory).

On the VM:
- `~/mon/{monitor.py,snmp.py,client.py,.env}` + a `~/mon/venv` (with `pysnmp`).
- `crontab`: daily `snapshot` (08:00 UTC) and weekly `check` (Mon 08:05 UTC → Telegram).
  Logs to `~/mon/cron.log`.

Update the code on the VM after changing it here:
```bash
scp monitoring/monitor.py monitoring/snmp.py proxmox/proxmox-devops/client.py \
    ubuntu@monitor.flamingo-banjo.ts.net:~/mon/
```

## Delivery — Telegram

`check` posts a compact, actionable report to the Telegram group in `MON_TELEGRAM_CHAT`
via the bot token in `MON_TELEGRAM_TOKEN` (full detail stays in `reports/*.md`).

## Config & secrets

In `proxmox/.env` (gitignored):
- `MON_SNMP_USER`, `MON_SNMP_AUTH` — Synology SNMPv3 credentials.
- `MON_SNMP_HOSTS` — comma-separated `name=ip` (Tailscale IPs), e.g. `homenas=100.85.234.68`.

## Thresholds (edit in `monitor.py`)

- RAM: ≥80% avg (or ≥90% peak) → increase; ≥70% → watch; ≤30% → over-provisioned.
- CPU: ≥60% avg (or ≥90% peak) → add vCPU; ≤5% → over-provisioned.
- Disk: ≥90% → grow soon; ≥80% → watch.

## Roadmap / TODO

- [ ] Weekly **LLM narrative** analysis → Telegram (Anthropic API from the VM, or a
  scheduled cloud routine reading git-pushed snapshots). Needs a credential decision.
- [ ] git-push snapshots from the VM for versioned history (needs a GitHub token on the VM).
- [ ] Install QEMU guest agent on `betbot` for in-guest free disk (needs VM shell access).
