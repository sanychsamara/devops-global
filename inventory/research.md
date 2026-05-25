# research

Single-VM project — a Linux VM for web-scraping / research work.

## Pointers

- **Code:** `C:\Develop\research\devops` — repo <https://github.com/sanychsamara/research>
- **VM lifecycle:** created & managed by the **proxmox-devops** factory in this repo →
  [`../proxmox/README.md`](../proxmox/README.md)
- **Tailscale:** `scrape-research.flamingo-banjo.ts.net`

## VM: scrape-research

| Field | Value |
|-------|-------|
| Platform | Proxmox node `proxmox`, vmid **101** |
| OS | Ubuntu 24.04 LTS (cloud image, cloned from template 9000) |
| Resources | 2 vCPU · 2 GB RAM · 20 GB disk (`local-lvm`) |
| Tailscale | `scrape-research.flamingo-banjo.ts.net` · `100.96.143.45` |
| LAN | `192.168.1.192` (DHCP on `vmbr0`) |
| Login | `ssh ubuntu@scrape-research.flamingo-banjo.ts.net` — key-based (no password); root via `sudo -i` |
| Backups | weekly `vzdump` → `NAS1`, Sun 03:00, keep-weekly=4 |

## Operations

```bash
# from the devops-global repo root
python proxmox/proxmox-devops/proxmox-devops.py status
python proxmox/proxmox-devops/proxmox-devops.py snapshot 101 --name pre-change
python proxmox/proxmox-devops/proxmox-devops.py backup   101 --now
python proxmox/proxmox-devops/proxmox-devops.py destroy  101 --yes      # then recreate with `create`
```
