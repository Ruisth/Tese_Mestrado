# egw-gateway-image-dev — bring-up variant of egw-gateway-image for QEMU
# diagnostics ONLY (PM fixed names: "adds debug-tweaks and the G1 container
# smoke package; QEMU-only").
#
# Identical to egw-gateway-image.bb (same packages, same operator account,
# same hardening drop-ins, same data-disk fstab entry) plus:
#   debug-tweaks         : root has an empty password and can log in on the
#                          serial console (runqemu 'nographic'). Over SSH the
#                          egw-gateway-config drop-in still wins: sshd_config
#                          includes /etc/ssh/sshd_config.d/*.conf on its line
#                          13, before the PermitRootLogin/PermitEmptyPasswords
#                          lines that debug-tweaks rewrites (rootfs-postcommands
#                          ssh_allow_root_login / ssh_allow_empty_password),
#                          and sshd keeps the first value of a keyword — so
#                          root stays refused over SSH and password logins
#                          stay disabled. Untested until the first boot:
#                          acceptance 'ssh -p 2222 root@127.0.0.1' refused.
#   egw-container-smoke  : the gate-G1 smoke script (docker info + one
#                          container; recipe byte-identical), useful on the
#                          first boot of the integrated profile before the
#                          compose stack is loaded.
#   EGW_AUTHORIZED_KEYS_REQUIRED = "0": a missing EGW_AUTHORIZED_KEYS_FILE
#                          only warns here, because the root console makes
#                          the image reachable; the campaign image keeps the
#                          hard failure.
# NEVER boot this image with anything but runqemu slirp on the WSL2 host,
# never give it a routable address, and never present it as the campaign
# image: the deployed artefact names carry 'egw-gateway-image-dev' precisely
# so the two cannot be confused in the evidence.
require egw-gateway-image.bb

SUMMARY = "EGW-OS bring-up image: egw-gateway-image plus debug-tweaks and the G1 smoke test (QEMU only)"

IMAGE_FEATURES += "debug-tweaks"

IMAGE_INSTALL:append = " egw-container-smoke"

EGW_AUTHORIZED_KEYS_REQUIRED = "0"
