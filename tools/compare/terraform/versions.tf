terraform {
  # Exact pins: the comparison must be reproducible on the same tool versions.
  required_version = "= 1.16.6"

  required_providers {
    local = {
      source  = "hashicorp/local"
      version = "= 2.9.1"
    }
    external = {
      source  = "hashicorp/external"
      version = "= 2.4.2"
    }
  }

  # State lives outside the clone: tf.sh passes -backend-config="workspace_dir=<root>/tfstate".
  backend "local" {}
}
