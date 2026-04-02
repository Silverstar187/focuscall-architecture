# focuscall.ai — Infrastructure as Code

Terraform + cloud-init für Hetzner CAX21 (ARM64, Ubuntu 24.04).

## Voraussetzungen

```bash
brew install terraform
# Hetzner API Token: https://console.hetzner.cloud/projects → API Tokens
```

## Neuen Server deployen

```bash
cp terraform.tfvars.example terraform.tfvars
# terraform.tfvars ausfüllen

terraform init
terraform plan
terraform apply
```

`terraform apply` dauert ~2min bis der Server läuft.
ZeroClaw Docker Image baut im Hintergrund (~10min nach Boot).

## Outputs

```
server_ip   = "91.99.x.x"
webhook_url = "http://91.99.x.x:9000"
```

→ `webhook_url` in Supabase Edge Function als `VPS_WEBHOOK_URL` setzen.

## Nach dem ersten Boot

provision.py + webhook-receiver.py deployen:

```bash
SERVER=$(terraform output -raw server_ip)
scp -i ~/.ssh/openclaw_nopass ../provisioning/provision.py root@$SERVER:/opt/focuscall/provisioning/
scp -i ~/.ssh/openclaw_nopass ../provisioning/webhook-receiver.py root@$SERVER:/opt/focuscall/provisioning/
scp -i ~/.ssh/openclaw_nopass ../provisioning/config.toml.tmpl root@$SERVER:/opt/focuscall/provisioning/
ssh -i ~/.ssh/openclaw_nopass root@$SERVER "systemctl start focuscall-webhook"
```

## Server entfernen

```bash
terraform destroy
```

## Struktur

```
infra/
├── main.tf                  — Server, Firewall, SSH Key
├── variables.tf             — Variablen-Definitionen
├── cloud-init.yml           — Bootstrap bei erstem Boot
├── terraform.tfvars.example — Vorlage (terraform.tfvars nie in Git!)
└── .gitignore               — Secrets ausschließen
```
