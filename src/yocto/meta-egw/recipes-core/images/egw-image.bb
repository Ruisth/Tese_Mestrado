SUMMARY = "C2DTA Edge Gateway base image (EGW-OS) for qemuarm64"
DESCRIPTION = "Minimal ARM64 edge-gateway image: systemd init, \
systemd-networkd DHCP networking, OpenSSH server, CA certificates and the \
moby/docker OCI runtime from meta-virtualization. Functional validation \
target for gate G1 (clean build, two QEMU boots, one executed container). \
Deliberately contains no Raspberry Pi specific packages (plan section 5.1)."
LICENSE = "MIT"

inherit core-image

# ssh-server-openssh : full OpenSSH sshd (not dropbear) so evidence files can
#                      be copied out over scp/sftp.
# debug-tweaks       : development-only conveniences (root login without a
#                      password on the QEMU console) needed for the G1
#                      bring-up. Never present this image as hardened and
#                      remove the feature for anything beyond functional
#                      validation in QEMU.
IMAGE_FEATURES += "ssh-server-openssh debug-tweaks"

# docker-moby         : OCI runtime (moby) from meta-virtualization; pulls in
#                       containerd/runc via its own dependencies.
# ca-certificates     : TLS trust store, required for registry access when the
#                       online smoke path (docker run hello-world) is used.
# kernel-modules      : install all modules built for linux-yocto. With the
#                       'virtualization' DISTRO_FEATURE, meta-virtualization
#                       applies its container kernel fragments (cgroups,
#                       namespaces, overlayfs, netfilter, ...) to
#                       linux-yocto, and this makes sure every resulting
#                       module is available in the rootfs.
# openssh-sftp-server : lets modern scp (sftp protocol) copy evidence out.
# egw-base-config     : networkd DHCP profile + docker.service enablement.
# egw-container-smoke : gate-G1 container smoke test script (+ optional unit).
IMAGE_INSTALL:append = " \
    docker-moby \
    ca-certificates \
    kernel-modules \
    openssh-sftp-server \
    egw-base-config \
    egw-container-smoke \
"

# Extra free rootfs space in KiB (2 GiB) so container images and layers can
# be imported or pulled during the smoke test. Sizing headroom only — not a
# statement about expected image sizes or performance.
IMAGE_ROOTFS_EXTRA_SPACE = "2097152"
