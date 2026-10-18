# Comparison environments: one module, one workspace per scenario (tf.sh selects it).
#
# What Terraform owns here: the DESIRED lifecycle of one guest and the prepared, disposable
# artefacts (work disks, state directory). What it does not own: the QEMU process itself. The live
# state is read, never inferred, by tools/compare/compare_env.sh status (an `external` data source)
# and compared with the desire in the `check` block below. A second `apply` without changes runs no
# provisioner: nothing is duplicated or recreated.

locals {
  tools_dir  = abspath("${path.module}/..")
  script     = "${local.tools_dir}/compare_env.sh"
  up         = "${local.tools_dir}/up.sh"
  env_file   = "${local.tools_dir}/scenarios/${var.scenario}.env"
  env_prefix = var.compare_root == "" ? "" : "EGW_COMPARE_ROOT='${var.compare_root}' "
}

# Prepared artefacts: immutable base copies verified by checksum, a fresh qcow2 overlay as the root
# disk, a fresh 32 GiB raw data disk (ext4, label egw-data), the scenario manifest. Replaced only when
# the scenario file changes (a different base); a script edit never destroys disks.
resource "terraform_data" "prepared" {
  input = {
    scenario            = var.scenario
    script              = local.script
    env_prefix          = local.env_prefix
    scenario_env_sha256 = filesha256(local.env_file)
    script_sha256       = filesha256(local.script)
    lib_sha256          = filesha256("${local.tools_dir}/lib.sh")
  }
  triggers_replace = [var.scenario, filesha256(local.env_file)]

  lifecycle {
    precondition {
      condition     = terraform.workspace == var.scenario
      error_message = "The workspace must be named after the scenario (tf.sh selects it): workspace '${terraform.workspace}', scenario '${var.scenario}'."
    }
  }

  provisioner "local-exec" {
    interpreter = ["bash", "-c"]
    command     = "${local.env_prefix}bash '${local.script}' prepare '${var.scenario}'"
  }

  # destroy removes ONLY this scenario's work disks and state, after a controlled stop, and keeps
  # bases, logs and results; it refuses (non-zero, so the destroy fails safely) while the guest runs.
  provisioner "local-exec" {
    when        = destroy
    interpreter = ["bash", "-c"]
    command     = "${self.output.env_prefix}bash '${self.output.script}' destroy '${self.output.scenario}'"
  }
}

# Desired power state. Creating it runs up.sh: start the guest, wait for ssh, bring the application
# stack up (idempotent: pinned images already on the data disk are not pulled again) and confirm it
# healthy; the environment is then left running. Destroying it (desired_state = stopped, or a
# destroy) runs the controlled stop, which never kills a QEMU process. A failed up leaves this
# resource tainted and the guest running for inspection: `tf.sh <s> stop` closes it; the next
# `apply` runs the controlled stop and then up again.
resource "terraform_data" "power" {
  count      = var.desired_state == "running" ? 1 : 0
  depends_on = [terraform_data.prepared]

  input = {
    scenario   = var.scenario
    script     = local.script
    up         = local.up
    env_prefix = local.env_prefix
  }
  triggers_replace = [terraform_data.prepared.id]

  provisioner "local-exec" {
    interpreter = ["bash", "-c"]
    command     = "${local.env_prefix}bash '${local.up}' '${var.scenario}'"
  }

  provisioner "local-exec" {
    when        = destroy
    interpreter = ["bash", "-c"]
    command     = "${self.output.env_prefix}bash '${self.output.script}' stop '${self.output.scenario}'"
  }
}

# The live state, read after the power step so that `terraform output` reflects the apply.
data "external" "status" {
  depends_on = [terraform_data.power]
  program    = ["bash", "-c", "${local.env_prefix}bash '${local.script}' status '${var.scenario}'"]
}

# Honest signal: a warning whenever the live state and the desired state disagree (for example a
# guest that ended on its own, or one started outside Terraform).
check "live_state_matches_desired" {
  data "external" "live" {
    program = ["bash", "-c", "${local.env_prefix}bash '${local.script}' status '${var.scenario}'"]
  }

  assert {
    condition     = (var.desired_state == "running") == (data.external.live.result.running == "true")
    error_message = "Live state (running=${data.external.live.result.running}, pid=${data.external.live.result.pid}) differs from desired_state=${var.desired_state} for scenario ${var.scenario}."
  }
}
