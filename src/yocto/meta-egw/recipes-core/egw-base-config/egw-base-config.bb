SUMMARY = "EGW base system configuration: networkd DHCP profile and docker enablement"
DESCRIPTION = "Installs a systemd-networkd .network file that enables DHCP \
on wired interfaces (en*/eth*, covering the QEMU virtio NIC) and statically \
enables docker.service so the OCI runtime is up after boot."
LICENSE = "MIT"
LIC_FILES_CHKSUM = "file://${COMMON_LICENSE_DIR}/MIT;md5=0835ade698e0bcf8506ecda2f7b4f302"

SRC_URI = "file://80-egw-wired.network"

# Scarthgap-era layout: file:// sources are fetched into ${WORKDIR}.
S = "${WORKDIR}"

do_install() {
    # DHCP on wired interfaces for systemd-networkd. /etc takes precedence
    # over /usr/lib network profiles, and "80-..." sorts before oe-core's
    # optional "wired.network" from systemd-conf, so this file wins (both
    # configure DHCP, so either outcome is functionally identical).
    install -d ${D}${sysconfdir}/systemd/network
    install -m 0644 ${WORKDIR}/80-egw-wired.network \
        ${D}${sysconfdir}/systemd/network/80-egw-wired.network

    # Statically enable docker.service for multi-user.target. This is
    # idempotent with meta-virtualization's own systemd enablement of
    # docker (its rootfs-time 'systemctl enable' is a no-op when the wants
    # symlink already exists and points at the right unit).
    install -d ${D}${sysconfdir}/systemd/system/multi-user.target.wants
    ln -sf ${systemd_system_unitdir}/docker.service \
        ${D}${sysconfdir}/systemd/system/multi-user.target.wants/docker.service
}

FILES:${PN} += " \
    ${sysconfdir}/systemd/network \
    ${sysconfdir}/systemd/system \
"

RDEPENDS:${PN} += "systemd"
