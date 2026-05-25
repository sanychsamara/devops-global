# Proxmox DevOps VM Factory

Spin up a ready-to-use Linux VM on the Proxmox node — cloned from a golden
cloud-init template, auto-joined to Tailscale, with optional weekly backups —
in one command or one sentence to Claude.

> All access is over **Tailscale** (`proxmox.flamingo-banjo.ts.net` / `100.104.12.124`).
> The local LAN IP `192.168.1.21` is never used.

**Status:** live. Token `root@pam!devops` configured, template **9000**
(`ubuntu-2404-cloud`) built, snippets installed, and a first VM (`scrape-research`,
vmid 101) verified running on the tailnet with SSH + weekly backup. Architecture and
design rationale live in the repo-root [`CLAUDE.md`](../CLAUDE.md).

## Layout

```
proxmox/
├── README.md                          this file
├── .env / .env.example                config (.env is gitignored)
├── proxmox-devops/
│   ├── proxmox-devops.py              the CLI (stdlib-only Python 3.8+)
│   ├── client.py                      thin Proxmox REST client
│   └── requirements.txt
├── snippets/                          cloud-init vendor snippets
│   ├── base.yaml                      agent-only (non-Tailscale VMs)
│   ├── tailscale-authkey.yaml.tmpl    zero-touch join (Mode A, default)
│   └── tailscale-login.yaml           interactive login URL (Mode B)
└── setup/
    ├── 00-create-api-token.md         mint the PVE API token
    ├── node-bootstrap.sh              one-shot: snippets + template (runs on node)
    ├── run-node-bootstrap.ps1         Windows runner for node-bootstrap.sh
    ├── 10-build-template.sh           standalone template build (reference)
    └── 20-enable-snippets.sh          standalone snippet install (reference)
.claude/skills/proxmox-devops/         Claude Code skill (natural-language → CLI)
```

## Usage

```bash
# The headline example:
python proxmox/proxmox-devops/proxmox-devops.py create --name scrape-research \
    --ram 2048 --cores 2 --disk 20 --tailscale --backup weekly

python proxmox/proxmox-devops/proxmox-devops.py status
python proxmox/proxmox-devops/proxmox-devops.py snapshot 101 --name pre-change
python proxmox/proxmox-devops/proxmox-devops.py backup   101 --now
python proxmox/proxmox-devops/proxmox-devops.py destroy  101 --yes
```

Or just tell Claude: *"create an ubuntu VM on alex proxmox, 2GB ram, 20GB disk,
name scrape-research, setup tailscale, weekly snapshot backups"* — the
`proxmox-devops` skill maps it to the command above.

## One-time node setup (already done — kept here for rebuilds)

1. **API token** — see [`setup/00-create-api-token.md`](./setup/00-create-api-token.md);
   put `PVE_TOKEN_SECRET` in `.env`. *(Done: `root@pam!devops`, privilege separation off.)*
2. **Tailscale key** — create a reusable, pre-approved, tagged (or **ephemeral**) auth
   key at <https://login.tailscale.com/admin/settings/keys>; put it in `TS_AUTHKEY`.
3. **Snippets + template 9000** — run the bootstrap on the node (prompts for the root
   password once):
   ```powershell
   # Windows (recommended): reads TS_AUTHKEY from .env, ships node-bootstrap.sh over SSH
   powershell -ExecutionPolicy Bypass -File proxmox\setup\run-node-bootstrap.ps1
   ```
   ```bash
   # or directly:
   ssh root@proxmox.flamingo-banjo.ts.net "TS_AUTHKEY='tskey-...' bash -s" < proxmox/setup/node-bootstrap.sh
   ```
4. **Verify**: `python proxmox/proxmox-devops/proxmox-devops.py status` → lists the node + template 9000.

## Tailscale modes

- `--tailscale` (default): zero-touch join via the reusable auth key — VM is on the
  tailnet in seconds, no clicking.
- `--tailscale-url`: interactive login; the CLI reads back the
  `https://login.tailscale.com/...` URL for you to click.

## SSH access

New VMs have **no root login and no password** — auth is key-only:

- User: **`ubuntu`** (set by `PROXMOX_DEVOPS_CIUSER`), with the public key from
  `PROXMOX_DEVOPS_SSH_PUBKEY` installed. Root via passwordless `sudo` (`sudo -i`).
- Over Tailscale: `ssh ubuntu@<tailscale-ip>` (or `ssh ubuntu@<name>.flamingo-banjo.ts.net` via MagicDNS).
- On the LAN: `ssh ubuntu@<lan-ip>` (both IPs are printed when the VM is created).

> The Tailscale snippet runs `tailscale up` **without** `--ssh`, so the VM's own
> `sshd` answers port 22 on every interface and your injected key works directly.
> (For keyless Tailscale SSH instead, re-add `--ssh` in
> `snippets/tailscale-authkey.yaml.tmpl` and add an `ssh` rule to your tailnet ACL.)

## Backups

`--backup weekly` registers a `vzdump` job (Sunday 03:00, mode=snapshot) to `NAS1`
keeping the last 4 weeklies. Fast-rollback snapshots are separate:
`proxmox-devops snapshot <vmid> --name ...`.

## Gotchas & fixes (learned in practice)

- **Token privsep:** a token with privilege separation on and no ACL authenticates
  but sees nothing — ours runs with privsep **off**.
- **DELETE needs query-string params** (Proxmox returns HTTP 501 on a DELETE body) —
  handled in `client.py`.
- **Guest-agent `exec` is blacklisted** on Ubuntu's `qemu-guest-agent` (HTTP 596), so
  IP / Tailscale detection reads `network-get-interfaces`, not `agent exec`.
- **No `--ssh`** on `tailscale up` — otherwise Tailscale hijacks port 22 and key SSH hangs.
- **Tailscale name churn:** destroying/recreating a VM leaves a stale offline device, so
  the next one joins as `name-1`. Delete stale devices in the admin, or use an
  **ephemeral** `TS_AUTHKEY` so they auto-remove.

## Notes / limitations

- The template build and snippet install need **SSH to the node** (one time);
  per-VM creation is then pure REST API.
- Self-signed TLS is not verified by default (`PVE_VERIFY_TLS=false`).
- First boot runs cloud-init (apt install of guest-agent + tailscale), so a new VM
  takes ~1–6 min before its IP / Tailscale status is reported.
