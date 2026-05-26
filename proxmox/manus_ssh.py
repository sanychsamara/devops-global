#!/usr/bin/env python3
"""manus_ssh.py — break-glass SSH to manus-sandbox over its public IP (password auth).

Use when the box is offline on the tailnet (e.g. to fix tailscaled). Credentials come
from proxmox/.env (MANUS_SSH_HOST / MANUS_SSH_USER / MANUS_SSH_PASSWORD) — gitignored,
never committed. Needs `pip install paramiko`.

  python proxmox/manus_ssh.py "tailscale status"
  python proxmox/manus_ssh.py --sudo "systemctl restart tailscaled"
"""
import os
import shlex
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "proxmox-devops"))
from client import load_env  # noqa: E402

import paramiko  # noqa: E402

ENV = load_env(os.path.join(HERE, ".env"))


def connect():
    host = ENV.get("MANUS_SSH_HOST")
    user = ENV.get("MANUS_SSH_USER", "ubuntu")
    pw = ENV.get("MANUS_SSH_PASSWORD")
    if not (host and pw):
        raise SystemExit("Set MANUS_SSH_HOST / MANUS_SSH_PASSWORD in proxmox/.env")
    cli = paramiko.SSHClient()
    cli.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    cli.connect(host, username=user, password=pw, timeout=20,
                look_for_keys=False, allow_agent=False)
    return cli, pw


def run(cli, pw, cmd, sudo=False, timeout=60):
    inner = f"bash -lc {shlex.quote(cmd)}"
    full = f"sudo -S -p '' {inner}" if sudo else inner
    stdin, stdout, stderr = cli.exec_command(full, timeout=timeout)
    if sudo:
        stdin.write(pw + "\n")
        stdin.flush()
    out = stdout.read().decode("utf-8", "replace")
    err = stderr.read().decode("utf-8", "replace")
    return out, err


def main():
    args = sys.argv[1:]
    sudo = False
    if args and args[0] == "--sudo":
        sudo, args = True, args[1:]
    cmd = " ".join(args) or "tailscale status"
    cli, pw = connect()
    out, err = run(cli, pw, cmd, sudo=sudo)
    sys.stdout.write(out)
    if err.strip():
        sys.stderr.write("\n[stderr]\n" + err)
    cli.close()


if __name__ == "__main__":
    main()
