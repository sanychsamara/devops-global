#!/usr/bin/env python3
"""monitor.py — lightweight, agentless homelab metrics.

- Proxmox VMs: CPU / memory / network / uptime from the API (RRD week average),
  in-guest free disk from the QEMU guest agent where available.
- Synology (SNMPv3): CPU / real memory / volume usage / uptime (point-in-time).

Writes a daily JSON snapshot and a plain-English right-sizing report.

  python monitoring/monitor.py snapshot   # collect -> monitoring/data/YYYY-MM-DD.json
  python monitoring/monitor.py report     # write   -> monitoring/reports/YYYY-MM-DD.md
  python monitoring/monitor.py check       # snapshot + report (run this on a schedule)

Config + secrets come from proxmox/.env. Proxmox part is stdlib-only; the
Synology part needs pysnmp (monitoring/requirements.txt) and is skipped if absent.
"""
import datetime
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(REPO, "proxmox", "proxmox-devops"))
from client import ProxmoxClient, ProxmoxError, load_env  # noqa: E402

DATA = os.path.join(HERE, "data")
REPORTS = os.path.join(HERE, "reports")
# Config/secrets: MON_ENV override (for the monitor VM) else proxmox/.env.
ENV_FILE = os.environ.get("MON_ENV") or os.path.join(REPO, "proxmox", ".env")

# Right-sizing thresholds (percent of allocation)
RAM_HIGH, RAM_WATCH, RAM_LOW = 80, 70, 30
CPU_HIGH, CPU_LOW = 60, 5
DISK_HIGH, DISK_CRIT = 80, 90


# ── Proxmox VMs ─────────────────────────────────────────────────────────
def collect_proxmox(client):
    out = []
    for r in client.get("/cluster/resources?type=vm") or []:
        if r.get("type") != "qemu" or r.get("template"):
            continue
        node, vmid = r["node"], r["vmid"]
        cur = client.get(f"/nodes/{node}/qemu/{vmid}/status/current")
        rec = {
            "vmid": vmid, "name": r.get("name"), "node": node,
            "status": cur.get("status"),
            "uptime_h": round(cur.get("uptime", 0) / 3600, 1),
            "cores": cur.get("cpus"),
            "mem_alloc_gb": round(cur.get("maxmem", 0) / 1e9, 2),
            "disk_alloc_gb": round(cur.get("maxdisk", 0) / 1e9, 1),
        }
        try:
            rrd = client.get(f"/nodes/{node}/qemu/{vmid}/rrddata?timeframe=week&cf=AVERAGE")
            cpus = [p["cpu"] * 100 for p in rrd if p.get("cpu") is not None]
            mem = [p["mem"] / p["maxmem"] * 100 for p in rrd if p.get("mem") and p.get("maxmem")]
            nin = [p["netin"] for p in rrd if p.get("netin") is not None]
            nout = [p["netout"] for p in rrd if p.get("netout") is not None]
            rec["cpu_avg"] = round(sum(cpus) / len(cpus), 1) if cpus else None
            rec["cpu_peak"] = round(max(cpus), 1) if cpus else None
            rec["mem_avg"] = round(sum(mem) / len(mem), 1) if mem else None
            rec["mem_peak"] = round(max(mem), 1) if mem else None
            rec["net_in_kbps"] = round(sum(nin) / len(nin) / 1024, 1) if nin else None
            rec["net_out_kbps"] = round(sum(nout) / len(nout) / 1024, 1) if nout else None
        except ProxmoxError:
            pass
        try:
            fs = client.get(f"/nodes/{node}/qemu/{vmid}/agent/get-fsinfo")
            disks = []
            for f in (fs.get("result") or []):
                t, u, mp = f.get("total-bytes"), f.get("used-bytes"), f.get("mountpoint", "")
                if t and u is not None and mp == "/":
                    disks.append({"mount": mp, "used_pct": round(u / t * 100), "total_gb": round(t / 1e9, 1)})
            rec["disk"] = disks
        except ProxmoxError:
            rec["disk"] = None
        out.append(rec)
    return out


def vm_verdict(rec):
    notes = []
    if rec.get("mem_avg") is not None:
        if rec["mem_avg"] >= RAM_HIGH or (rec.get("mem_peak") or 0) >= 90:
            notes.append(f"RAM tight ({rec['mem_avg']}% avg / {rec['mem_peak']}% peak of "
                         f"{rec['mem_alloc_gb']} GB) — consider increasing.")
        elif rec["mem_avg"] >= RAM_WATCH:
            notes.append(f"RAM fairly high ({rec['mem_avg']}% avg of {rec['mem_alloc_gb']} GB) — monitor.")
        elif rec["mem_avg"] <= RAM_LOW:
            notes.append(f"RAM over-provisioned ({rec['mem_avg']}% avg of {rec['mem_alloc_gb']} GB).")
    if rec.get("cpu_avg") is not None:
        if rec["cpu_avg"] >= CPU_HIGH or (rec.get("cpu_peak") or 0) >= 90:
            notes.append(f"CPU busy ({rec['cpu_avg']}% avg / {rec['cpu_peak']}% peak over "
                         f"{rec['cores']} vCPU) — consider adding vCPU.")
        elif rec["cpu_avg"] <= CPU_LOW:
            notes.append(f"CPU mostly idle ({rec['cpu_avg']}% avg over {rec['cores']} vCPU).")
    if rec.get("disk"):
        for d in rec["disk"]:
            if d["used_pct"] >= DISK_CRIT:
                notes.append(f"Disk {d['mount']} {d['used_pct']}% of {d['total_gb']} GB — grow soon.")
            elif d["used_pct"] >= DISK_HIGH:
                notes.append(f"Disk {d['mount']} {d['used_pct']}% of {d['total_gb']} GB — watch.")
    elif rec.get("disk") is None:
        notes.append("No guest agent → in-guest free disk unknown (only allocated size).")
    return notes or ["Healthy / right-sized."]


# ── Synology (SNMP) ─────────────────────────────────────────────────────
def collect_synology(env):
    hosts = (env.get("MON_SNMP_HOSTS") or "").strip()
    if not hosts:
        return []
    try:
        import snmp
    except ImportError:
        print("  (pysnmp not installed — skipping Synology; pip install -r monitoring/requirements.txt)")
        return []
    user, auth = env.get("MON_SNMP_USER"), env.get("MON_SNMP_AUTH")
    out = []
    for pair in hosts.split(","):
        if "=" not in pair:
            continue
        name, ip = (x.strip() for x in pair.split("=", 1))
        rec = {"name": name, "ip": ip, "kind": "synology"}
        try:
            rec.update(snmp.synology_metrics(ip, user, auth))
            rec["status"] = "ok"
        except Exception as e:  # noqa: BLE001 — record any SNMP failure
            rec["status"], rec["error"] = "unreachable", str(e)
        out.append(rec)
    return out


def syn_verdict(rec):
    if rec.get("status") != "ok":
        return [f"Unreachable via SNMP ({rec.get('error', '?')})."]
    notes = []
    m = rec.get("mem_used_pct")
    if m is not None:
        if m >= RAM_HIGH:
            notes.append(f"RAM high ({m}% of {rec['mem_total_gb']} GB).")
        elif m >= RAM_WATCH:
            notes.append(f"RAM fairly high ({m}% of {rec['mem_total_gb']} GB) — monitor.")
    if (rec.get("cpu_busy_pct") or 0) >= CPU_HIGH:
        notes.append(f"CPU busy ({rec['cpu_busy_pct']}% at sample).")
    for v in rec.get("volumes", []):
        if v["used_pct"] >= DISK_CRIT:
            notes.append(f"Volume {v['name']} {v['used_pct']}% of {v['total_gb']} GB — grow soon.")
        elif v["used_pct"] >= DISK_HIGH:
            notes.append(f"Volume {v['name']} {v['used_pct']}% of {v['total_gb']} GB — watch.")
    return notes or ["Healthy / right-sized."]


# ── outputs ─────────────────────────────────────────────────────────────
def write_snapshot(vms, syn):
    os.makedirs(DATA, exist_ok=True)
    today = datetime.date.today().isoformat()
    path = os.path.join(DATA, f"{today}.json")
    with open(path, "w", encoding="utf-8") as fh:
        json.dump({"date": today,
                   "collected_at": datetime.datetime.now().isoformat(timespec="seconds"),
                   "vms": vms, "synology": syn}, fh, indent=2)
    return path


def write_report(vms, syn):
    os.makedirs(REPORTS, exist_ok=True)
    today = datetime.date.today().isoformat()
    path = os.path.join(REPORTS, f"{today}.md")
    L = [f"# Homelab resource report — {today}", "",
         "_Non-critical, agentless. Proxmox = RRD week average; Synology = SNMP point-in-time._", "",
         "## Proxmox VMs", "",
         "| VM | status | uptime | CPU avg/peak | RAM avg/peak (alloc) | disk | net in |",
         "|----|--------|--------|--------------|----------------------|------|--------|"]
    for v in vms:
        disk = (", ".join(f"{d['mount']} {d['used_pct']}%/{d['total_gb']}GB" for d in v["disk"])
                if v.get("disk") else f"alloc {v.get('disk_alloc_gb')}GB (no agent)")
        L.append(f"| {v['name']} | {v['status']} | {v['uptime_h']}h | "
                 f"{v.get('cpu_avg')}%/{v.get('cpu_peak')}% | "
                 f"{v.get('mem_avg')}%/{v.get('mem_peak')}% ({v['mem_alloc_gb']}GB) | {disk} | "
                 f"{v.get('net_in_kbps')} KB/s |")
    if syn:
        L += ["", "## NAS / Synology (SNMP, point-in-time)", "",
              "| Host | uptime | CPU | RAM used (total) | volumes |",
              "|------|--------|-----|------------------|---------|"]
        for s in syn:
            if s.get("status") == "ok":
                vols = ", ".join(f"{v['name']} {v['used_pct']}%/{v['total_gb']}GB" for v in s.get("volumes", []))
                L.append(f"| {s['name']} | {s['uptime_h']}h | {s['cpu_busy_pct']}% | "
                         f"{s['mem_used_pct']}% ({s['mem_total_gb']}GB) | {vols} |")
            else:
                L.append(f"| {s['name']} | — | — | — | {s['status']} |")
        L += ["", "_`homenas` also hosts Home Assistant and aperil-bot (containers share its "
              "resources; no per-container SNMP)._"]
    L += ["", "## Right-sizing recommendations", ""]
    for v in vms:
        L.append(f"**{v['name']}** (vmid {v['vmid']})")
        L += [f"- {n}" for n in vm_verdict(v)]
        L.append("")
    for s in syn:
        L.append(f"**{s['name']}** (NAS)")
        L += [f"- {n}" for n in syn_verdict(s)]
        L.append("")
    with open(path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(L))
    return path


def telegram_text(vms, syn):
    """Compact, actionable summary for a chat message (full detail is in the .md)."""
    L = [f"Homelab report {datetime.date.today().isoformat()}", ""]
    for v in vms:
        L.append(f"{v['name']}: cpu {v.get('cpu_avg')}% avg, ram {v.get('mem_avg')}% of {v['mem_alloc_gb']}GB")
        L += [f"  - {n}" for n in vm_verdict(v) if not n.startswith(("Healthy", "No guest"))]
    for s in syn:
        if s.get("status") == "ok":
            L.append(f"{s['name']} (NAS): cpu {s['cpu_busy_pct']}%, ram {s['mem_used_pct']}% of {s['mem_total_gb']}GB")
            L += [f"  - {n}" for n in syn_verdict(s) if not n.startswith("Healthy")]
        else:
            L.append(f"{s['name']} (NAS): {s.get('status')}")
    return "\n".join(L)


def telegram_notify(env, text):
    token, chat = env.get("MON_TELEGRAM_TOKEN"), env.get("MON_TELEGRAM_CHAT")
    if not (token and chat):
        return False
    import urllib.parse
    import urllib.request
    body = urllib.parse.urlencode({"chat_id": chat, "text": text[:4000]}).encode()
    try:
        urllib.request.urlopen(
            urllib.request.Request(f"https://api.telegram.org/bot{token}/sendMessage", data=body),
            timeout=15)
        return True
    except Exception as e:  # noqa: BLE001
        print("telegram error:", e)
        return False


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "check"
    if mode not in ("snapshot", "report", "check"):
        print("usage: monitor.py [snapshot|report|check]")
        sys.exit(2)
    env = load_env(ENV_FILE)
    client = ProxmoxClient(env)
    vms = collect_proxmox(client)
    syn = collect_synology(env)
    if mode in ("snapshot", "check"):
        print("snapshot ->", write_snapshot(vms, syn))
    if mode in ("report", "check"):
        print("report   ->", write_report(vms, syn))
    if mode == "check" and telegram_notify(env, telegram_text(vms, syn)):
        print("telegram -> sent")


if __name__ == "__main__":
    main()
