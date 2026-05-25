# home-assistant

Home Assistant — home automation. Runs on the **Synology NAS** (`homenas`).
**No custom code and no deploy scripts** — managed entirely through the Home
Assistant + Synology UIs.

## Pointers

- **Code:** none (no repo / no IaC)
- **Tailscale:** `homenas.flamingo-banjo.ts.net` · `100.85.234.68`
- **Platform:** Synology NAS `homenas`

## Host: Home Assistant

| Field | Value |
|-------|-------|
| Platform | Synology NAS `homenas` |
| Tailscale | `homenas.flamingo-banjo.ts.net` · `100.85.234.68` |
| Deploy | none — configured in-app on the Synology (HA OS VM or container) |
| Backups | TBD — HA has built-in backups; note where they're stored |

## Notes

- `homenas` is the Synology box itself; Home Assistant runs on it.
- Nothing to build/deploy from a repo — this entry exists for inventory completeness.
