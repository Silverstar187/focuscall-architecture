variable "hcloud_token" {
  description = "Hetzner Cloud API Token (from https://console.hetzner.cloud/projects)"
  type        = string
  sensitive   = true
}

variable "ssh_public_key_path" {
  description = "Path to SSH public key file"
  type        = string
  default     = "~/.ssh/openclaw_nopass.pub"
}

variable "webhook_secret" {
  description = "32-byte hex secret for HMAC webhook signing (generate: python3 -c 'import secrets; print(secrets.token_hex(32))')"
  type        = string
  sensitive   = true
}

variable "zeroclaw_repo" {
  description = "ZeroClaw GitHub repo to clone"
  type        = string
  default     = "https://github.com/b0xtch/zeroclaw"
}
