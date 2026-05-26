# Homelab Inventory — VMs & Hosts

All hosts are on the **flamingo-banjo** tailnet (`*.flamingo-banjo.ts.net`); prefer
Tailscale names/IPs over LAN IPs. One Markdown file per project in this folder has
the details and pointers.

_Last updated: 2026-05-25._

| Project | Host | Platform | Tailscale (IP) | Specs | Role |
|---------|------|----------|----------------|-------|------|
| [research](research.md) | **scrape-research** | Proxmox `proxmox` · vmid 101 | scrape-research.flamingo-banjo.ts.net · 100.96.143.45 (LAN 192.168.1.192) | Ubuntu 24.04 · 2 vCPU · 2 GB · 20 GB | web-scraping / research VM |
| [aperil](aperil.md) | **aperil-bot** | Synology NAS (⚠️ not Proxmox) | aperil.flamingo-banjo.ts.net · 100.110.104.89 | TBD | aperil bot |
| [betbot](betbot.md) | **betbot** | Proxmox `proxmox` · vmid 100 | betbot.flamingo-banjo.ts.net · 100.100.152.29 | Linux · 4 vCPU · 8 GB · 100 GB | Kalshi betting bot |
| [home-assistant](home-assistant.md) | **Home Assistant** | Synology `homenas` | homenas.flamingo-banjo.ts.net · 100.85.234.68 | appliance | home automation |
| [monitoring](../monitoring/README.md) | **monitor** | Proxmox `proxmox` · vmid 102 | monitor.flamingo-banjo.ts.net · 100.120.34.88 | Ubuntu 24.04 · 1 vCPU · 2 GB · 10 GB | metrics collector (cron → Telegram) |
| [manus-sandbox](manus-sandbox.md) | **manus-sandbox** | GCP VM `cloud-pc-9ga3ux78` (Manus; not Proxmox) | manus-sandbox-1.flamingo-banjo.ts.net · 100.116.125.109 (public 136.118.155.212) | Linux · ~4 GB · 67 GB | Manus operator VM / handoff target (monitored) |

## Platforms at a glance

- **Proxmox** (node `proxmox`, reached at `proxmox.flamingo-banjo.ts.net`): `scrape-research` (101), `betbot` (100), `monitor` (102, the metrics collector).
  - `scrape-research` is created/managed by the **proxmox-devops** factory in this repo — see [`../proxmox/README.md`](../proxmox/README.md).
  - `betbot` predates the factory (manually built, no guest agent).
- **Synology NAS**: `aperil-bot` (own Tailscale node `aperil`), Home Assistant (on `homenas`). Not managed by the Proxmox factory.

> Legend: "TBD" = not yet documented. Fill in as details are confirmed.
