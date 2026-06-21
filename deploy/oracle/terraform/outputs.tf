output "instance_public_ip" {
  value       = oci_core_instance.this.public_ip
  description = "Public IP of the created instance."
}

output "instance_ocid" {
  value = oci_core_instance.this.id
}

output "ssh_command" {
  value = "ssh -i <your-private-key> ubuntu@${oci_core_instance.this.public_ip}"
}
