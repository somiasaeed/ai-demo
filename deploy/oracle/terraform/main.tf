# Oracle Always-Free infrastructure for the AI Agent Hub.
# Provisions: VCN, internet gateway, route table, public subnet, security list
# (SSH/80/443 open), and a Ubuntu 22.04 compute instance.
#
# Run from Oracle Cloud Shell (Terraform is pre-installed + pre-authenticated):
#   terraform init
#   terraform plan
#   terraform apply

terraform {
  required_version = ">= 1.3"
  required_providers {
    oci = {
      source  = "oracle/oci"
      version = ">= 5.0"
    }
  }
}

# In Cloud Shell this is pre-authenticated (delegation token).
provider "oci" {
  region = var.region
}

# ── First availability domain in the region ─────────────────────────────────
data "oci_identity_availability_domains" "ads" {
  compartment_id = var.compartment_ocid
}
locals {
  ad = data.oci_identity_availability_domains.ads.availability_domains[0].name
  # Cloud Shell key (manual access) + CI/CD deploy key, newline-joined when both set.
  ssh_keys = var.deploy_ssh_public_key == "" ? var.ssh_public_key : "${var.ssh_public_key}\n${var.deploy_ssh_public_key}"
}

# ── Network ─────────────────────────────────────────────────────────────────
resource "oci_core_vcn" "this" {
  compartment_id = var.compartment_ocid
  cidr_block     = "10.0.0.0/16"
  display_name   = "aihub-vcn"
  dns_label      = "aihubvcn"
}

resource "oci_core_internet_gateway" "this" {
  compartment_id = var.compartment_ocid
  vcn_id         = oci_core_vcn.this.id
  display_name   = "aihub-igw"
  enabled        = true
}

resource "oci_core_route_table" "this" {
  compartment_id = var.compartment_ocid
  vcn_id         = oci_core_vcn.this.id
  display_name   = "aihub-rt"

  route_rules {
    destination       = "0.0.0.0/0"
    destination_type  = "CIDR_BLOCK"
    network_entity_id = oci_core_internet_gateway.this.id
  }
}

resource "oci_core_security_list" "this" {
  compartment_id = var.compartment_ocid
  vcn_id         = oci_core_vcn.this.id
  display_name   = "aihub-sl"

  egress_security_rules {
    destination = "0.0.0.0/0"
    protocol    = "all"
  }

  dynamic "ingress_security_rules" {
    for_each = toset([22, 80, 443])
    content {
      source   = "0.0.0.0/0"
      protocol = "6" # TCP
      tcp_options {
        min = ingress_security_rules.value
        max = ingress_security_rules.value
      }
    }
  }
}

resource "oci_core_subnet" "this" {
  compartment_id             = var.compartment_ocid
  vcn_id                     = oci_core_vcn.this.id
  cidr_block                 = "10.0.0.0/24"
  display_name               = "aihub-public-subnet"
  route_table_id             = oci_core_route_table.this.id
  security_list_ids          = [oci_core_security_list.this.id]
  prohibit_public_ip_on_vnic = false
  dns_label                  = "aihubpub"
}

# ── Compute instance ────────────────────────────────────────────────────────
data "oci_core_images" "ubuntu" {
  compartment_id           = var.compartment_ocid
  operating_system         = "Canonical Ubuntu"
  operating_system_version = "22.04"
  shape                    = var.instance_shape
  sort_by                  = "TIMECREATED"
  sort_order               = "DESC"
}

resource "oci_core_instance" "this" {
  availability_domain = local.ad
  compartment_id      = var.compartment_ocid
  display_name        = var.instance_name
  shape               = var.instance_shape

  # shape_config only applies to the flexible A1 shape, not the fixed micro.
  dynamic "shape_config" {
    for_each = var.instance_shape == "VM.Standard.A1.Flex" ? [1] : []
    content {
      ocpus         = var.a1_ocpus
      memory_in_gbs = var.a1_memory_gb
    }
  }

  source_details {
    source_type             = "image"
    source_id               = data.oci_core_images.ubuntu.images[0].id
    boot_volume_size_in_gbs = var.boot_volume_gb
  }

  create_vnic_details {
    subnet_id        = oci_core_subnet.this.id
    assign_public_ip = true
  }

  # ssh_authorized_keys: manual-access key + CI/CD deploy key.
  # user_data: cloud-init that installs Docker and writes the prod compose/Caddyfile,
  # so a fresh `terraform apply` yields a deploy-ready server.
  metadata = {
    ssh_authorized_keys = local.ssh_keys
    user_data           = base64encode(file("${path.module}/cloud-init.yaml"))
  }
}
