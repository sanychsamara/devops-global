#!/usr/bin/env python3
"""proxmox-devops — Proxmox VM factory.

Clone a golden cloud-init template into a ready-to-use Linux VM, join it to
Tailscale, and (optionally) register a weekly backup — in one command.

  python proxmox-devops/proxmox-devops.py create --name scrape-research \
      --ram 2048 --disk 20 --cores 2 --tailscale --backup weekly

  python proxmox-devops/proxmox-devops.py status
  python proxmox-devops/proxmox-devops.py list
  python proxmox-devops/proxmox-devops.py snapshot <vmid> --name pre-change
  python proxmox-devops/proxmox-devops.py backup  <vmid> --schedule "sun 03:00"
  python proxmox-devops/proxmox-devops.py destroy <vmid> --yes

Config comes from proxmox/.env (see .env.example). Host is always the
Tailscale name/IP — never the local LAN IP.
"""
import argparse
import os
import re
import sys
import time
import urllib.parse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from client import ProxmoxClient, ProxmoxError, load_env  # noqa: E402

ENV_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env")
TS_URL_RE = re.compile(r"https://login\.tailscale\.com/\S+")


# ── helpers ────────────────────────────────────────────────────────────
def read_pubkey(env):
    path = env.get("PROXMOX_DEVOPS_SSH_PUBKEY", "").strip()
    if path and os.path.isfile(path):
        with open(path, encoding="utf-8") as fh:
            return fh.read().strip()
    return None


def get_ifaces(client, vmid):
    """Guest-agent interface list. More reliable than agent ping/exec on this PVE."""
    try:
        return client.get(f"/nodes/{client.node}/qemu/{vmid}/agent/network-get-interfaces")
    except ProxmoxError:
        return None


def lan_ip_from(data):
    for iface in (data.get("result") or []):
        name = iface.get("name", "")
        if name in ("lo", "tailscale0") or name.startswith(("docker", "veth", "br-")):
            continue
        for addr in (iface.get("ip-addresses") or []):
            ip = addr.get("ip-address", "")
            if addr.get("ip-address-type") == "ipv4" and not ip.startswith("127."):
                return ip
    return None


def ts_ip_from(data):
    for iface in (data.get("result") or []):
        if iface.get("name") == "tailscale0":
            for addr in (iface.get("ip-addresses") or []):
                ip = addr.get("ip-address", "")
                if addr.get("ip-address-type") == "ipv4" and ip.startswith("100."):
                    return ip
    return None


def find_backup_jobs_for(client, vmid):
    jobs = client.get("/cluster/backup") or []
    out = []
    for j in jobs:
        ids = str(j.get("vmid", "")).split(",")
        if str(vmid) in ids:
            out.append(j)
    return out


def create_backup_job(client, vmid, env, schedule=None):
    schedule = schedule or env.get("PROXMOX_DEVOPS_BACKUP_SCHEDULE", "sun 03:00")
    params = {
        "vmid": str(vmid),
        "storage": env.get("PROXMOX_DEVOPS_BACKUP_STORAGE", "NAS1"),
        "schedule": schedule,
        "mode": "snapshot",
        "enabled": 1,
        "prune-backups": env.get("PROXMOX_DEVOPS_BACKUP_RETENTION", "keep-weekly=4"),
        "notes-template": "{{guestname}} (proxmox-devops weekly)",
        "comment": f"proxmox-devops:{vmid}",
    }
    client.post("/cluster/backup", params)
    return params


# ── commands ───────────────────────────────────────────────────────────
def cmd_status(client, env, args):
    ver = client.get("/version")
    print(f"Proxmox {ver.get('version')} @ {client.base}")
    print(f"Node: {client.node}\n")
    print(f"{'TYPE':6} {'VMID':>5}  {'NAME':24} {'STATUS':9} {'TEMPLATE'}")
    for r in sorted(client.get("/cluster/resources?type=vm") or [], key=lambda x: x.get("vmid", 0)):
        print(f"{r.get('type'):6} {r.get('vmid'):>5}  {str(r.get('name','')):24} "
              f"{str(r.get('status','')):9} {'yes' if r.get('template') else ''}")


def cmd_list(client, env, args):
    cmd_status(client, env, args)


def cmd_create(client, env, args):
    node = client.node
    template_id = args.template or int(env.get("PROXMOX_DEVOPS_TEMPLATE_ID", 9000))
    storage = args.storage or env.get("PROXMOX_DEVOPS_STORAGE", "local-lvm")
    snip_storage = env.get("PROXMOX_DEVOPS_SNIPPET_STORAGE", "local")
    vmid = args.vmid or client.nextid()

    print(f"[1/6] clone template {template_id} -> VM {vmid} '{args.name}' on {storage}")
    upid = client.post(f"/nodes/{node}/qemu/{template_id}/clone", {
        "newid": vmid, "name": args.name, "full": 1, "storage": storage,
    })
    client.wait_task(upid, timeout=600)

    print(f"[2/6] configure cores={args.cores} ram={args.ram}MB cloud-init")
    cfg = {
        "memory": args.ram,
        "cores": args.cores,
        "ciuser": env.get("PROXMOX_DEVOPS_CIUSER", "ubuntu"),
        "ipconfig0": "ip=dhcp",
        "agent": "enabled=1",
        "tags": "proxmox-devops",
    }
    pub = read_pubkey(env)
    if pub:
        cfg["sshkeys"] = urllib.parse.quote(pub, safe="")
    else:
        print("      WARNING: no SSH public key found (set PROXMOX_DEVOPS_SSH_PUBKEY) — "
              "you will rely on Tailscale SSH only.")
    if args.tailscale_url:
        cfg["cicustom"] = f"vendor={snip_storage}:snippets/tailscale-login.yaml"
    elif args.tailscale:
        cfg["cicustom"] = f"vendor={snip_storage}:snippets/tailscale-authkey.yaml"
    else:
        # No Tailscale: use the agent-only snippet so we never silently inherit
        # the template's auth-key join, but still get the guest agent for IP.
        cfg["cicustom"] = f"vendor={snip_storage}:snippets/base.yaml"
    client.post(f"/nodes/{node}/qemu/{vmid}/config", cfg)

    print(f"[3/6] resize scsi0 -> {args.disk}G")
    client.put(f"/nodes/{node}/qemu/{vmid}/resize", {"disk": "scsi0", "size": f"{args.disk}G"})

    print("[4/6] start VM")
    upid = client.post(f"/nodes/{node}/qemu/{vmid}/status/start")
    client.wait_task(upid)

    want_ts = args.tailscale or args.tailscale_url
    print(f"[5/6] wait for boot + network{' + Tailscale' if want_ts else ''} "
          "(first boot installs the agent + Tailscale; up to 6 min)")
    ip = ts_ip = ts_url = None
    deadline = time.time() + 360
    while time.time() < deadline:
        data = get_ifaces(client, vmid)
        if data:
            ip = ip or lan_ip_from(data)
            if args.tailscale:
                ts_ip = ts_ip or ts_ip_from(data)
        if args.tailscale_url and not ts_url:
            # Mode B needs the login URL from the boot log; agent exec is best-effort.
            try:
                res = client.agent_exec(vmid, ["cat", "/var/log/tailscale-up.log"])
                m = TS_URL_RE.search((res.get("out-data") or "") + (res.get("err-data") or ""))
                if m:
                    ts_url = m.group(0)
            except ProxmoxError:
                pass
        if ip and (ts_ip or ts_url or not want_ts):
            break
        time.sleep(5)

    if args.backup:
        print(f"[6/6] register weekly backup -> {env.get('PROXMOX_DEVOPS_BACKUP_STORAGE','NAS1')} "
              f"({env.get('PROXMOX_DEVOPS_BACKUP_SCHEDULE','sun 03:00')})")
        create_backup_job(client, vmid, env, args.backup_schedule)
    else:
        print("[6/6] backup: skipped (pass --backup weekly to enable)")

    print("\n" + "=" * 60)
    print(f"  VM ready: {args.name}  (vmid {vmid})")
    print(f"  LAN IP:        {ip or 'pending (check Proxmox console)'}")
    if args.tailscale_url:
        print(f"  Tailscale:     LOGIN REQUIRED -> {ts_url or 'URL not captured yet; run: tailscale up on the VM'}")
    elif args.tailscale:
        print(f"  Tailscale:     {args.name} @ {ts_ip or 'joining... (give it a moment)'}")
    print(f"  SSH:           ssh {env.get('PROXMOX_DEVOPS_CIUSER','ubuntu')}@{ts_ip or ip or args.name}")
    if args.backup:
        print(f"  Backups:       weekly -> {env.get('PROXMOX_DEVOPS_BACKUP_STORAGE','NAS1')}")
    print("=" * 60)


def cmd_destroy(client, env, args):
    node = client.node
    vmid = args.vmid
    if not args.yes:
        print(f"Refusing to destroy VM {vmid} without --yes")
        return
    for j in find_backup_jobs_for(client, vmid):
        if str(j.get("vmid")) == str(vmid):  # only delete single-VM jobs we own
            print(f"  removing backup job {j.get('id')}")
            client.delete(f"/cluster/backup/{j.get('id')}")
    status = client.get(f"/nodes/{node}/qemu/{vmid}/status/current")
    if status.get("status") == "running":
        print("  stopping VM")
        client.wait_task(client.post(f"/nodes/{node}/qemu/{vmid}/status/stop"))
    print(f"  deleting VM {vmid}")
    upid = client.delete(f"/nodes/{node}/qemu/{vmid}",
                         {"purge": 1, "destroy-unreferenced-disks": 1})
    client.wait_task(upid)
    print(f"VM {vmid} destroyed.")


def cmd_snapshot(client, env, args):
    node = client.node
    params = {"snapname": args.name, "description": args.description or "via proxmox-devops"}
    if args.vmstate:
        params["vmstate"] = 1
    upid = client.post(f"/nodes/{node}/qemu/{args.vmid}/snapshot", params)
    client.wait_task(upid)
    print(f"Snapshot '{args.name}' created on VM {args.vmid}.")


def cmd_backup(client, env, args):
    if args.now:
        upid = client.post(f"/nodes/{client.node}/vzdump", {
            "vmid": str(args.vmid),
            "storage": env.get("PROXMOX_DEVOPS_BACKUP_STORAGE", "NAS1"),
            "mode": "snapshot",
        })
        client.wait_task(upid, timeout=3600)
        print(f"On-demand backup of VM {args.vmid} complete.")
        return
    p = create_backup_job(client, args.vmid, env, args.schedule)
    print(f"Weekly backup job created for VM {args.vmid}: "
          f"{p['schedule']} -> {p['storage']} ({p['prune-backups']}).")


# ── argparse ───────────────────────────────────────────────────────────
def build_parser():
    p = argparse.ArgumentParser(prog="proxmox-devops", description="Proxmox VM factory")
    sub = p.add_subparsers(dest="cmd", required=True)

    c = sub.add_parser("create", help="create a new VM from the golden template")
    c.add_argument("--name", required=True)
    c.add_argument("--ram", type=int, default=2048, help="MB (default 2048)")
    c.add_argument("--cores", type=int, default=2)
    c.add_argument("--disk", type=int, default=20, help="GB (default 20)")
    c.add_argument("--template", type=int, default=None, help="template VMID (default from .env)")
    c.add_argument("--storage", default=None, help="disk storage (default from .env)")
    c.add_argument("--vmid", type=int, default=None, help="force a VMID (default: next free)")
    c.add_argument("--tailscale", action="store_true", help="zero-touch join via auth key (Mode A)")
    c.add_argument("--tailscale-url", action="store_true", help="interactive login, return URL (Mode B)")
    c.add_argument("--backup", choices=["weekly"], default=None, help="register a recurring backup job")
    c.add_argument("--backup-schedule", default=None, help="override schedule, e.g. 'sun 03:00'")
    c.set_defaults(func=cmd_create)

    sub.add_parser("status", help="show node + VMs").set_defaults(func=cmd_status)
    sub.add_parser("list", help="alias for status").set_defaults(func=cmd_list)

    d = sub.add_parser("destroy", help="stop + delete a VM and its backup job")
    d.add_argument("vmid", type=int)
    d.add_argument("--yes", action="store_true", help="confirm destruction")
    d.set_defaults(func=cmd_destroy)

    s = sub.add_parser("snapshot", help="take a snapshot")
    s.add_argument("vmid", type=int)
    s.add_argument("--name", required=True)
    s.add_argument("--description", default=None)
    s.add_argument("--vmstate", action="store_true", help="include RAM state")
    s.set_defaults(func=cmd_snapshot)

    b = sub.add_parser("backup", help="create a weekly backup job (or --now for one-off)")
    b.add_argument("vmid", type=int)
    b.add_argument("--schedule", default=None, help="systemd calendar, e.g. 'sun 03:00'")
    b.add_argument("--now", action="store_true", help="run a backup immediately instead")
    b.set_defaults(func=cmd_backup)
    return p


def main():
    args = build_parser().parse_args()
    env = load_env(ENV_PATH)
    try:
        client = ProxmoxClient(env)
        args.func(client, env, args)
    except ProxmoxError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
