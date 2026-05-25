#!/usr/bin/env bash
# Step 2 — Enable cloud-init snippets and install the Tailscale vendor snippets.
# RUN ON THE PROXMOX NODE:
#   scp -r proxmox/snippets root@proxmox.flamingo-banjo.ts.net:/tmp/
#   ssh root@proxmox.flamingo-banjo.ts.net 'TS_AUTHKEY=tskey-... bash -s' < proxmox/setup/20-enable-snippets.sh
set -euo pipefail

SNIPPET_STORAGE="${SNIPPET_STORAGE:-local}"
SNIPPET_DIR="${SNIPPET_DIR:-/var/lib/vz/snippets}"
SRC_DIR="${SRC_DIR:-/tmp/snippets}"     # where you scp'd proxmox/snippets to
: "${TS_AUTHKEY:?Set TS_AUTHKEY to a reusable, pre-approved, tagged Tailscale auth key}"

echo ">> Enabling 'snippets' content on storage '$SNIPPET_STORAGE' (preserving existing types)"
# local already has: backup,iso,vztmpl,images,import — add snippets.
pvesm set "$SNIPPET_STORAGE" --content "backup,iso,vztmpl,images,import,snippets"

mkdir -p "$SNIPPET_DIR"

echo ">> Writing Mode A (auth key) vendor snippet"
sed "s|__TS_AUTHKEY__|${TS_AUTHKEY}|g" \
    "$SRC_DIR/tailscale-authkey.yaml.tmpl" > "$SNIPPET_DIR/tailscale-authkey.yaml"
chmod 600 "$SNIPPET_DIR/tailscale-authkey.yaml"   # contains the auth key

echo ">> Writing Mode B (login URL) vendor snippet"
cp "$SRC_DIR/tailscale-login.yaml" "$SNIPPET_DIR/tailscale-login.yaml"

echo ">> Writing base (agent-only) vendor snippet for non-Tailscale VMs"
cp "$SRC_DIR/base.yaml" "$SNIPPET_DIR/base.yaml"

echo ">> Installed:"
ls -l "$SNIPPET_DIR"/tailscale-*.yaml
echo "Done. Snippets are referenced as ${SNIPPET_STORAGE}:snippets/<file>.yaml"
