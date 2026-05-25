#!/usr/bin/env bash
# One-time node bootstrap — snippets + golden Ubuntu cloud-init template.
# Combines 20-enable-snippets.sh + 10-build-template.sh into a single run that
# generates the snippet files inline (no scp needed).
#
# Run it on the node, passing the Tailscale auth key via env:
#   ssh root@proxmox.flamingo-banjo.ts.net "TS_AUTHKEY='tskey-...' bash -s" < proxmox/setup/node-bootstrap.sh
set -euo pipefail

: "${TS_AUTHKEY:?Set TS_AUTHKEY (reusable, pre-approved, tagged Tailscale auth key)}"
SNIPPET_STORAGE="${SNIPPET_STORAGE:-local}"
SNIPPET_DIR="${SNIPPET_DIR:-/var/lib/vz/snippets}"
TEMPLATE_ID="${TEMPLATE_ID:-9000}"
TEMPLATE_NAME="${TEMPLATE_NAME:-ubuntu-2404-cloud}"
STORAGE="${STORAGE:-local-lvm}"
BRIDGE="${BRIDGE:-vmbr0}"
IMG_URL="${IMG_URL:-https://cloud-images.ubuntu.com/noble/current/noble-server-cloudimg-amd64.img}"
IMG_DIR="/var/lib/vz/template/iso"
IMG_FILE="$IMG_DIR/$(basename "$IMG_URL")"

echo "==> [1/4] enable 'snippets' content on storage '$SNIPPET_STORAGE'"
pvesm set "$SNIPPET_STORAGE" --content "backup,iso,vztmpl,images,import,snippets"
mkdir -p "$SNIPPET_DIR"

echo "==> [2/4] write cloud-init vendor snippets"
# base: agent only (non-Tailscale VMs)
cat > "$SNIPPET_DIR/base.yaml" <<'EOF'
#cloud-config
runcmd:
  - [ bash, -c, "export DEBIAN_FRONTEND=noninteractive; apt-get update && apt-get install -y qemu-guest-agent && systemctl enable --now qemu-guest-agent || true" ]
EOF
# login: interactive Tailscale login, URL captured to /var/log/tailscale-up.log
cat > "$SNIPPET_DIR/tailscale-login.yaml" <<'EOF'
#cloud-config
runcmd:
  - [ bash, -c, "export DEBIAN_FRONTEND=noninteractive; apt-get update && apt-get install -y qemu-guest-agent curl" ]
  - [ bash, -c, "systemctl enable --now qemu-guest-agent || true" ]
  - [ bash, -c, "curl -fsSL https://tailscale.com/install.sh | sh" ]
  - [ bash, -c, "nohup tailscale up --hostname=\"$(hostname)\" --accept-routes > /var/log/tailscale-up.log 2>&1 &" ]
EOF
# authkey: zero-touch join (TS_AUTHKEY expanded now; $(hostname) preserved for VM boot)
cat > "$SNIPPET_DIR/tailscale-authkey.yaml" <<EOF
#cloud-config
runcmd:
  - [ bash, -c, "export DEBIAN_FRONTEND=noninteractive; apt-get update && apt-get install -y qemu-guest-agent curl" ]
  - [ bash, -c, "systemctl enable --now qemu-guest-agent || true" ]
  - [ bash, -c, "curl -fsSL https://tailscale.com/install.sh | sh" ]
  - [ bash, -c, "tailscale up --authkey='${TS_AUTHKEY}' --hostname=\"\$(hostname)\" --accept-routes" ]
  - [ bash, -c, "tailscale ip -4 > /var/log/tailscale-ip.txt 2>&1 || true" ]
EOF
chmod 600 "$SNIPPET_DIR/tailscale-authkey.yaml"
ls -l "$SNIPPET_DIR"/*.yaml

echo "==> [3/4] download Ubuntu 24.04 cloud image (if missing)"
mkdir -p "$IMG_DIR"
if [ ! -f "$IMG_FILE" ]; then
  ( command -v wget >/dev/null && wget -O "$IMG_FILE" "$IMG_URL" ) || curl -fSL -o "$IMG_FILE" "$IMG_URL"
fi

echo "==> [4/4] build template $TEMPLATE_ID ($TEMPLATE_NAME)"
qm destroy "$TEMPLATE_ID" --purge 2>/dev/null || true
qm create "$TEMPLATE_ID" --name "$TEMPLATE_NAME" --memory 2048 --cores 2 \
  --net0 "virtio,bridge=$BRIDGE" --scsihw virtio-scsi-single --ostype l26 --agent enabled=1
qm disk import "$TEMPLATE_ID" "$IMG_FILE" "$STORAGE"
qm set "$TEMPLATE_ID" --scsi0 "$STORAGE:vm-$TEMPLATE_ID-disk-0"
qm set "$TEMPLATE_ID" --ide2 "$STORAGE:cloudinit"
qm set "$TEMPLATE_ID" --boot "order=scsi0"
qm set "$TEMPLATE_ID" --serial0 socket --vga serial0
qm set "$TEMPLATE_ID" --ipconfig0 "ip=dhcp"
qm set "$TEMPLATE_ID" --cicustom "vendor=$SNIPPET_STORAGE:snippets/base.yaml"
qm template "$TEMPLATE_ID"

echo "DONE: template $TEMPLATE_ID ready. proxmox-devops can now clone it."
