# manus-sandbox

The **always-on VM that runs the Manus agent** (its `manus-computer-operator` process).
Kept as a **handoff target** for delegating work to Manus. No projects of ours run here.

## Pointers

- **Platform:** GCP VM — hostname `cloud-pc-9ga3ux78`, kernel `6.17.0-gcp`, ~4 GB RAM /
  67 GB disk. Always on (uptime ~11 days). GCP internal IP `10.138.0.2`.
- **Public IP:** `136.118.155.212` (SSH open, password auth).
- **Owner:** Manus agent (external) — runs `~/.manus/manus-computer-operator`.

## Access

- **Break-glass SSH (public IP, password):** user `ubuntu` (has sudo). Password is in
  `proxmox/.env` as `MANUS_SSH_PASSWORD` (gitignored — **not** committed). Use the helper
  (no `sshpass` in our env, so it uses paramiko):
  ```bash
  python proxmox/manus_ssh.py "uptime"
  python proxmox/manus_ssh.py --sudo "systemctl status tailscaled"
  ```
- **Tailscale:** ⚠️ **not installed on this VM.** The tailnet node that briefly appeared as
  `manus-sandbox` (kernel 6.1.102) was a *separate, ephemeral* sandbox Manus spins up per
  task and tears down — it is not this box and is gone/offline.

## Monitoring

- Wired as an SSH-pull host (`MON_SSH_HOSTS`) with Tailscale set up on the tailnet side
  (`tag:monitor → tag:manus`, grant `tcp:22` + ssh `accept` for root). But it can't report
  until **this VM is on the tailnet** — i.e. Tailscale is installed here and joins as
  `tag:manus`. Pending decision/install. See `monitoring/README.md`.
