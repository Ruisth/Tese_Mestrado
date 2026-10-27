SUMMARY = "C2DTA Edge Gateway OS image (EGW-OS) that hosts the full digital-twin container stack"
DESCRIPTION = "Headless ARM64 edge-gateway operating system built with Yocto \
(Poky Scarthgap): systemd init, systemd-networkd DHCP, systemd-resolved DNS, \
systemd-timesyncd NTP, OpenSSH (key-only operator login, no root login) and \
the moby/docker OCI runtime with the Compose V2 plugin from \
meta-virtualization. It hosts the six containers of the local digital-twin \
core (Mosquitto, Eclipse Ditto gateway/policies/things, MongoDB, MQTT-to-Ditto \
controller) INSIDE the guest (ADR 0008 and plan v2.0 sections 2 and 5 - the \
working revision of 2026-09-16, not yet published on dev; PM work \
order 2026-09-17 item 3). The host carries no Python, JVM, MongoDB, \
Mosquitto, Ditto, DIDComm/ACA-Py, ledger or IPFS software: everything the \
C2DTA paper's EGW does beyond the OS layer lives in a container or is out of \
scope. First target: the INTEGRATED QEMU/TCG profile on qemuarm64 \
(kas/egw-qemuarm64-integrated.yml — ARM64 emulated on an x86-64 host, \
functional/integration evidence only); the native ARM64 route \
(kas/egw-genericarm64.yml) builds the same recipe later. This recipe is NOT \
egw-image.bb: the gate-G1 image and its sealed evidence stay untouched."
LICENSE = "MIT"

# core-image       : IMAGE_FEATURES handling (ssh-server-openssh) and the
#                    packagegroup-core-boot + packagegroup-base-extended
#                    base set.
# extrausers       : EXTRA_USERS_PARAMS below (operator account).
# image-buildinfo  : writes /etc/buildinfo with the layer revisions and the
#                    variables in IMAGE_BUILDINFO_VARS (poky
#                    meta/classes/image-buildinfo.bbclass), so every run can
#                    be bound to the exact image build and runqemu profile
#                    (PM item 7; capture-sut-environment.sh should record it).
inherit core-image extrausers image-buildinfo

# The QB_* values are the runqemu profile written into qemuboot.conf; listing
# them here records CPU model, SMP and memory inside the guest as well.
IMAGE_BUILDINFO_VARS = "DISTRO DISTRO_VERSION MACHINE TUNE_FEATURES IMAGE_NAME QB_CPU QB_SMP QB_MEM EGW_HOSTNAME"

# ssh-server-openssh : full OpenSSH sshd (not dropbear) so evidence files can
#                      be copied out over scp/sftp and the harness can open
#                      its 'ssh -L' tunnels to the controller (:8000) and
#                      the Ditto gateway (:8080), both loopback-only in
#                      compose.yaml.
# debug-tweaks       : deliberately ABSENT. On the G1 image it made root
#                      passwordless and rewrote PermitRootLogin /
#                      PermitEmptyPasswords to 'yes' in sshd_config
#                      (poky rootfs-postcommands.bbclass:
#                      ssh_allow_empty_password, ssh_allow_root_login).
#                      Working plan v2.0 (unpublished) section 5 item 2 and PM item 3 forbid that
#                      on the integrated profile. Without it,
#                      zap_empty_root_password (rootfs-postcommands.bbclass
#                      line 8) locks root ('root:*:'). For QEMU bring-up
#                      with a root serial console use egw-gateway-image-dev.
IMAGE_FEATURES += "ssh-server-openssh"

# docker-moby         : OCI runtime (moby 25.0.9, meta-virtualization
#                       recipes-containers/docker/docker-moby_git.bb +
#                       docker.inc); RDEPENDS util-linux (whole meta-package:
#                       lsblk, findmnt, lscpu, mount, blkid ...), iptables,
#                       containerd, runc, tini; RRECOMMENDS the nf-nat,
#                       nf-conntrack-netlink, xt-addrtype, xt-masquerade and
#                       dm-thin-pool modules. Creates the 'docker' group at
#                       package-install time (docker.inc line 140,
#                       GROUPADD_PARAM = "-r docker").
# docker-compose      : Compose V2 CLI plugin (docker-compose_git.bb, PV
#                       v2.26.0, PACKAGECONFIG default 'docker-plugin'):
#                       do_install lines 66-69 place the binary in
#                       ${nonarch_libdir}/docker/cli-plugins/docker-compose
#                       = /usr/lib/docker/cli-plugins, one of the four
#                       system plugin directories the docker CLI 25.0.9
#                       searches (cli/cli-plugins/manager/manager_unix.go
#                       lines 6-7 in the moby source of the build tree), so
#                       'docker compose' — which every deployment script
#                       calls — resolves without configuration. Never built
#                       in the G1 tree: its first build is an acceptance
#                       step ('docker compose version' -> v2.26.0).
# ca-certificates     : TLS trust store for registry pulls and curl to
#                       public hosts (the MQTT/TLS trust is the project's
#                       own dev CA mounted into the containers, not this
#                       store).
# curl                : measure-cold-start.sh polls /ready with
#                       'curl -s -o /dev/null -w %{http_code}'; BusyBox
#                       wget cannot report the status code
#                       (poky recipes-support/curl/curl_8.7.1.bb, openssl
#                       backend in the default PACKAGECONFIG).
# openssl-bin         : generate-dev-tls.sh (dev CA + broker certificate
#                       with SAN) runs openssl on the guest.
# kernel-modules      : all modules built for linux-yocto (about 8 MiB on
#                       G1, 296 packages). Docker's own RRECOMMENDS name
#                       only five; the blanket package is kept because the
#                       full stack (bridge/veth/NAT chains, overlay2, MongoDB
#                       and Ditto networking) has never run on this kernel,
#                       and the exact list is an optimisation to derive from
#                       'lsmod' after a complete compose run. The kernel
#                       Image package itself is kept OUT of the rootfs by
#                       the kas manifests, each in its own way:
#                       kas/egw-qemuarm64-integrated.yml names
#                       kernel-image-<version> in BAD_RECOMMENDATIONS;
#                       kas/egw-genericarm64.yml relies on the machine-scoped
#                       linux-yocto bbappend (blank RRECOMMENDS of
#                       kernel-base) plus the removal of the 'efi' machine
#                       feature.
# openssh-sftp-server : lets modern scp (sftp protocol) copy evidence out.
# sudo                : controlled privilege for the operator account
#                       (/etc/sudoers.d/egw from egw-gateway-config); poky
#                       recipes-extended/sudo/sudo_1.9.17p2.bb, built
#                       --without-pam because 'pam' is not in
#                       DISTRO_FEATURES.
# e2fsprogs-resize2fs : manual fallback for growing the data-disk file
#                       system if systemd-growfs (the automatic path, see
#                       egw_add_data_disk_fstab) has to be bypassed.
# e2fsprogs-e2fsck    : repairs the data disk after an unclean QEMU exit
#                       (the fstab entry has passno 0, so nothing runs
#                       fsck automatically). Both are sub-packages of
#                       e2fsprogs_1.47.0.bb line 88.
# egw-base-config     : the G1 recipe, byte-identical: networkd DHCP
#                       profile (80-egw-wired.network) and the
#                       docker.service enablement symlink.
# egw-gateway-config  : this profile's additions: journald / timesyncd /
#                       sshd drop-ins, docker daemon.json, sudoers rule,
#                       tmpfiles for /opt/egw, docker.service drop-in for
#                       the data disk.
# NOT installed on purpose: tzdata (the guest, the containers and the
# harness run in UTC; the harness windows samples by UTC wall-clock time),
# egw-container-smoke (G1-only; re-added by egw-gateway-image-dev),
# util-linux-* singletons (already in the util-linux meta-package that
# docker-moby depends on).
IMAGE_INSTALL:append = " \
    docker-moby \
    docker-compose \
    ca-certificates \
    curl \
    openssl-bin \
    kernel-modules \
    openssh-sftp-server \
    sudo \
    e2fsprogs-resize2fs \
    e2fsprogs-e2fsck \
    egw-base-config \
    egw-gateway-config \
"

# Only the C/POSIX locale: the runbook and the containers run with TZ=UTC
# and ASCII output; poky's default installs 'c en-us en-gb' (G1
# testdata.json IMAGE_LINGUAS) and the glibc locale packages with it.
IMAGE_LINGUAS = ""

# Operator account (working plan v2.0, unpublished, section 5 item 2 / PM item 3: SSH key access,
# controlled service access, no passwordless root).
#  - 'egw', uid 1000 / gid 1000, member of 'docker' so it drives dockerd
#    without sudo; sudo NOPASSWD (egw-gateway-config) for systemctl /
#    systemd-run / journalctl, which the harness collector hooks need.
#  - uid 1000 is the uid the controller container runs as (src/Dockerfile:
#    useradd --uid 1000 egw): the deployment tree and the data/events bind
#    mount it writes are owned by this uid on the guest (tmpfiles in
#    egw-gateway-config pre-create them), so no chown step is needed and
#    directories are never created by root on first start (PM item 3).
#  - PASSWORD FIELD: '-p '*'' writes 'egw:*:' into /etc/shadow — an
#    unusable password that is NOT a locked account. useradd without -p
#    writes '!' (every useradd-created account in the G1 rootfs has it,
#    e.g. 'sshd:!:'), and poky's OpenSSH 9.6p1 is built with
#    LOCKED_PASSWD_PREFIX "!" (config.h line 1709 of the G1 build):
#    platform.c lines 245-247 report such an account as locked and auth.c
#    line 112 refuses it ('User egw not allowed because account is
#    locked') even with a valid key, because PAM is off. '*' is the
#    convention rootfs-postcommands.bbclass line 243 uses for root. The
#    quoting is the documented extrausers idiom ("useradd -p '' tester" in
#    extrausers.bbclass): the setting passes through eval in
#    useradd_base.bbclass perform_useradd (line 43), where the inner shell
#    removes the quotes.
#  - Password authentication is refused by the sshd drop-in and root is
#    locked (see IMAGE_FEATURES), so access is by the public key installed
#    below only.
# The 'docker' group already exists at this point: docker-moby creates it
# at package-install time, and ROOTFS_POSTPROCESS_COMMAND (where
# extrausers runs set_user_group) executes after package installation.
# Acceptance after the build: 'tar -xjOf <image>.rootfs.tar.bz2 ./etc/shadow
# | grep ^egw:' prints 'egw:*:', never 'egw:!:'.
EXTRA_USERS_PARAMS = "\
    groupadd -g 1000 egw; \
    useradd -u 1000 -g egw -G docker -m -d /home/egw -s /bin/sh -p '*' egw; \
"

# Public key for the operator account, supplied AT BUILD TIME through the
# environment: the kas manifests declare EGW_AUTHORIZED_KEYS_FILE in their
# 'env:' block, kas adds it to BB_ENV_PASSTHROUGH_ADDITIONS, BitBake sees
# it here. Contents are copied into /home/egw/.ssh/authorized_keys; the file
# itself is never stored in the layer, and a private key is refused.
# EGW_AUTHORIZED_KEYS_REQUIRED = "1": the build FAILS when the variable is
# unset or empty (an image with key-only SSH and a locked root would be
# unreachable, and a silently unreachable image is the failure mode PM item
# 3 forbids). egw-gateway-image-dev sets it to "0" (warning only) because
# that image has a root serial console for QEMU bring-up.
EGW_AUTHORIZED_KEYS_FILE ?= ""
EGW_AUTHORIZED_KEYS_REQUIRED ?= "1"
# Re-run do_rootfs when the key file's CONTENT changes, not only its path.
do_rootfs[file-checksums] += "${@('%s:True' % d.getVar('EGW_AUTHORIZED_KEYS_FILE')) if d.getVar('EGW_AUTHORIZED_KEYS_FILE') else ''}"

# Second persistent disk for /var/lib/docker (see kas/egw-qemuarm64-integrated.yml
# block 50 for the choice). "1" appends the fstab entry below; a manifest
# that keeps Docker on the root file system (e.g. a native VM with one
# large disk) sets EGW_DOCKER_DATA_DISK = "0". The label must match the one
# scripts/run-qemu-integrated.sh gives the disk file (mkfs.ext4 -L).
EGW_DOCKER_DATA_DISK ?= "1"
EGW_DOCKER_DATA_DISK_LABEL ?= "egw-data"

# Persistent /var/log and the guest hostname are set HERE, in the assembled
# rootfs, and NOT through VOLATILE_LOG_DIR / hostname:pn-base-files. Both
# variables reach task signatures far beyond base-files: VOLATILE_LOG_DIR
# through FILESYSTEM_PERMS_TABLES (bitbake.conf line 387, read by
# oe.package.fixup_perms in every do_package — present in the G1 sigdata of
# busybox, linux-yocto, systemd and dbus alike), the hostname override
# through useradd.bbclass line 12 (DEPENDS on base-files for systemd, dbus,
# docker-moby ...). Either would rebuild the G1 package set in the new build
# directory; kas/egw-qemuarm64-integrated.yml block 28 carries the evidence.
# EGW_PERSISTENT_VAR_LOG = "1": replace base-files' '/var/log -> volatile/log'
#   symlink (base-files_3.0.14.bb lines 57, 86-87) with a directory on the
#   root file system and pre-create /var/log/journal. systemd's tmpfiles
#   'L /var/log - - - - /var/volatile/log' (00-create-volatile.conf) is a
#   silent no-op on an existing directory (tmpfiles.c create_symlink,
#   systemd 255.21: not 'L+', returns 0 at log_debug), and
#   'z /var/log/journal 2755 root systemd-journal' (tmpfiles.d/systemd.conf
#   line 27) sets the ownership at boot; journald (Storage=persistent from
#   egw-gateway-config) creates /var/log/journal/<machine-id> itself after
#   systemd-journal-flush.service. "0" keeps poky's volatile log.
# EGW_HOSTNAME: written to /etc/hostname and to the '127.0.1.1' line of
#   /etc/hosts (the two files base-files_3.0.14.bb lines 113-116 fill with
#   ${MACHINE}); empty keeps base-files' value. Recorded in /etc/buildinfo.
EGW_PERSISTENT_VAR_LOG ?= "1"
EGW_HOSTNAME ?= ""

# Scarthgap: ROOTFS_POSTPROCESS_COMMAND entries are whitespace separated
# (oe/utils.py execute_pre_post_process lines 263-265: ';' is replaced by a
# space and the string is split on whitespace; rootfs-postcommands.bbclass
# entries end with a space). The extrausers class appended 'set_user_group'
# at inherit time, so the functions below run after the 'egw' user and its
# home exist, and after every package is installed (base-files' /var/log
# symlink and /etc/hostname are in place to be replaced).
ROOTFS_POSTPROCESS_COMMAND:append = " egw_install_authorized_keys egw_add_data_disk_fstab egw_persistent_var_log egw_set_hostname"

egw_install_authorized_keys() {
    if [ -z "${EGW_AUTHORIZED_KEYS_FILE}" ]; then
        if [ "${EGW_AUTHORIZED_KEYS_REQUIRED}" = "1" ]; then
            bbfatal "EGW_AUTHORIZED_KEYS_FILE is unset: ${PN} would accept no SSH login (password authentication is disabled, root is locked). Export EGW_AUTHORIZED_KEYS_FILE=/path/to/key.pub in the shell that runs kas (e.g. ssh-keygen -t ed25519 -f ~/.ssh/egw_campaign; export EGW_AUTHORIZED_KEYS_FILE=~/.ssh/egw_campaign.pub), or build egw-gateway-image-dev for console-only bring-up."
        fi
        bbwarn "EGW_AUTHORIZED_KEYS_FILE is unset: no SSH key installed for user 'egw'; ${PN} accepts no SSH login (serial console only)."
        return 0
    fi
    if [ ! -r "${EGW_AUTHORIZED_KEYS_FILE}" ]; then
        bbfatal "EGW_AUTHORIZED_KEYS_FILE='${EGW_AUTHORIZED_KEYS_FILE}' is not readable on the build host."
    fi
    if grep -q "PRIVATE KEY" "${EGW_AUTHORIZED_KEYS_FILE}"; then
        bbfatal "EGW_AUTHORIZED_KEYS_FILE points at a PRIVATE key; pass the .pub file."
    fi
    if ! grep -Eq '^(ssh-ed25519|ssh-rsa|ecdsa-sha2-nistp[0-9]+|sk-ssh-ed25519@openssh.com|sk-ecdsa-sha2-nistp256@openssh.com) ' "${EGW_AUTHORIZED_KEYS_FILE}"; then
        bbfatal "EGW_AUTHORIZED_KEYS_FILE='${EGW_AUTHORIZED_KEYS_FILE}' contains no OpenSSH public key line."
    fi
    install -d -m 0700 ${IMAGE_ROOTFS}/home/egw/.ssh
    install -m 0600 "${EGW_AUTHORIZED_KEYS_FILE}" ${IMAGE_ROOTFS}/home/egw/.ssh/authorized_keys
    chown -R 1000:1000 ${IMAGE_ROOTFS}/home/egw/.ssh
}

# Data disk for Docker: one /etc/fstab line (base-files' stock fstab has no
# entry for /var/lib/docker; docker-moby ships no /var/lib/docker directory,
# dockerd creates it at first start). Why fstab rather than a native
# .mount unit: systemd-fstab-generator turns 'x-systemd.growfs' into
# systemd-growfs@var-lib-docker.service (systemd 255.21 source in the
# build tree, src/fstab-generator/fstab-generator.c line 806 parses the
# option and lines 659-660 hook the unit for the mount), so a disk file
# enlarged on the host is grown in the guest at the next boot; a native
# .mount unit gets no such hook. Options:
#   nofail                   the boot never drops to emergency mode when the
#                            disk is absent; docker.service alone fails,
#                            because egw-gateway-config's drop-in sets
#                            RequiresMountsFor=/var/lib/docker (visible in
#                            'systemctl --failed', PM item 3).
#   x-systemd.device-timeout limits the wait for a missing disk to 30 s.
#   passno 0                 no automatic fsck (e2fsprogs-e2fsck is installed
#                            for a manual check after an unclean exit).
# LABEL= resolves through udev's 60-persistent-storage.rules (present in
# the G1 rootfs at /usr/lib/udev/rules.d/) to /dev/disk/by-label/<label>.
egw_add_data_disk_fstab() {
    if [ "${EGW_DOCKER_DATA_DISK}" != "1" ]; then
        bbnote "${PN}: EGW_DOCKER_DATA_DISK != 1, /var/lib/docker stays on the root file system"
        return 0
    fi
    if grep -q '/var/lib/docker' ${IMAGE_ROOTFS}/etc/fstab; then
        bbfatal "egw_add_data_disk_fstab: /etc/fstab already has a /var/lib/docker entry"
    fi
    install -d -m 0710 ${IMAGE_ROOTFS}/var/lib/docker
    printf '%s\n' \
        '# EGW persistent Docker data disk (egw-gateway-image.bb): images, overlay2' \
        '# layers, named volumes and json-file logs. Created on the host by' \
        '# scripts/run-qemu-integrated.sh (mkfs.ext4 -L ${EGW_DOCKER_DATA_DISK_LABEL}) and attached per run.' \
        'LABEL=${EGW_DOCKER_DATA_DISK_LABEL}  /var/lib/docker  ext4  defaults,nofail,x-systemd.growfs,x-systemd.device-timeout=30s  0  0' \
        >> ${IMAGE_ROOTFS}/etc/fstab
}

# Persistent /var/log on the root file system (see EGW_PERSISTENT_VAR_LOG
# above). Idempotent: if a manifest ever sets VOLATILE_LOG_DIR = "no" (none
# in this change set does; both kas profiles use EGW_PERSISTENT_VAR_LOG),
# /var/log is already a directory and only gains the journal sub-directory. Files that
# packages placed under /var/volatile/log at do_package time stay there
# (on G1 that is only egw-container-smoke's log, -dev image).
egw_persistent_var_log() {
    if [ "${EGW_PERSISTENT_VAR_LOG}" != "1" ]; then
        bbnote "${PN}: EGW_PERSISTENT_VAR_LOG != 1, /var/log stays as base-files installed it"
        return 0
    fi
    if [ -L ${IMAGE_ROOTFS}/var/log ]; then
        rm -f ${IMAGE_ROOTFS}/var/log
    elif [ -d ${IMAGE_ROOTFS}/var/log ]; then
        bbnote "${PN}: /var/log is already a directory"
    elif [ -e ${IMAGE_ROOTFS}/var/log ]; then
        bbfatal "egw_persistent_var_log: ${IMAGE_ROOTFS}/var/log is neither a symlink nor a directory"
    fi
    install -d -m 0755 ${IMAGE_ROOTFS}/var/log
    # Mode/group (2755 root:systemd-journal) are applied at boot by
    # tmpfiles.d/systemd.conf; only the directory has to exist.
    install -d -m 0755 ${IMAGE_ROOTFS}/var/log/journal
}

# Guest hostname (see EGW_HOSTNAME above). base-files writes
# '/etc/hostname' = ${MACHINE} and appends '127.0.1.1 ${MACHINE}' to
# /etc/hosts (base-files_3.0.14.bb lines 113-116); both are rewritten here.
egw_set_hostname() {
    if [ -z "${EGW_HOSTNAME}" ]; then
        bbnote "${PN}: EGW_HOSTNAME empty, hostname stays '$(cat ${IMAGE_ROOTFS}/etc/hostname 2>/dev/null)'"
        return 0
    fi
    echo "${EGW_HOSTNAME}" > ${IMAGE_ROOTFS}/etc/hostname
    if grep -q '^127\.0\.1\.1[[:space:]]' ${IMAGE_ROOTFS}/etc/hosts; then
        sed -i -e 's/^127\.0\.1\.1[[:space:]].*/127.0.1.1 ${EGW_HOSTNAME}/' ${IMAGE_ROOTFS}/etc/hosts
    else
        echo "127.0.1.1 ${EGW_HOSTNAME}" >> ${IMAGE_ROOTFS}/etc/hosts
    fi
}

# Free space added to the root file system at build time, in KiB (2 GiB —
# the G1 value, so the deployed .ext4 stays about 2.6 GB). The root file
# system holds the OS, /opt/egw (deployment tree, image archives loaded
# once, data/events at 1 Hz), /home/egw and the journal capped at 256 MiB;
# Docker images, layers, volumes and container logs live on the data disk
# (egw_add_data_disk_fstab), so this value does not size the stack.
IMAGE_ROOTFS_EXTRA_SPACE = "2097152"
