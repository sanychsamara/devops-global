#!/usr/bin/env python3
"""analyze.py — weekly LLM right-sizing narrative for the homelab.

Reads recent monitoring snapshots, asks Claude for a concise capacity verdict,
and posts it to Telegram. Runs weekly on the monitor VM after `monitor.py check`.

Model: claude-haiku-4-5 by default (cheapest — this is a small weekly
summarization task; the whole point is "very low cost"). Override with
MON_LLM_MODEL. Needs MON_ANTHROPIC_KEY in the env.

No prompt caching on purpose: weekly runs are far apart with no shared prefix
within the cache TTL, so caching would add write cost with zero cache reads.
"""
import glob
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from monitor import DATA, ENV_FILE, telegram_notify  # noqa: E402
from client import load_env  # noqa: E402

SYSTEM = (
    "You are a homelab capacity advisor. Given recent per-host metrics (Proxmox VMs "
    "with week-average CPU/RAM and a NAS sampled via SNMP), write a SHORT plain-text "
    "message for a Telegram chat — no markdown headers, no preamble. For each host: say "
    "whether it should get more or less CPU/RAM/disk and why, citing the actual numbers; "
    "give healthy hosts a single line. End with a one-line bottom line. Under ~1500 chars."
)


def recent_snapshots(n=7):
    out = []
    for f in sorted(glob.glob(os.path.join(DATA, "*.json")))[-n:]:
        try:
            with open(f, encoding="utf-8") as fh:
                out.append(json.load(fh))
        except (OSError, ValueError):
            pass
    return out


def main():
    env = load_env(ENV_FILE)
    key = env.get("MON_ANTHROPIC_KEY") or os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        print("MON_ANTHROPIC_KEY not set — skipping LLM analysis.")
        return
    snaps = recent_snapshots()
    if not snaps:
        print("no snapshots to analyze.")
        return

    import anthropic  # lazy: only needed when a key is present

    model = env.get("MON_LLM_MODEL", "claude-haiku-4-5")
    client = anthropic.Anthropic(api_key=key)
    prompt = ("Recent homelab metric snapshots (oldest first), JSON:\n\n"
              + json.dumps(snaps, indent=2)
              + "\n\nWrite the weekly right-sizing summary.")
    resp = client.messages.create(
        model=model,
        max_tokens=1024,
        system=SYSTEM,
        messages=[{"role": "user", "content": prompt}],
    )
    text = "".join(b.text for b in resp.content if b.type == "text").strip()
    if not text:
        print("empty LLM response.")
        return
    msg = "Weekly capacity analysis\n\n" + text
    print(msg)
    if telegram_notify(env, msg):
        print("telegram -> sent")


if __name__ == "__main__":
    main()
