#!/usr/bin/env python3
"""Render the cloud-init NoCloud seed that provisions the ``debian13`` comparison guest.

    render_seed.py --pubkey FILE --hostname NAME --repo ROOT --out DIR [--mask-timers]

Writes ``DIR/user-data``, ``DIR/meta-data`` and ``DIR/vendor-data`` (the three files a NoCloud
seed served over HTTP consists of). The user-data is ``#cloud-config`` YAML written by hand
(standard library only): every guest configuration file the project's Yocto image carries is
embedded as a literal block scalar with the repository bytes unchanged, so that the Debian guest
reproduces the image's configuration verbatim. Only the two placeholders of the timesyncd
drop-in are substituted, with the values the egw-gateway-config recipe substitutes at build time.

Secrets: the seed carries the operator's PUBLIC key only. A file that holds private-key material
(``-----BEGIN``) is refused before anything is written. Nothing is read from the environment.

Exit codes: 0 written; 2 bad arguments, unreadable or unsuitable input.
"""
from __future__ import annotations

import argparse
import datetime as dt
import re
import subprocess
import sys
from pathlib import Path

SCENARIO = "debian13"
GATEWAY_CONFIG = Path("src/yocto/meta-egw/recipes-core/egw-gateway-config/files")
GATEWAY_RECIPE = Path("src/yocto/meta-egw/recipes-core/egw-gateway-config/egw-gateway-config.bb")
BASE_CONFIG = Path("src/yocto/meta-egw/recipes-core/egw-base-config/files")

# (guest path, repository source, mode). The guest paths are where the Yocto image installs the
# same bytes (egw-gateway-config.bb do_install; egw-base-config for the network profile), with
# /etc used where the image uses /usr/lib (tmpfiles.d, the docker.service drop-in): on Debian
# the package-owned /usr/lib trees must not be written to and /etc takes precedence anyway.
GUEST_FILES = (
    ("/etc/docker/daemon.json", GATEWAY_CONFIG / "daemon.json", "0644"),
    ("/etc/systemd/journald.conf.d/10-egw.conf", GATEWAY_CONFIG / "10-egw-journald.conf", "0644"),
    ("/etc/ssh/sshd_config.d/10-egw.conf", GATEWAY_CONFIG / "10-egw-sshd.conf", "0644"),
    ("/etc/sudoers.d/egw", GATEWAY_CONFIG / "egw-sudoers", "0440"),
    ("/etc/tmpfiles.d/egw.conf", GATEWAY_CONFIG / "egw.conf", "0644"),
    ("/etc/systemd/system/docker.service.d/10-egw-data-disk.conf", GATEWAY_CONFIG / "10-egw-data-disk.conf", "0644"),
    ("/etc/systemd/timesyncd.conf.d/10-egw.conf", GATEWAY_CONFIG / "10-egw-timesyncd.conf", "0644"),
    ("/etc/systemd/network/80-egw-wired.network", BASE_CONFIG / "80-egw-wired.network", "0644"),
)
TIMESYNCD_GUEST_PATH = "/etc/systemd/timesyncd.conf.d/10-egw.conf"

# The same line egw-gateway-image.bb appends to the image's /etc/fstab (egw_add_data_disk_fstab).
FSTAB_LINE = "LABEL=egw-data  /var/lib/docker  ext4  defaults,nofail,x-systemd.growfs,x-systemd.device-timeout=30s  0  0"

PACKAGES = ("docker.io", "docker-compose", "docker-cli", "containerd", "runc", "curl", "openssl",
            "ca-certificates", "e2fsprogs", "sudo")

HOSTNAME_RE = re.compile(r"^[a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?$")
PUBKEY_RE = re.compile(r"^(ssh-(ed25519|rsa|dss)|ecdsa-sha2-nistp(256|384|521)|sk-(ssh-ed25519|ecdsa-sha2-nistp256))(@openssh\.com)? [A-Za-z0-9+/]+=*( [^\r\n]*)?$")


class SeedError(Exception):
    """A reason the seed must not be written (reported, exit 2)."""


# --------------------------------------------------------------------------
# YAML emission (a small, explicit subset: mappings, sequences, quoted and literal scalars)
# --------------------------------------------------------------------------

def yaml_single(text: str) -> str:
    """A YAML single-quoted scalar: only the quote itself needs escaping (doubled)."""
    if "\n" in text or "\r" in text:
        raise SeedError("single-quoted scalars cannot hold line breaks")
    return "'" + text.replace("'", "''") + "'"


def yaml_double(text: str) -> str:
    """A YAML double-quoted scalar for text that may hold any printable character."""
    if any(ord(c) < 32 for c in text):
        raise SeedError("quoted scalar holds a control character")
    return '"' + text.replace("\\", "\\\\").replace('"', '\\"') + '"'


def yaml_flow_seq(items: list[str]) -> str:
    """A flow sequence whose items are all single-quoted (no plain-scalar ambiguity)."""
    return "[" + ", ".join(yaml_single(i) for i in items) + "]"


def yaml_block(text: str, indent: int) -> list[str]:
    """Lines of a literal block scalar whose content starts at column ``indent``.

    Returns the header (``|``, with the chomping indicator that reproduces the trailing newlines
    of ``text`` exactly, and an explicit indentation indicator when the first line starts with a
    space) followed by the content lines, each prefixed with ``indent`` spaces. The content is
    reproduced byte for byte by any YAML 1.1/1.2 parser.
    """
    if not text:
        raise SeedError("empty content cannot be a block scalar")
    if "\r" in text:
        raise SeedError("content holds a carriage return (a parser would fold it): source not LF-only")
    if text[:1] == "\t":
        raise SeedError("content starts with a tab: not representable as an indented block")
    if text.endswith("\n\n"):
        chomp = "+"
    elif text.endswith("\n"):
        chomp = ""
    else:
        chomp = "-"
    # The indentation indicator is relative to the parent node, two columns to the left.
    explicit = "2" if text[:1] == " " else ""
    header = "|" + explicit + chomp
    body = text[:-1] if text.endswith("\n") else text
    pad = " " * indent
    lines = [header]
    for line in body.split("\n"):
        lines.append(pad + line if line else "")
    return lines


# --------------------------------------------------------------------------
# inputs
# --------------------------------------------------------------------------

def read_pubkey(path: Path) -> str:
    """The first line of an OpenSSH public key file; private-key material is refused."""
    try:
        raw = path.read_bytes()
    except OSError as exc:
        raise SeedError(f"public key file unreadable: {exc}") from None
    if b"-----BEGIN" in raw or b"PRIVATE KEY" in raw:
        raise SeedError(f"{path} holds private-key material; pass the .pub file")
    text = raw.decode("utf-8", "replace")
    first = next((ln.strip() for ln in text.splitlines() if ln.strip()), "")
    if not first:
        raise SeedError(f"{path} is empty")
    if not PUBKEY_RE.match(first):
        raise SeedError(f"{path} does not start with an OpenSSH public key line")
    return first


def read_source(repo: Path, rel: Path) -> str:
    """The repository file as text (UTF-8, LF only, newline kept)."""
    path = repo / rel
    try:
        raw = path.read_bytes()
    except OSError as exc:
        raise SeedError(f"source file unreadable: {exc}") from None
    if not raw:
        raise SeedError(f"source file is empty: {path}")
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise SeedError(f"source file is not UTF-8: {path}: {exc}") from None


def recipe_variable(recipe_text: str, name: str, recipe: Path) -> str:
    match = re.search(rf'^{re.escape(name)}\s*\?=\s*"([^"\n]*)"\s*$', recipe_text, re.MULTILINE)
    if match is None:
        raise SeedError(f"{recipe} no longer defines {name} ?= \"...\"; update render_seed.py")
    return match.group(1)


def repo_commit(repo: Path) -> str:
    """HEAD of the repository the sources were read from, or 'unknown'."""
    try:
        done = subprocess.run(["git", "-C", str(repo), "rev-parse", "HEAD"], capture_output=True,
                              text=True, timeout=30, check=False)
    except (OSError, subprocess.SubprocessError):
        return "unknown"
    head = done.stdout.strip()
    return head if done.returncode == 0 and re.fullmatch(r"[0-9a-f]{40}", head) else "unknown"


# --------------------------------------------------------------------------
# rendering
# --------------------------------------------------------------------------

def render_user_data(hostname: str, pubkey: str, files: list[tuple[str, str, str]], buildinfo: str,
                     mask_timers: bool, rendered_utc: str, commit: str) -> str:
    out: list[str] = []
    add = out.append
    add("#cloud-config")
    add(f"# NoCloud user-data of the {SCENARIO} comparison scenario, rendered by")
    add(f"# tools/compare/debian/render_seed.py at {rendered_utc} from repository commit {commit}.")
    add("# write_files carries the guest configuration of the project's Yocto image byte for byte")
    add("# (egw-gateway-config, egw-base-config); only the timesyncd placeholders are substituted,")
    add("# exactly as the recipe does at build time. Public key only; no secret is in this file.")
    add(f"hostname: {hostname}")
    add(f"fqdn: {hostname}.localdomain")
    add("manage_etc_hosts: true")
    add("timezone: Etc/UTC")
    add("ssh_pwauth: false")
    add("disable_root: true")
    add("groups:")
    add("  - egw")
    # One user only (no 'default'): the operator account of the Yocto image, uid 1000, key-only.
    add("users:")
    add("  - name: egw")
    add("    uid: 1000")
    add("    primary_group: egw")
    add("    gecos: egw operator")
    add("    shell: /bin/sh")
    add("    lock_passwd: true")
    add(f"    sudo: {yaml_double('ALL=(ALL:ALL) NOPASSWD: ALL')}")
    add("    ssh_authorized_keys:")
    add(f"      - {yaml_double(pubkey)}")
    add("package_update: true")
    add("package_upgrade: false")
    add("packages:")
    for pkg in PACKAGES:
        add(f"  - {pkg}")
    # Early, once: the data disk goes under /var/lib/docker BEFORE docker.io's postinst starts
    # dockerd, so the first daemon already writes to the data disk (same fstab line as the image).
    add("bootcmd:")
    add("  - - cloud-init-per")
    add("    - once")
    add("    - egw-data-disk")
    add("    - sh")
    add("    - -c")
    script = "\n".join([
        "set -e",
        "mkdir -m 0710 -p /var/lib/docker",
        f"grep -q 'LABEL=egw-data' /etc/fstab || printf '%s\\n' {shell_single(FSTAB_LINE)} >> /etc/fstab",
        "systemctl daemon-reload",
        "mount /var/lib/docker || true",
    ]) + "\n"
    block = yaml_block(script, 6)
    add("    - " + block[0])
    out.extend(block[1:])
    add("write_files:")
    for guest_path, mode, content in files:
        add(f"  - path: {guest_path}")
        add("    owner: root:root")
        add(f"    permissions: {yaml_single(mode)}")
        block = yaml_block(content, 6)
        add("    content: " + block[0])
        out.extend(block[1:])
    add("  - path: /etc/egw-buildinfo")
    add("    owner: root:root")
    add("    permissions: '0644'")
    block = yaml_block(buildinfo, 6)
    add("    content: " + block[0])
    out.extend(block[1:])
    add("runcmd:")
    add("  - " + yaml_flow_seq(["usermod", "-aG", "docker", "egw"]))
    add("  - " + yaml_flow_seq(["systemctl", "daemon-reload"]))
    add("  - " + yaml_flow_seq(["systemd-tmpfiles", "--create", "egw.conf"]))
    add("  - " + yaml_flow_seq(["sh", "-c", "systemctl is-enabled systemd-networkd > /dev/null 2>&1"
                                           " || systemctl enable --now systemd-networkd || true"]))
    add("  - " + yaml_flow_seq(["systemctl", "restart", "docker"]))
    if mask_timers:
        add("  - " + yaml_flow_seq(["systemctl", "mask", "--now", "apt-daily.timer", "apt-daily-upgrade.timer"]))
    add("  - " + yaml_flow_seq(["sh", "-c", "dpkg-query -W -f='${binary:Package} ${Architecture} ${Version}\\n'"
                                           " > /etc/egw-buildinfo.packages"]))
    add("  - " + yaml_flow_seq(["touch", "/etc/cloud/cloud-init.disabled"]))
    add("  - " + yaml_flow_seq(["sync"]))
    add("power_state:")
    add("  mode: poweroff")
    add("  message: egw-firstboot-done")
    add("  timeout: 60")
    add("  condition: true")
    return "\n".join(out) + "\n"


def shell_single(text: str) -> str:
    """A POSIX shell single-quoted word."""
    return "'" + text.replace("'", "'\\''") + "'"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n", 1)[0])
    ap.add_argument("--pubkey", required=True, type=Path, help="OpenSSH PUBLIC key file (.pub)")
    ap.add_argument("--hostname", required=True, help="guest host name (lower-case label)")
    ap.add_argument("--repo", required=True, type=Path, help="repository root the sources are read from")
    ap.add_argument("--out", required=True, type=Path, help="directory to write user-data, meta-data, vendor-data")
    ap.add_argument("--mask-timers", action="store_true",
                    help="also mask apt-daily.timer and apt-daily-upgrade.timer on the guest")
    args = ap.parse_args(argv)
    try:
        if not HOSTNAME_RE.match(args.hostname):
            raise SeedError(f"hostname '{args.hostname}' is not a lower-case DNS label")
        pubkey = read_pubkey(args.pubkey)
        recipe_text = read_source(args.repo, GATEWAY_RECIPE)
        ntp = recipe_variable(recipe_text, "EGW_NTP_SERVERS", GATEWAY_RECIPE)
        fallback = recipe_variable(recipe_text, "EGW_FALLBACK_NTP_SERVERS", GATEWAY_RECIPE)
        files: list[tuple[str, str, str]] = []
        for guest_path, rel, mode in GUEST_FILES:
            content = read_source(args.repo, rel)
            if guest_path == TIMESYNCD_GUEST_PATH:
                content = content.replace("@EGW_NTP_SERVERS@", ntp).replace("@EGW_FALLBACK_NTP_SERVERS@", fallback)
            if "@EGW_" in content:
                raise SeedError(f"{rel} still holds an unsubstituted @EGW_...@ placeholder")
            files.append((guest_path, mode, content))
        now = dt.datetime.now(dt.timezone.utc)
        rendered_utc = now.strftime("%Y-%m-%dT%H:%M:%SZ")
        commit = repo_commit(args.repo)
        buildinfo = f"scenario={SCENARIO}\nseed_rendered_utc={rendered_utc}\nsource_repo_commit={commit}\n"
        user_data = render_user_data(args.hostname, pubkey, files, buildinfo, args.mask_timers, rendered_utc, commit)
        meta_data = f"instance-id: egw-{SCENARIO}-{now.strftime('%Y%m%dT%H%M%SZ')}\nlocal-hostname: {args.hostname}\n"
        vendor_data = "#cloud-config\n"
        args.out.mkdir(parents=True, exist_ok=True)
        written = []
        for name, text in (("user-data", user_data), ("meta-data", meta_data), ("vendor-data", vendor_data)):
            path = args.out / name
            path.write_bytes(text.encode("utf-8"))
            written.append(path)
    except SeedError as exc:
        print(f"STOP: {exc}", file=sys.stderr)
        return 2
    for path in written:
        print(path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
