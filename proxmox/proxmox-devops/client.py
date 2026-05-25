"""Thin Proxmox VE REST client (standard library only).

Auth: API token (preferred) or username/password ticket.
TLS:  Proxmox uses a self-signed cert; verification is off by default.
Host: always the Tailscale name/IP (set in .env) — never the local LAN IP.
"""
import json
import os
import ssl
import time
import urllib.error
import urllib.parse
import urllib.request


class ProxmoxError(Exception):
    pass


def load_env(path):
    """Minimal .env loader: KEY=VALUE lines, '#' comments, no export needed."""
    env = {}
    if path and os.path.isfile(path):
        with open(path, encoding="utf-8") as fh:
            for raw in fh:
                line = raw.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                k, v = line.split("=", 1)
                env[k.strip()] = v.strip().strip('"').strip("'")
    # Real environment variables win over the file.
    for k, v in os.environ.items():
        if k.startswith(("PVE_", "PROXMOX_DEVOPS_", "TS_", "MON_")):
            env[k] = v
    return env


class ProxmoxClient:
    def __init__(self, env):
        host = env.get("PVE_HOST", "proxmox.flamingo-banjo.ts.net")
        port = env.get("PVE_PORT", "8006")
        self.base = f"https://{host}:{port}/api2/json"
        self.node = env.get("PVE_NODE", "proxmox")
        self.verify = str(env.get("PVE_VERIFY_TLS", "false")).lower() == "true"

        self.token_id = env.get("PVE_TOKEN_ID")
        self.token_secret = env.get("PVE_TOKEN_SECRET")
        self.user = env.get("PVE_USER")
        self.password = env.get("PVE_PASSWORD")

        self._ticket = None
        self._csrf = None

        if not self.verify:
            self._ctx = ssl.create_default_context()
            self._ctx.check_hostname = False
            self._ctx.verify_mode = ssl.CERT_NONE
        else:
            self._ctx = ssl.create_default_context()

        if not (self.token_id and self.token_secret):
            if self.user and self.password:
                self._login()
            else:
                raise ProxmoxError(
                    "No credentials. Set PVE_TOKEN_ID/PVE_TOKEN_SECRET (preferred) "
                    "or PVE_USER/PVE_PASSWORD in .env."
                )

    # ---- auth ----------------------------------------------------------
    def _login(self):
        data = self._raw(
            "POST", "/access/ticket",
            {"username": self.user, "password": self.password}, auth=False,
        )
        self._ticket = data["ticket"]
        self._csrf = data["CSRFPreventionToken"]

    def _auth_headers(self, method):
        h = {}
        if self.token_id and self.token_secret:
            h["Authorization"] = f"PVEAPIToken={self.token_id}={self.token_secret}"
        elif self._ticket:
            h["Cookie"] = f"PVEAuthCookie={self._ticket}"
            if method in ("POST", "PUT", "DELETE"):
                h["CSRFPreventionToken"] = self._csrf
        return h

    # ---- low level -----------------------------------------------------
    def _raw(self, method, path, params=None, auth=True):
        url = self.base + path
        body = None
        headers = {"Accept": "application/json"}
        if auth:
            headers.update(self._auth_headers(method))
        if params:
            if method in ("GET", "DELETE"):
                # Proxmox rejects a request body on DELETE (HTTP 501); use the query string.
                url += "?" + urllib.parse.urlencode(params)
            else:
                body = urllib.parse.urlencode(params).encode()
                headers["Content-Type"] = "application/x-www-form-urlencoded"
        req = urllib.request.Request(url, data=body, method=method, headers=headers)
        try:
            with urllib.request.urlopen(req, context=self._ctx, timeout=60) as resp:
                payload = json.load(resp)
        except urllib.error.HTTPError as e:
            detail = e.read().decode(errors="replace")
            raise ProxmoxError(f"{method} {path} -> HTTP {e.code}: {detail}") from None
        except urllib.error.URLError as e:
            raise ProxmoxError(f"{method} {path} -> connection error: {e.reason}") from None
        return payload.get("data")

    def get(self, path, params=None):
        return self._raw("GET", path, params)

    def post(self, path, params=None):
        return self._raw("POST", path, params)

    def put(self, path, params=None):
        return self._raw("PUT", path, params)

    def delete(self, path, params=None):
        return self._raw("DELETE", path, params)

    # ---- helpers -------------------------------------------------------
    def nextid(self):
        return int(self.get("/cluster/nextid"))

    def wait_task(self, upid, timeout=300, poll=2):
        """Block until a node task (UPID) finishes; raise on non-OK exit."""
        deadline = time.time() + timeout
        path = f"/nodes/{self.node}/tasks/{urllib.parse.quote(upid, safe='')}/status"
        while time.time() < deadline:
            st = self.get(path)
            if st and st.get("status") == "stopped":
                if st.get("exitstatus") != "OK":
                    raise ProxmoxError(f"task {upid} failed: {st.get('exitstatus')}")
                return st
            time.sleep(poll)
        raise ProxmoxError(f"task {upid} timed out after {timeout}s")

    def agent_exec(self, vmid, command):
        """Run a command in the guest via the QEMU agent; return collected output."""
        pid = self.post(
            f"/nodes/{self.node}/qemu/{vmid}/agent/exec",
            {"command": command},
        )["pid"]
        for _ in range(30):
            res = self.get(
                f"/nodes/{self.node}/qemu/{vmid}/agent/exec-status",
                {"pid": pid},
            )
            if res.get("exited"):
                return res
            time.sleep(1)
        return {"exited": 0, "out-data": "", "err-data": "timeout"}

    def agent_ready(self, vmid):
        try:
            self.get(f"/nodes/{self.node}/qemu/{vmid}/agent/ping")
            return True
        except ProxmoxError:
            return False
