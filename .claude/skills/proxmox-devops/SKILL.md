---
name: proxmox-devops
description: >
  Create, list, snapshot, back up, or destroy Linux VMs on the user's Proxmox
  server ("alex proxmox") via the proxmox-devops CLI. TRIGGER when the user asks
  to spin up / create / make a new VM (e.g. "create an ubuntu VM, 2GB ram, 20GB
  disk, name scrape-research, setup tailscale, weekly backups"), or to list /
  delete / snapshot / back up Proxmox VMs.
---

# Proxmox DevOps VM factory

Drives `proxmox/proxmox-devops/proxmox-devops.py` against the user's Proxmox
node (reached over Tailscale at `proxmox.flamingo-banjo.ts.net`). Config lives in
`proxmox/.env`.

## Parsing the request

Map the user's words to flags:

| User says | Flag |
|-----------|------|
| name `X` / call it `X` | `--name X` |
| `2GB ram` / `2048MB` | `--ram 2048` (convert GB→MB: GB×1024) |
| `20GB disk` | `--disk 20` (GB) |
| `4 cpus` / `2 cores` | `--cores N` (default 2) |
| `cpu host` / `kvm64` / portable cpu | `--cpu <type>` (default `host`, which exposes AVX/AVX2 for NumPy) |
| `setup tailscale` / `on tailnet` | `--tailscale` (zero-touch, default) |
| `give me a login link` / `tailscale login url` | `--tailscale-url` (instead of `--tailscale`) |
| `weekly backups` / `backup it` | `--backup weekly` |
| ubuntu (any) | template default (Ubuntu 24.04); no flag needed |

Defaults if unspecified: `--ram 2048 --cores 2 --disk 20`, no tailscale, no backup.

## How to run it

From the repo root:

```
python proxmox/proxmox-devops/proxmox-devops.py create --name <name> --ram <MB> --cores <N> --disk <GB> [--tailscale|--tailscale-url] [--backup weekly]
```

Other actions:
- List: `python proxmox/proxmox-devops/proxmox-devops.py status`
- Snapshot: `python proxmox/proxmox-devops/proxmox-devops.py snapshot <vmid> --name <snap>`
- Backup now / schedule: `python proxmox/proxmox-devops/proxmox-devops.py backup <vmid> [--now | --schedule "sun 03:00"]`
- Destroy (irreversible — always confirm with the user first): `python proxmox/proxmox-devops/proxmox-devops.py destroy <vmid> --yes`

## Before running

1. Confirm `proxmox/.env` exists with a valid `PVE_TOKEN_SECRET` (and `TS_AUTHKEY`
   if tailscale is requested). If not, point the user to `proxmox/setup/00-create-api-token.md`.
2. The one-time template + snippets setup (`proxmox/setup/10-build-template.sh`,
   `20-enable-snippets.sh`) must have been run on the node. If `status` shows no
   template (VMID 9000), the user needs to run setup first.

## After running

Report back what the CLI prints: the **VMID**, **LAN IP**, **Tailscale name/IP**
(or the **login URL** for `--tailscale-url`), the **SSH command**, and whether
backups were scheduled. Never invent an IP — relay exactly what the tool returned.

## Safety

- `destroy` deletes the VM and its disks. Always confirm the target VMID with the
  user and only pass `--yes` after explicit confirmation.
- This skill targets the user's own authorized homelab. Do not point it at other hosts.
