# Step 0 — Create a Proxmox API token (done once)

Scripts authenticate with an **API token**, not the root password.

> ✅ Already created for this project: **`root@pam!devops`**, secret stored in
> `proxmox/.env`. The steps below are for reference / recreating it.

## Option A — via the web UI

1. Open `https://proxmox.flamingo-banjo.ts.net:8006` (or `https://100.104.12.124:8006`).
2. **Datacenter → Permissions → API Tokens → Add**.
   - User: `root@pam`
   - Token ID: `devops`
   - **Uncheck "Privilege Separation"** for a quick homelab setup (token inherits root's rights),
     or leave it checked and grant the role below.
3. Copy the **Secret** shown once into `proxmox/.env` as `PVE_TOKEN_SECRET`.
   `PVE_TOKEN_ID` is then `root@pam!devops`.

## Option B — via SSH on the node

```bash
ssh root@proxmox.flamingo-banjo.ts.net
# Full-rights token (privilege separation off):
pveum user token add root@pam devops --privsep 0
# ^ prints the secret value ONCE — copy it to .env
```

## Least-privilege (recommended if you don't want full root)

```bash
ssh root@proxmox.flamingo-banjo.ts.net
pveum role add ProxmoxDevops -privs \
  "VM.Allocate VM.Clone VM.Config.Disk VM.Config.CPU VM.Config.Memory \
   VM.Config.Network VM.Config.Options VM.Config.Cloudinit VM.PowerMgmt \
   VM.Audit VM.Snapshot VM.Backup Datastore.AllocateSpace Datastore.Audit \
   Sys.Audit VM.Monitor VM.GuestAgent.Audit VM.GuestAgent.Unrestricted"
pveum user add devops@pve
pveum acl modify / -user devops@pve -role ProxmoxDevops
pveum user token add devops@pve devops --privsep 0
# Then in .env:  PVE_TOKEN_ID=devops@pve!devops
```

## Verify

```bash
cd proxmox
python proxmox-devops/proxmox-devops.py status     # should list the node + existing VMs
```
