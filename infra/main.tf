terraform {
  required_providers {
    hcloud = {
      source  = "hetznercloud/hcloud"
      version = "~> 1.49"
    }
  }
  required_version = ">= 1.5"
}

provider "hcloud" {
  token = var.hcloud_token
}

# ── SSH Key ────────────────────────────────────────────────────────────────────
resource "hcloud_ssh_key" "focuscall" {
  name       = "focuscall-key"
  public_key = file(var.ssh_public_key_path)
}

# ── Firewall ───────────────────────────────────────────────────────────────────
resource "hcloud_firewall" "focuscall" {
  name = "focuscall-firewall"

  # SSH
  rule {
    direction  = "in"
    protocol   = "tcp"
    port       = "22"
    source_ips = ["0.0.0.0/0", "::/0"]
  }

  # HTTP
  rule {
    direction  = "in"
    protocol   = "tcp"
    port       = "80"
    source_ips = ["0.0.0.0/0", "::/0"]
  }

  # HTTPS
  rule {
    direction  = "in"
    protocol   = "tcp"
    port       = "443"
    source_ips = ["0.0.0.0/0", "::/0"]
  }

  # Webhook Receiver (nur von Supabase IPs oder offen — später einschränken)
  rule {
    direction  = "in"
    protocol   = "tcp"
    port       = "9000"
    source_ips = ["0.0.0.0/0", "::/0"]
  }
}

# ── Server ─────────────────────────────────────────────────────────────────────
resource "hcloud_server" "focuscall" {
  name         = "focuscall-prod"
  server_type  = "cax21"        # ARM64, 4 cores, 8GB RAM, 80GB disk — 6.60€/mo
  image        = "ubuntu-24.04"
  location     = "fsn1"         # Falkenstein, Germany
  ssh_keys     = [hcloud_ssh_key.focuscall.id]
  firewall_ids = [hcloud_firewall.focuscall.id]
  user_data    = templatefile("${path.module}/cloud-init.yml", {
    webhook_secret       = var.webhook_secret
    zeroclaw_repo        = var.zeroclaw_repo
  })

  labels = {
    env     = "production"
    project = "focuscall"
  }
}

# ── Outputs ────────────────────────────────────────────────────────────────────
output "server_ip" {
  value       = hcloud_server.focuscall.ipv4_address
  description = "Public IPv4 of the focuscall server"
}

output "webhook_url" {
  value       = "http://${hcloud_server.focuscall.ipv4_address}:9000"
  description = "Webhook receiver URL (set this in Supabase Edge Function)"
}
