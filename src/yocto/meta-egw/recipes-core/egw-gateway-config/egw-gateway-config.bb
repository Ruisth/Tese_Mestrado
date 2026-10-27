SUMMARY = "EGW gateway configuration: journald/timesyncd/sshd drop-ins, docker daemon.json, sudoers, tmpfiles, data-disk ordering"
DESCRIPTION = "Installs the guest-side configuration the integrated gateway \
needs beyond package defaults and beyond the byte-identical G1 recipe \
egw-base-config (which keeps the networkd DHCP profile and the docker.service \
enablement): journald limits for a persistent journal, a timesyncd NTP list, \
an sshd hardening drop-in (key-only operator login, no root), a docker \
daemon.json with bounded json-file logs, a sudoers rule for the operator, \
tmpfiles entries for the operator-owned deployment/evidence tree /opt/egw, \
and a docker.service drop-in that orders dockerd after the persistent data \
disk mounted on /var/lib/docker (working plan v2.0, unpublished, section 5 \
item 2; PM work order \
2026-09-17 item 3)."
LICENSE = "MIT"
LIC_FILES_CHKSUM = "file://${COMMON_LICENSE_DIR}/MIT;md5=0835ade698e0bcf8506ecda2f7b4f302"

SRC_URI = " \
    file://10-egw-journald.conf \
    file://10-egw-timesyncd.conf \
    file://10-egw-sshd.conf \
    file://daemon.json \
    file://egw-sudoers \
    file://egw.conf \
    file://10-egw-data-disk.conf \
"

# Scarthgap-era layout: file:// sources are fetched into ${WORKDIR}.
S = "${WORKDIR}"

# NTP servers for systemd-timesyncd (space separated), substituted into
# 10-egw-timesyncd.conf. Override in the kas manifest (block 29-time-sync)
# or local.conf, e.g. an institutional server, or on AWS the link-local
# Amazon Time Sync Service 169.254.169.123. DHCP-supplied NTP servers
# (networkd UseNTP=yes, the default) take precedence over NTP= at run time;
# FallbackNTP= is used only when NTP= and DHCP yield nothing (runqemu slirp
# offers no NTP option, so NTP= is what the integrated guest uses).
EGW_NTP_SERVERS ?= "0.pool.ntp.org 1.pool.ntp.org 2.pool.ntp.org 3.pool.ntp.org"
EGW_FALLBACK_NTP_SERVERS ?= "time.cloudflare.com"

do_install() {
    # journald: persistent, size-capped, no syslog forwarding. Drop-ins are
    # sorted by file name across /usr/lib and /etc, so "10-egw" overrides
    # systemd-conf's /usr/lib/systemd/journald.conf.d/00-systemd-conf.conf
    # (ForwardToSyslog=yes, RuntimeMaxUse=64M; systemd-conf_1.0.bb line 25,
    # file present in the G1 rootfs).
    install -d ${D}${sysconfdir}/systemd/journald.conf.d
    install -m 0644 ${WORKDIR}/10-egw-journald.conf \
        ${D}${sysconfdir}/systemd/journald.conf.d/10-egw.conf

    # timesyncd: explicit NTP list (build-time variables, see above).
    # /etc/systemd/timesyncd.conf exists in the G1 rootfs with an empty
    # [Time] section; systemd 255 reads timesyncd.conf.d/*.conf next to it.
    install -d ${D}${sysconfdir}/systemd/timesyncd.conf.d
    sed -e 's|@EGW_NTP_SERVERS@|${EGW_NTP_SERVERS}|' \
        -e 's|@EGW_FALLBACK_NTP_SERVERS@|${EGW_FALLBACK_NTP_SERVERS}|' \
        ${WORKDIR}/10-egw-timesyncd.conf \
        > ${D}${sysconfdir}/systemd/timesyncd.conf.d/10-egw.conf
    chmod 0644 ${D}${sysconfdir}/systemd/timesyncd.conf.d/10-egw.conf

    # sshd: poky's sshd_config (recipes-connectivity/openssh/openssh/
    # sshd_config, installed unchanged in the G1 rootfs) has
    # 'Include /etc/ssh/sshd_config.d/*.conf' on line 13, before every
    # default, and sshd keeps the FIRST value of a keyword, so this drop-in
    # wins over anything below it (including the PermitRootLogin /
    # PermitEmptyPasswords rewrites of debug-tweaks on the -dev image).
    install -d ${D}${sysconfdir}/ssh/sshd_config.d
    install -m 0644 ${WORKDIR}/10-egw-sshd.conf \
        ${D}${sysconfdir}/ssh/sshd_config.d/10-egw.conf

    # Docker daemon configuration. docker-moby ships an EMPTY /etc/docker
    # (docker.inc line 120) and its docker.service starts
    # '/usr/bin/dockerd -H fd:// --containerd=/run/containerd/containerd.sock'
    # with no storage/log flags, so the keys in daemon.json (dockerd's
    # default configuration file) conflict with nothing on the command
    # line. 'hosts' is deliberately absent from daemon.json: it would
    # collide with '-H fd://' and dockerd refuses to start on a conflict.
    install -d ${D}${sysconfdir}/docker
    install -m 0644 ${WORKDIR}/daemon.json ${D}${sysconfdir}/docker/daemon.json

    # sudo: the rule goes into /etc/sudoers.d/egw (mode 0440, owner root,
    # file name without '.').
    # Verified in the package built on 2026-09-18 (build-integrated/,
    # packages-split/sudo-lib/etc/sudoers line 139): poky's sudo_1.9.17p2
    # ships an active '@includedir /etc/sudoers.d'. Still to be confirmed
    # on the booted guest: 'visudo -c', 'sudo -l -U egw' and
    # 'ssh -p 2222 egw@127.0.0.1 sudo -n true'.
    # The directory is also owned by sudo-lib, which ships it as 0750
    # root:root (rpm -qplv sudo-lib-1.9.17p2-r0.cortexa57.rpm). RPM treats a
    # mode difference on a shared directory as a file conflict: the first
    # build (commit 68f9ae7, 2026-09-18) created it 0755 and do_rootfs failed
    # in the dnf transaction test. The mode here must stay identical to
    # sudo-lib's.
    install -d -m 0750 ${D}${sysconfdir}/sudoers.d
    install -m 0440 ${WORKDIR}/egw-sudoers ${D}${sysconfdir}/sudoers.d/egw

    # tmpfiles: operator-owned deployment/evidence tree, created at every
    # boot by systemd-tmpfiles-setup ('d' creates parents; /usr/lib/tmpfiles.d
    # is where the G1 rootfs keeps systemd's own entries).
    install -d ${D}${nonarch_libdir}/tmpfiles.d
    install -m 0644 ${WORKDIR}/egw.conf ${D}${nonarch_libdir}/tmpfiles.d/egw.conf

    # docker.service drop-in: dockerd must not start before the persistent
    # data disk is mounted on /var/lib/docker (fstab entry appended by
    # egw-gateway-image.bb). Placed under the unit directory docker-moby
    # installs its unit into (/usr/lib/systemd/system/docker.service), in
    # a drop-in directory of this package.
    install -d ${D}${systemd_system_unitdir}/docker.service.d
    install -m 0644 ${WORKDIR}/10-egw-data-disk.conf \
        ${D}${systemd_system_unitdir}/docker.service.d/10-egw-data-disk.conf
}

FILES:${PN} += " \
    ${sysconfdir}/systemd/journald.conf.d \
    ${sysconfdir}/systemd/timesyncd.conf.d \
    ${sysconfdir}/ssh/sshd_config.d \
    ${sysconfdir}/docker \
    ${sysconfdir}/sudoers.d \
    ${nonarch_libdir}/tmpfiles.d \
    ${systemd_system_unitdir}/docker.service.d \
"

CONFFILES:${PN} += " \
    ${sysconfdir}/systemd/journald.conf.d/10-egw.conf \
    ${sysconfdir}/systemd/timesyncd.conf.d/10-egw.conf \
    ${sysconfdir}/ssh/sshd_config.d/10-egw.conf \
    ${sysconfdir}/docker/daemon.json \
    ${sysconfdir}/sudoers.d/egw \
"

# systemd : journald/timesyncd/tmpfiles consumers of the files above
#           (resolved and timesyncd are PACKAGECONFIG options of the main
#           systemd package in Scarthgap, not separate packages).
# sudo    : /etc/sudoers.d/egw is only meaningful with sudo installed.
# The docker daemon.json and the docker.service drop-in assume docker-moby,
# which egw-gateway-image.bb installs explicitly; not declared here so the
# recipe can also be installed on a runtime-less diagnostic image (a
# drop-in for an absent unit is ignored by systemd).
# The sshd drop-in assumes openssh-sshd (IMAGE_FEATURES ssh-server-openssh).
RDEPENDS:${PN} += "systemd sudo"
