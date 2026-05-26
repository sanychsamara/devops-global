#!/usr/bin/env python3
"""analyze.py — weekly LLM right-sizing narrative for the homelab.

Reads recent monitoring snapshots, asks an Anthropic model **via OpenRouter** for a
concise capacity verdict, and posts it to Telegram. Runs weekly on the monitor VM
after `monitor.py check`.

Auth: OPENROUTER_API_KEY (read from the environment, or from the .env file).
Model: anthropic/claude-haiku-4.5 by default (cheap); override with MON_LLM_MODEL.
Stdlib HTTP only — OpenRouter is OpenAI-compatible.
"""
import glob
import json
import os
import sys
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from monitor import DATA, ENV_FILE, telegram_notify  # noqa: E402
from client import load_env  # noqa: E402

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
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


def ask_openrouter(key, model, system, user_content):
    body = json.dumps({
        "model": model,
        "max_tokens": 1024,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user_content},
        ],
    }).encode()
    req = urllib.request.Request(OPENROUTER_URL, data=body, headers={
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
        "X-Title": "homelab-monitor",
    })
    with urllib.request.urlopen(req, timeout=90) as resp:
        data = json.load(resp)
    return (data["choices"][0]["message"]["content"] or "").strip()


def main():
    env = load_env(ENV_FILE)
    key = os.environ.get("OPENROUTER_API_KEY") or env.get("OPENROUTER_API_KEY")
    if not key:
        print("OPENROUTER_API_KEY not set — skipping LLM analysis.")
        return
    snaps = recent_snapshots()
    if not snaps:
        print("no snapshots to analyze.")
        return
    model = env.get("MON_LLM_MODEL", "anthropic/claude-haiku-4.5")
    prompt = ("Recent homelab metric snapshots (oldest first), JSON:\n\n"
              + json.dumps(snaps, indent=2)
              + "\n\nWrite the weekly right-sizing summary.")
    text = ask_openrouter(key, model, SYSTEM, prompt)
    if not text:
        print("empty LLM response.")
        return
    msg = "Weekly capacity analysis\n\n" + text
    print(msg)
    if telegram_notify(env, msg):
        print("telegram -> sent")


if __name__ == "__main__":
    main()
