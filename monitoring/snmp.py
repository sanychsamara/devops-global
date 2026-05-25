"""Minimal SNMPv3 (SHA, authNoPriv) client for Synology hosts via pysnmp 7.

Exposes synology_metrics(ip, user, auth) -> dict with cpu/mem/uptime/volumes.
Memory "used" excludes cache+buffers (NAS uses most RAM as cache).
"""
import asyncio
import re

from pysnmp.hlapi.v3arch.asyncio import (
    ContextData, ObjectIdentity, ObjectType, SnmpEngine, UdpTransportTarget,
    UsmUserData, get_cmd, usmHMACSHAAuthProtocol, walk_cmd,
)

UCD, HR = "1.3.6.1.4.1.2021", "1.3.6.1.2.1.25"
SCALARS = {
    "mem_total_kb": f"{UCD}.4.5.0",
    "mem_avail_kb": f"{UCD}.4.6.0",
    "mem_buffer_kb": f"{UCD}.4.14.0",
    "mem_cached_kb": f"{UCD}.4.15.0",
    "cpu_idle": f"{UCD}.11.11.0",
    "uptime_ticks": f"{HR}.1.1.0",
}
STOR = {"descr": f"{HR}.2.3.1.3", "units": f"{HR}.2.3.1.4",
        "size": f"{HR}.2.3.1.5", "used": f"{HR}.2.3.1.6"}


async def _query(ip, user, auth):
    eng = SnmpEngine()
    creds = UsmUserData(user, authKey=auth, authProtocol=usmHMACSHAAuthProtocol)
    target = await UdpTransportTarget.create((ip, 161), timeout=5, retries=1)
    ctx = ContextData()

    scal = {}
    for name, oid in SCALARS.items():
        ei, es, _, vbs = await get_cmd(eng, creds, target, ctx, ObjectType(ObjectIdentity(oid)))
        if ei or es:
            raise RuntimeError(f"{name}: {ei or es.prettyPrint()}")
        scal[name] = int(vbs[0][1])

    async def walk(base):
        res = {}
        async for ei, es, _, vbs in walk_cmd(eng, creds, target, ctx,
                                             ObjectType(ObjectIdentity(base)),
                                             lexicographicMode=False):
            if ei or es:
                break
            for oid, val in vbs:
                res[str(oid)[len(base) + 1:]] = val
        return res

    descr = await walk(STOR["descr"])
    units = await walk(STOR["units"])
    size = await walk(STOR["size"])
    used = await walk(STOR["used"])
    eng.close_dispatcher()

    real_used = (scal["mem_total_kb"] - scal["mem_avail_kb"]
                 - scal["mem_buffer_kb"] - scal["mem_cached_kb"])
    vols = []
    for idx, d in descr.items():
        name = str(d)
        if not re.match(r"^/volume\d+$", name):   # skip btrfs subvolumes like /volume1/@docker
            continue
        try:
            unit, sz, us = int(units[idx]), int(size[idx]), int(used[idx])
        except (KeyError, ValueError):
            continue
        if sz <= 0:
            continue
        vols.append({"name": name, "used_pct": round(us / sz * 100),
                     "total_gb": round(sz * unit / 1e9, 1)})
    return {
        "cpu_busy_pct": 100 - scal["cpu_idle"],
        "mem_used_pct": round(real_used / scal["mem_total_kb"] * 100, 1),
        "mem_total_gb": round(scal["mem_total_kb"] / 1024 / 1024, 1),
        "uptime_h": round(scal["uptime_ticks"] / 100 / 3600, 1),
        "volumes": vols,
    }


def synology_metrics(ip, user, auth):
    return asyncio.run(_query(ip, user, auth))


if __name__ == "__main__":
    import json
    for host, ip in (("homenas", "100.85.234.68"), ("aperil", "100.110.104.89")):
        try:
            print(host, json.dumps(synology_metrics(ip, "alex", "alex261075")))
        except Exception as e:
            print(host, "ERROR:", repr(e))
