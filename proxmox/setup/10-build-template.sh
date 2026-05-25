#!/usr/bin/env bash
# Step 1 — Build the golden Ubuntu cloud-init template (do this once).
# RUN ON THE PROXMOX NODE (after 20-enable-snippets.sh):
#   ssh root@proxmox.flamingo-banjo.ts.net 'bash -s' < proxmox/setup/10-build-template.sh
#
# Produces a PVE template (default id 9000) that proxmox-devops clones for every new VM.
set -euo pipefail

TEMPLATE_ID="${TEMPLATE_ID:-9000}"
TEMPLATE_NAME="${TEMPLATE_NAME:-ubuntu-2404-cloud}"
STORAGE="${STORAGE:-local-lvm}"
SNIPPET_STORAGE="${SNIPPET_STORAGE:-local}"
BRIDGE="${BRIDGE:-vmbr0}"
IMG_URL="${IMG_URL:-https://cloud-images.ubuntu.com/noble/current/noble-server-cloudimg-amd64.img}"
IMG_DIR="/var/lib/vz/template/iso"
IMG_FILE="$IMG_DIR/$(basename "$IMG_URL")"

echo ">> Downloading Ubuntu 24.04 cloud image (if missing)"
mkdir -p "$IMG_DIR"
[ -f "$IMG_FILE" ] || wget -O "$IMG_FILE" "$IMG_URL"

echo ">> (Re)creating template VM $TEMPLATE_ID"
qm destroy "$TEMPLATE_ID" --purge 2>/dev/null || true
qm create "$TEMPLATE_ID" \
  --name "$TEMPLATE_NAME" \
  --memory 2048 --cores 2 \
  --net0 "virtio,bridge=$BRIDGE" \
  --scsihw virtio-scsi-single \
  --ostype l26 \
  --agent enabled=1

echo ">> Importing cloud image disk to $STORAGE"
# 'qm disk import' is the PVE 8/9 command (older alias: 'qm importdisk')
qm disk import "$TEMPLATE_ID" "$IMG_FILE" "$STORAGE"
qm set "$TEMPLATE_ID" --scsi0 "$STORAGE:vm-$TEMPLATE_ID-disk-0"

echo ">> Attaching cloud-init drive, serial console, boot order, DHCP, vendor snippet"
qm set "$TEMPLATE_ID" --ide2 "$STORAGE:cloudinit"
qm set "$TEMPLATE_ID" --boot "order=scsi0"
qm set "$TEMPLATE_ID" --serial0 socket --vga serial0
qm set "$TEMPLATE_ID" --ipconfig0 "ip=dhcp"
# Safe default snippet = agent-only. proxmox-devops always sets the right one per VM
# (base.yaml / tailscale-authkey.yaml / tailscale-login.yaml).
qm set "$TEMPLATE_ID" --cicustom "vendor=$SNIPPET_STORAGE:snippets/base.yaml"

echo ">> Converting to template"
qm template "$TEMPLATE_ID"

echo "Done. Template $TEMPLATE_ID ($TEMPLATE_NAME) ready. proxmox-devops will clone it."
