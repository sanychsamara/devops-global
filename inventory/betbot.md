# betbot

Kalshi betting bot. Runs on Proxmox.

## Pointers

- **Code:** `C:\Develop\betbot\devops` — repo <https://github.com/sanychsamara/betbot>
- **Tailscale:** `betbot.flamingo-banjo.ts.net` · `100.100.152.29`
- **Platform:** Proxmox node `proxmox`, vmid **100**

## VM: betbot

| Field | Value |
|-------|-------|
| Platform | Proxmox node `proxmox`, vmid **100** |
| OS | Linux (`ostype=l26`) |
| Resources | 4 vCPU · 8 GB RAM · 100 GB disk (`local-lvm`) |
| Network | `vmbr0` (e1000), **autostarts** (`onboot=1`) |
| Tailscale | `betbot.flamingo-banjo.ts.net` · `100.100.152.29` |
| Login | TBD — predates the proxmox-devops factory; document the user + SSH auth |
| Backups | TBD — no factory-managed backup job yet |

## Notes

- **2026-05-25:** RAM increased 2 GB → 4 GB → 8 GB (it was running ~77% on 2 GB); the VM was
  rebooted (graceful Proxmox reboot) to apply each bump. Proxmox confirms 8192 MB allocated.
- Manually created VM (not cloned from template 9000), and **no QEMU guest agent**, so
  the factory CLI can't read its IP automatically.
- It can still be backed up via the factory if desired:
  `python proxmox/proxmox-devops/proxmox-devops.py backup 100 --now`
  (or register a weekly job).
