variable "scenario" {
  description = "Which operating system the guest boots: yocto (egw-gateway-image) or debian13."
  type        = string

  validation {
    condition     = contains(["yocto", "debian13"], var.scenario)
    error_message = "scenario must be one of: yocto, debian13."
  }
}

variable "desired_state" {
  description = "Desired power state of the guest. Terraform records the desire; the live state is read by `status`."
  type        = string
  default     = "running"

  validation {
    condition     = contains(["running", "stopped"], var.desired_state)
    error_message = "desired_state must be running or stopped."
  }
}

variable "compare_root" {
  description = "State root outside the clone (bases, disks, logs, results). Empty = the scripts' default $HOME/egw-compare."
  type        = string
  default     = ""
}
