# manus-sandbox

The **always-on VM that runs the Manus agent** (`manus-computer-operator`). Kept as a
**handoff target** for delegating work to Manus. No projects of ours run here.

## Pointers

- **Platform:** GCP VM — hostname `cloud-pc-9ga3ux78`, kernel `6.17.0-gcp`, ~4 GB RAM /
  67 GB disk, always on. GCP internal IP `10.138.0.2`.
- **Public IP:** `136.118.155.212` (SSH open, password auth — break-glass).
- **Tailscale:** node **`manus-sandbox-1.flamingo-banjo.ts.net`** · `100.116.125.109`,
  tagged `tag:manus`, Tailscale SSH enabled. (`-1` because the old, now-defunct ephemeral
  sandbox still holds the `manus-sandbox` name — delete it in the admin to free the name.)
- **Owner:** Manus agent (external).

## Access

- **Over Tailscale (preferred):** `ssh root@manus-sandbox-1.flamingo-banjo.ts.net` (or
  `…@100.116.125.109`) — brokered by Tailscale SSH, authorized by the `tag:monitor → tag:manus`
  ssh ACL rule (the `monitor` node connects this way for metrics).
- **Break-glass (public IP, password):** user `ubuntu` (sudo); password in `proxmox/.env`
  as `MANUS_SSH_PASSWORD` (gitignored, **not** committed). Helper (uses paramiko — no
  `sshpass` in our env):
  ```bash
  python proxmox/manus_ssh.py "uptime"
  python proxmox/manus_ssh.py --sudo "systemctl status tailscaled"
  ```

## Monitoring — live

Collected by the `monitor` VM as an SSH-pull host (`MON_SSH_HOSTS=root@100.116.125.109`,
stable Tailscale IP). Appears in the report + Telegram under **"Other hosts (SSH)"** with
load/CPU, RAM, disk, uptime. Set up 2026-05-26.

## History

- **2026-05-26:** Tailscale was not installed on this VM; the tailnet `manus-sandbox` that
  briefly appeared was a separate ephemeral per-task sandbox (kernel 6.1.102), now gone.
  Installed Tailscale here over the break-glass public-IP SSH and joined the tailnet as
  `tag:manus` + `--ssh`, which made it monitorable.
- ⚠️ Tagged `tag:manus` (tag-owned). If the Manus agent later reimages/resets this VM,
  Tailscale must be reinstalled (re-run the join). Confirm tagging doesn't disrupt Manus.
