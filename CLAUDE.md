# CLAUDE.md — devops-global

DevOps automation repo. Current contents: a **Proxmox VM factory** under `proxmox/`.

## Proxmox VM factory

One command (or one sentence to Claude) → a running, Tailscale-joined Ubuntu VM on
the home Proxmox node, with optional weekly backups.

- **Usage / quickstart:** [`proxmox/README.md`](proxmox/README.md)
- **CLI:** `proxmox/proxmox-devops/proxmox-devops.py` (`create | status | list | snapshot | backup | destroy`); REST client in `client.py`. Stdlib-only Python 3.8+.
- **Natural-language skill:** `.claude/skills/proxmox-devops/SKILL.md` (maps "create an ubuntu VM, 2GB, 20GB, tailscale, weekly backups" → CLI).
- **One-time node bootstrap:** `proxmox/setup/` — `node-bootstrap.sh` (snippets + template, runs on the node) and `run-node-bootstrap.ps1` (Windows runner).
- **Secrets:** `proxmox/.env` (gitignored) — PVE API token + Tailscale auth key.

### Environment (verified 2026-05-25)

- Proxmox VE **9.1.1**, single node `proxmox` (32 vCPU / 135 GB).
- Reach the API **only via Tailscale**: `proxmox.flamingo-banjo.ts.net` (or `100.104.12.124`). **Never** the LAN IP `192.168.1.21`.
- Storage: `local-lvm` (LVM-thin, VM disks, snapshot-capable) · `NAS1` (NFS, backups) · `local` (dir, cloud-init snippets).
- Auth: API token `root@pam!devops` (**privilege separation off**).
- Golden template: VMID **9000** (`ubuntu-2404-cloud`).

### Key design decisions (and why)

- **REST API + SSH split.** Per-VM lifecycle is pure REST API; only the one-time
  golden-template/snippet build needs node SSH (no clean API for disk import or
  writing snippet files).
- **Golden template + full clone + cloud-init.** Clone 9000 → set CPU/RAM → resize
  disk → attach a cloud-init vendor snippet → start. Fast, repeatable.
- **Tailscale via cloud-init vendor-data snippet.** Proxmox's native cloud-init
  can't run arbitrary commands; vendor-data (`--cicustom`) can. Three snippets:
  `base.yaml` (agent only), `tailscale-authkey.yaml` (zero-touch, default),
  `tailscale-login.yaml` (interactive URL). The CLI picks one per VM.
- **Zero-touch Tailscale** using a reusable auth key baked into the snippet;
  `--hostname` = VM name.
- **Key-based SSH, not Tailscale SSH.** The snippet runs `tailscale up` **without**
  `--ssh`, so the VM's own `sshd` owns port 22 (tailnet + LAN) and the injected SSH
  key works directly. Login user `ubuntu`, no password, root via passwordless `sudo`.
- **Backups = weekly `vzdump` → `NAS1`** (mode=snapshot, keep-weekly=4, Sun 03:00).
  Fast-rollback snapshots are a separate concern (`snapshot` subcommand).
- **Secrets in `.env`** (gitignored); the API host is always the Tailscale name.

### Gotchas (hard-won — don't re-learn these)

- A PVE token with **privsep on and no ACL** authenticates but sees nothing → use
  privsep off (homelab) or grant a role (`setup/00-create-api-token.md`).
- **DELETE with a request body → HTTP 501.** DELETE params must go in the query
  string (handled in `client.py`).
- Ubuntu's `qemu-guest-agent` **blacklists `guest-exec`** → `agent/exec` returns
  HTTP 596. Read VM IP / Tailscale IP from `agent/network-get-interfaces` instead.
- **`tailscale up --ssh` hijacks port 22** on the tailnet → key SSH hangs. Omit it.
- **Tailscale device names are sticky.** Destroy/recreate leaves stale offline
  entries and the new device gets a `-1` suffix. Delete stale devices in the
  Tailscale admin, or use an **ephemeral** auth key for automatic cleanup.
- First boot installs agent + Tailscale over the network → allow ~1–6 min before
  IPs report.

## Conventions

- Windows host, **PowerShell** default — use PowerShell syntax for shell commands.
- Never commit `proxmox/.env` or `*.key` (already in `.gitignore`).
