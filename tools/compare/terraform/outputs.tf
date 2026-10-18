output "scenario" {
  value = var.scenario
}

output "desired_state" {
  value = var.desired_state
}

output "status" {
  description = "Live state as read by compare_env.sh status at the end of this apply (strings)."
  value       = data.external.status.result
}

output "manifest_path" {
  value = data.external.status.result.manifest
}
