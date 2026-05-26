# manus-sandbox

Permanent sandbox attached to the **Manus** AI agent. No projects of ours run here yet —
kept as a **handoff target** for delegating work to another agent.

## Pointers

- **Tailscale:** `manus-sandbox.flamingo-banjo.ts.net` · `100.91.181.84`
- **Platform:** containerized Linux sandbox (hostname `41263648be78`, kernel 6.1.102),
  managed by Manus — **not** on our Proxmox.
- **Owner:** Manus agent (external).

## Access

- **SSH as `root` via Tailscale SSH** — authenticated by **tailnet identity, not your SSH key**:
  ```bash
  ssh root@manus-sandbox.flamingo-banjo.ts.net
  ```
  Port 22 is served by Tailscale SSH (no OpenSSH banner). The first connect triggers a
  Tailscale browser check; once approved, the session opens as `root`.
- Verified 2026-05-25: reachable on the tailnet; Tailscale SSH login as `root` works
  interactively. Your private key is **not** used (Tailscale SSH brokers auth).

## Notes

- Use for handing off tasks to Manus; document any project that lands here.
- **Monitoring:** wired into the monitor VM as an SSH-pull host (`MON_SSH_HOSTS`). It will
  start reporting once a Tailscale ACL `ssh` rule with `"action": "accept"` (no check) lets
  the **headless** `monitor` node SSH in as `root` — check-mode needs a browser approval the
  monitor node can't do, so until then it shows "unreachable". See `monitoring/README.md`.
