SUMMARY = "Container runtime smoke test producing gate-G1 evidence"
DESCRIPTION = "Installs /usr/bin/egw-container-smoke.sh, which verifies that \
'docker info' works, executes one container (offline docker-import of a \
minimal busybox rootfs by default, or 'docker run hello-world' when network \
access exists) and appends a timestamped PASS/FAIL line to \
/var/log/egw-smoke.log. Also ships an optional oneshot systemd unit that is \
NOT enabled by default."
LICENSE = "MIT"
LIC_FILES_CHKSUM = "file://${COMMON_LICENSE_DIR}/MIT;md5=0835ade698e0bcf8506ecda2f7b4f302"

SRC_URI = " \
    file://egw-container-smoke.sh \
    file://egw-container-smoke.service \
"

# Scarthgap-era layout: file:// sources are fetched into ${WORKDIR}.
S = "${WORKDIR}"

inherit systemd

SYSTEMD_SERVICE:${PN} = "egw-container-smoke.service"
# Deliberately not enabled: gate-G1 evidence is captured by running the
# script interactively on the recorded QEMU console. To run it on every
# boot instead: systemctl enable egw-container-smoke.service
SYSTEMD_AUTO_ENABLE:${PN} = "disable"

# The image installs docker-moby explicitly; this RDEPENDS documents the
# requirement for anyone installing the smoke test into another image.
RDEPENDS:${PN} += "docker-moby"

do_install() {
    install -d ${D}${bindir}
    install -m 0755 ${WORKDIR}/egw-container-smoke.sh \
        ${D}${bindir}/egw-container-smoke.sh

    install -d ${D}${systemd_system_unitdir}
    install -m 0644 ${WORKDIR}/egw-container-smoke.service \
        ${D}${systemd_system_unitdir}/egw-container-smoke.service
}
