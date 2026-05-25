# aperil

`aperil-bot` — runs on the **Synology NAS** (⚠️ **not** Proxmox, so it is *not*
managed by the proxmox-devops factory).

## Pointers

- **Code:** `C:\Develop\aperil\devops` — repo <https://github.com/sanychsamara/aperil>
- **Tailscale:** `aperil.flamingo-banjo.ts.net` · `100.110.104.89`
- **Platform:** Synology NAS

## Host: aperil-bot

| Field | Value |
|-------|-------|
| Platform | Synology NAS |
| Tailscale | `aperil.flamingo-banjo.ts.net` · `100.110.104.89` |
| Deploy | TBD — document how it's deployed (Docker / Container Manager / Synology VM) |
| Login | TBD |
| Data / volumes | TBD |

## Notes

- Has its own Tailscale node (`aperil`), distinct from `homenas` — likely a container or
  VM on the Synology with Tailscale running inside it. Confirm whether it's the same
  physical Synology as `homenas`.
- Fill in: deploy method, exposed ports, persistent data paths, restart/update procedure.
