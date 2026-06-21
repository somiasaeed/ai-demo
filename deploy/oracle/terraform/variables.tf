variable "compartment_ocid" {
  type        = string
  description = "Root compartment (tenancy) OCID. In Cloud Shell: oci iam availability-domain list --query 'data[0].\"compartment-id\"'"
}

variable "region" {
  type        = string
  default     = "eu-milan-1"
  description = "Home region identifier."
}

variable "instance_name" {
  type    = string
  default = "aihub"
}

variable "instance_shape" {
  type        = string
  default     = "VM.Standard.E2.1.Micro" # 1 GB, always available
  description = "Use VM.Standard.A1.Flex for more RAM (up to 4 OCPU / 24 GB free)."
}

variable "a1_ocpus" {
  type        = number
  default     = 2
  description = "OCPU count when instance_shape = VM.Standard.A1.Flex."
}

variable "a1_memory_gb" {
  type        = number
  default     = 8
  description = "Memory (GB) when instance_shape = VM.Standard.A1.Flex."
}

variable "boot_volume_gb" {
  type        = number
  default     = 50
  description = "Boot volume size. Always-Free total block storage is 200 GB."
}

variable "ssh_public_key" {
  type        = string
  description = "Your SSH public key for manual access (Cloud Shell aihub_key.pub or ~/.ssh/id_rsa.pub)."
}

variable "deploy_ssh_public_key" {
  type        = string
  default     = ""
  description = "Public key for the GitHub Actions deploy user. Leave empty to skip. The matching private key is stored as the GitHub Secret DEPLOY_SSH_KEY."
}
