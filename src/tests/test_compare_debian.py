"""Cases for the Debian 13 base-preparation helpers of the comparison tool
(tools/compare/debian): the cloud-init seed renderer, the first-boot verdict
read from the serial console log, and the boot-file extractor.

The two Python helpers run under this interpreter on any host. The extractor is
bash for the WSL2 host and is exercised there only, on a synthetic GPT image
(protective MBR, header at LBA 1 with both CRCs, entries at LBA 2) with
stand-ins for the three tools it cannot have here: qemu-img (copies the file),
debugfs (answers 'ls -p /boot', 'dump' and 'stats' from a listing the case
chooses and records what it was asked, with the size of the file it was given)
and blkid. dd, od, sha256sum and python3 are the real ones. Nothing here says
anything about a real image, a guest or cloud-init itself.
"""
from __future__ import annotations

import hashlib
import os
import re
import shutil
import struct
import subprocess
import sys
import uuid
import zlib
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
DEBIAN_DIR = REPO_ROOT / "tools" / "compare" / "debian"
RENDER_SEED = DEBIAN_DIR / "render_seed.py"
FIRSTBOOT_CHECK = DEBIAN_DIR / "firstboot_check.py"
EXTRACT_BOOT = DEBIAN_DIR / "extract_boot.sh"
GATEWAY_CONFIG = REPO_ROOT / "src" / "yocto" / "meta-egw" / "recipes-core" / "egw-gateway-config" / "files"
BASE_CONFIG = REPO_ROOT / "src" / "yocto" / "meta-egw" / "recipes-core" / "egw-base-config" / "files"

PUBKEY = "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIFakeKeyForTests0000000000000000000000000 egw@test"
HOSTNAME = "egw-qemu-debian13"
NTP_LINE = "NTP=0.pool.ntp.org 1.pool.ntp.org 2.pool.ntp.org 3.pool.ntp.org"
FALLBACK_LINE = "FallbackNTP=time.cloudflare.com"
FSTAB_LINE = "LABEL=egw-data  /var/lib/docker  ext4  defaults,nofail,x-systemd.growfs,x-systemd.device-timeout=30s  0  0"

# guest path -> repository file embedded byte for byte
VERBATIM = {
    "/etc/docker/daemon.json": GATEWAY_CONFIG / "daemon.json",
    "/etc/systemd/journald.conf.d/10-egw.conf": GATEWAY_CONFIG / "10-egw-journald.conf",
    "/etc/ssh/sshd_config.d/10-egw.conf": GATEWAY_CONFIG / "10-egw-sshd.conf",
    "/etc/sudoers.d/egw": GATEWAY_CONFIG / "egw-sudoers",
    "/etc/tmpfiles.d/egw.conf": GATEWAY_CONFIG / "egw.conf",
    "/etc/systemd/system/docker.service.d/10-egw-data-disk.conf": GATEWAY_CONFIG / "10-egw-data-disk.conf",
    "/etc/systemd/network/80-egw-wired.network": BASE_CONFIG / "80-egw-wired.network",
}
TIMESYNCD_GUEST = "/etc/systemd/timesyncd.conf.d/10-egw.conf"
TIMESYNCD_SRC = GATEWAY_CONFIG / "10-egw-timesyncd.conf"

bash_only = pytest.mark.skipif(
    sys.platform == "win32" or any(shutil.which(t) is None for t in ("bash", "dd", "od", "sha256sum")),
    reason="extract_boot.sh is bash for the WSL2 host (dd, od, sha256sum)",
)


def run_py(script: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, str(script), *args], capture_output=True, text=True,
                          encoding="utf-8", timeout=120)


# --------------------------------------------------------------------------
# render_seed.py
# --------------------------------------------------------------------------

@pytest.fixture
def pubkey_file(tmp_path: Path) -> Path:
    path = tmp_path / "egw_campaign.pub"
    path.write_bytes((PUBKEY + "\n").encode())
    return path


def render(tmp_path: Path, pubkey_file: Path, *extra: str) -> tuple[Path, subprocess.CompletedProcess]:
    out = tmp_path / "seed"
    done = run_py(RENDER_SEED, "--pubkey", str(pubkey_file), "--hostname", HOSTNAME,
                  "--repo", str(REPO_ROOT), "--out", str(out), *extra)
    return out, done


@pytest.fixture
def seed(tmp_path: Path, pubkey_file: Path) -> tuple[Path, subprocess.CompletedProcess]:
    out, done = render(tmp_path, pubkey_file)
    assert done.returncode == 0, done.stderr
    return out, done


def user_data_of(seed) -> str:
    return (seed[0] / "user-data").read_bytes().decode("utf-8")


def embedded_block(user_data: str, guest_path: str) -> str:
    """The literal block written for ``guest_path`` in write_files, de-indented.

    Reads the renderer's own layout (``  - path:`` entries, ``    content: |``, content at six
    columns) so that the check does not depend on a YAML library being installed.
    """
    lines = user_data.split("\n")
    i = lines.index(f"  - path: {guest_path}")
    while not lines[i].startswith("    content: |"):
        i += 1
    assert lines[i] == "    content: |", lines[i]
    i += 1
    body = []
    while i < len(lines) and (lines[i].startswith("      ") or lines[i] == ""):
        body.append(lines[i][6:])
        i += 1
    while body and body[-1] == "":
        body.pop()
    return "\n".join(body) + "\n"


def test_render_seed_writes_the_three_nocloud_files(seed):
    out, done = seed
    for name in ("user-data", "meta-data", "vendor-data"):
        assert (out / name).is_file(), name
        assert str(out / name) in done.stdout
    assert user_data_of(seed).split("\n", 1)[0] == "#cloud-config"
    assert (out / "vendor-data").read_bytes() == b"#cloud-config\n"
    assert b"\r" not in (out / "user-data").read_bytes()


def test_meta_data_names_the_instance_and_the_host(seed):
    meta = (seed[0] / "meta-data").read_text(encoding="utf-8")
    assert re.search(r"^instance-id: egw-debian13-\d{8}T\d{6}Z$", meta, re.M), meta
    assert f"local-hostname: {HOSTNAME}\n" in meta


def test_user_data_carries_identity_key_and_markers(seed):
    text = user_data_of(seed)
    assert f"\nhostname: {HOSTNAME}\n" in text
    assert f'      - "{PUBKEY}"\n' in text
    assert "ssh_pwauth: false" in text and "disable_root: true" in text
    assert "    sudo: \"ALL=(ALL:ALL) NOPASSWD: ALL\"" in text
    assert "    lock_passwd: true" in text and "    uid: 1000" in text and "    shell: /bin/sh" in text
    assert text.count("  - name: ") == 1, "exactly one user"
    assert NTP_LINE in text and FALLBACK_LINE in text
    assert FSTAB_LINE in text
    assert "mkdir -m 0710 -p /var/lib/docker" in text
    for pkg in ("docker.io", "docker-compose", "docker-cli", "containerd", "runc", "curl", "openssl",
                "ca-certificates", "e2fsprogs", "sudo"):
        assert f"\n  - {pkg}\n" in text, pkg
    assert "package_upgrade: false" in text
    assert "  mode: poweroff" in text and "  message: egw-firstboot-done" in text
    assert "@EGW_" not in text
    assert "PRIVATE" not in text


def test_runcmd_order_and_timers_flag(tmp_path, pubkey_file):
    plain = user_data_of(render(tmp_path / "a", pubkey_file))
    masked = user_data_of(render(tmp_path / "b", pubkey_file, "--mask-timers"))
    assert "apt-daily.timer" not in plain
    assert "['systemctl', 'mask', '--now', 'apt-daily.timer', 'apt-daily-upgrade.timer']" in masked
    runcmd = plain.split("\nruncmd:\n", 1)[1].split("\npower_state:\n", 1)[0].split("\n")
    assert runcmd[0] == "  - ['usermod', '-aG', 'docker', 'egw']"
    assert runcmd[1] == "  - ['systemctl', 'daemon-reload']"
    assert runcmd[2] == "  - ['systemd-tmpfiles', '--create', 'egw.conf']"
    assert "systemd-networkd" in runcmd[3] and "|| true" in runcmd[3]
    assert runcmd[4] == "  - ['systemctl', 'restart', 'docker']"
    assert "dpkg-query -W" in runcmd[5] and "/etc/egw-buildinfo.packages" in runcmd[5]
    assert runcmd[6] == "  - ['touch', '/etc/cloud/cloud-init.disabled']"
    assert runcmd[7] == "  - ['sync']"


@pytest.mark.parametrize("guest_path", sorted(VERBATIM))
def test_write_files_hold_the_repository_bytes_verbatim(seed, guest_path):
    expected = VERBATIM[guest_path].read_bytes().decode("utf-8")
    assert embedded_block(user_data_of(seed), guest_path) == expected


def test_timesyncd_placeholders_are_substituted_as_the_recipe_does(seed):
    expected = (TIMESYNCD_SRC.read_bytes().decode("utf-8")
                .replace("@EGW_NTP_SERVERS@", "0.pool.ntp.org 1.pool.ntp.org 2.pool.ntp.org 3.pool.ntp.org")
                .replace("@EGW_FALLBACK_NTP_SERVERS@", "time.cloudflare.com"))
    assert embedded_block(user_data_of(seed), TIMESYNCD_GUEST) == expected
    assert NTP_LINE + "\n" in expected


def test_buildinfo_records_scenario_time_and_commit(seed):
    block = embedded_block(user_data_of(seed), "/etc/egw-buildinfo")
    lines = block.split("\n")
    assert lines[0] == "scenario=debian13"
    assert re.fullmatch(r"seed_rendered_utc=\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ", lines[1]), lines[1]
    assert re.fullmatch(r"source_repo_commit=([0-9a-f]{40}|unknown)", lines[2]), lines[2]


def test_user_data_parses_as_yaml_with_the_expected_structure(seed):
    yaml = pytest.importorskip("yaml")
    data = yaml.safe_load(user_data_of(seed))
    assert data["hostname"] == HOSTNAME and data["manage_etc_hosts"] is True
    assert data["groups"] == ["egw"]
    (user,) = data["users"]
    assert user["name"] == "egw" and user["uid"] == 1000 and user["primary_group"] == "egw"
    assert user["ssh_authorized_keys"] == [PUBKEY]
    assert user["sudo"] == "ALL=(ALL:ALL) NOPASSWD: ALL"
    (boot,) = data["bootcmd"]
    assert boot[:5] == ["cloud-init-per", "once", "egw-data-disk", "sh", "-c"]
    assert FSTAB_LINE in boot[5] and boot[5].startswith("set -e\nmkdir -m 0710 -p /var/lib/docker\n")
    files = {f["path"]: f for f in data["write_files"]}
    for guest_path, src in VERBATIM.items():
        assert files[guest_path]["content"] == src.read_bytes().decode("utf-8"), guest_path
        assert files[guest_path]["owner"] == "root:root"
    assert files["/etc/sudoers.d/egw"]["permissions"] == "0440"
    assert files["/etc/docker/daemon.json"]["permissions"] == "0644"
    assert NTP_LINE + "\n" in files[TIMESYNCD_GUEST]["content"]
    assert data["runcmd"][0] == ["usermod", "-aG", "docker", "egw"]
    assert data["runcmd"][-1] == ["sync"]
    assert ["touch", "/etc/cloud/cloud-init.disabled"] in data["runcmd"]
    dpkg = [c for c in data["runcmd"] if c[0] == "sh" and "dpkg-query" in c[2]]
    assert dpkg and "${Version}\\n'" in dpkg[0][2]
    assert data["power_state"] == {"mode": "poweroff", "message": "egw-firstboot-done", "timeout": 60, "condition": True}


def test_render_seed_refuses_a_private_key(tmp_path):
    key = tmp_path / "egw_campaign"
    key.write_bytes(b"-----BEGIN OPENSSH PRIVATE KEY-----\nb3BlbnNzaC1rZXktdjEAAAAATESTONLY\n-----END OPENSSH PRIVATE KEY-----\n")
    out, done = render(tmp_path, key)
    assert done.returncode == 2, done.stdout + done.stderr
    assert "private-key material" in done.stderr
    assert "b3BlbnNzaC" not in done.stderr + done.stdout
    assert not out.exists()


@pytest.mark.parametrize("content", [b"", b"\n\n", b"not a key at all\n"])
def test_render_seed_refuses_an_empty_or_odd_key_file(tmp_path, content):
    key = tmp_path / "odd.pub"
    key.write_bytes(content)
    out, done = render(tmp_path, key)
    assert done.returncode == 2, done.stdout + done.stderr
    assert not out.exists()


def test_render_seed_refuses_a_bad_hostname(tmp_path, pubkey_file):
    done = run_py(RENDER_SEED, "--pubkey", str(pubkey_file), "--hostname", "Egw Host",
                  "--repo", str(REPO_ROOT), "--out", str(tmp_path / "seed"))
    assert done.returncode == 2 and "hostname" in done.stderr


def test_render_seed_refuses_a_repo_without_the_sources(tmp_path, pubkey_file):
    done = run_py(RENDER_SEED, "--pubkey", str(pubkey_file), "--hostname", HOSTNAME,
                  "--repo", str(tmp_path / "empty"), "--out", str(tmp_path / "seed"))
    assert done.returncode == 2 and "unreadable" in done.stderr
    assert not (tmp_path / "seed").exists()


# --------------------------------------------------------------------------
# firstboot_check.py
# --------------------------------------------------------------------------

BOOT_HEAD = """[    0.000000] Booting Linux on physical CPU 0x0000000000 [0x414fd0c1]
[    0.000000] Linux version 6.12.113+deb13-cloud-arm64 (debian-kernel@lists.debian.org)
[    2.345678] cloud-init[412]: Cloud-init v. 25.1.4 running 'init-local' at Sun, 18 Oct 2026 12:30:01 +0000. Up 2.21 seconds.
ci-info: ++++++Authorized keys from /home/egw/.ssh/authorized_keys for user egw+++++++
-----BEGIN SSH HOST KEY FINGERPRINTS-----
256 SHA256:9mZz2u3tQmVv1aFakeFingerprint root@egw-qemu-debian13 (ED25519)
-----END SSH HOST KEY FINGERPRINTS-----
-----BEGIN SSH HOST KEY KEYS-----
ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIHostKeyPublicPartOnly root@egw-qemu-debian13
-----END SSH HOST KEY KEYS-----
"""
FINISHED = ("Cloud-init v. 25.1.4 finished at Sun, 18 Oct 2026 12:36:48 +0000. Datasource DataSourceNoCloudNet "
            "[seed=http://10.0.2.2:8099/][dsmode=net].  Up 412.31 seconds\n")
POWERDOWN = "[  415.123456] reboot: Power down\n"


def check(tmp_path: Path, text: str) -> subprocess.CompletedProcess:
    log = tmp_path / "console.log"
    log.write_bytes(text.encode("utf-8"))
    return run_py(FIRSTBOOT_CHECK, str(log))


def test_firstboot_ok_needs_both_markers_and_tolerates_the_public_host_key_blocks(tmp_path):
    done = check(tmp_path, BOOT_HEAD + FINISHED + POWERDOWN)
    assert done.returncode == 0, done.stdout + done.stderr
    assert done.stdout.startswith("FIRSTBOOT: ok finished=11 powerdown=12\n")
    assert "FIRSTBOOT-INFO: Cloud-init v. 25.1.4 finished at" in done.stdout
    assert "KEY-ERROR" not in done.stdout and "FIRSTBOOT-WARN" not in done.stdout


def test_firstboot_missing_power_down(tmp_path):
    done = check(tmp_path, BOOT_HEAD + FINISHED)
    assert done.returncode == 1
    assert done.stdout.strip() == "FIRSTBOOT: missing powerdown (no 'reboot: Power down')"


def test_firstboot_missing_finished(tmp_path):
    done = check(tmp_path, BOOT_HEAD + POWERDOWN)
    assert done.returncode == 1
    assert done.stdout.strip() == "FIRSTBOOT: missing finished (no cloud-init completion line)"


def test_firstboot_missing_both_names_both(tmp_path):
    done = check(tmp_path, BOOT_HEAD)
    assert done.returncode == 1
    assert "missing finished" in done.stdout and "powerdown" in done.stdout


def test_firstboot_power_down_before_finished_is_not_complete(tmp_path):
    done = check(tmp_path, BOOT_HEAD + POWERDOWN + FINISHED)
    assert done.returncode == 1
    assert "precedes finished" in done.stdout


def test_firstboot_warnings_are_reported_not_fatal(tmp_path):
    noise = ("[FAILED] Failed to start apt-daily.service - Daily apt download activities.\n"
             "E: Unable to locate package nonesuch\n"
             "[  301.2] cloud-init[812]: 2026-10-18 12:35:00,000 - cc_package_update_upgrade_install.py[WARNING]: 1 failed\n"
             "dpkg: error processing package nonesuch (--configure):\n"
             "Traceback (most recent call last):\n")
    done = check(tmp_path, BOOT_HEAD + noise + FINISHED + POWERDOWN)
    assert done.returncode == 0, done.stdout
    warns = [ln for ln in done.stdout.splitlines() if ln.startswith("FIRSTBOOT-WARN: ")]
    assert len(warns) == 5, done.stdout
    assert warns[0].endswith("Failed to start apt-daily.service - Daily apt download activities.")
    assert done.stdout.splitlines()[-2].startswith("FIRSTBOOT: ok ")


@pytest.mark.parametrize("leak", [
    "-----BEGIN OPENSSH PRIVATE KEY-----\n",
    "-----BEGIN RSA PRIVATE KEY-----\n",
    "-----BEGIN CERTIFICATE-----\n",
    "some tool printed PRIVATE KEY material here\n",
])
def test_firstboot_key_material_in_the_log_is_fatal_and_not_echoed(tmp_path, leak):
    done = check(tmp_path, BOOT_HEAD + leak + "b3BlbnNzaC1rZXktdjEAAAAASECRET\n" + FINISHED + POWERDOWN)
    assert done.returncode == 3, done.stdout
    assert done.stdout.startswith("KEY-ERROR: line 11 ")
    assert "SECRET" not in done.stdout and "BEGIN" not in done.stdout
    assert "FIRSTBOOT: ok" not in done.stdout


def test_firstboot_missing_log_is_exit_2(tmp_path):
    done = run_py(FIRSTBOOT_CHECK, str(tmp_path / "absent.log"))
    assert done.returncode == 2 and "unreadable" in done.stderr
    assert run_py(FIRSTBOOT_CHECK).returncode == 2


# --------------------------------------------------------------------------
# extract_boot.sh (bash host only)
# --------------------------------------------------------------------------

LINUX_FS = uuid.UUID("0FC63DAF-8483-4772-8E79-3D69D16ADBBF")
EFI_SYSTEM = uuid.UUID("C12A7328-F81F-11D2-BA4B-00A0C93EC93B")
KVER = "6.12.113+deb13-cloud-arm64"
ROOT_UUID = "8d2a7e3c-4b1f-4e6a-9c0d-1f2e3d4c5b6a"
SECTOR = 512

QEMU_IMG_STUB = r"""#!/bin/sh
# stub qemu-img: 'convert [-O fmt] IN OUT' copies IN to OUT; anything else is refused.
[ "$1" = convert ] || { echo "stub qemu-img: unsupported: $*" >&2; exit 1; }
eval "src=\${$(($# - 1))}"
eval "dst=\${$#}"
cp "$src" "$dst"
"""

DEBUGFS_STUB = r"""#!/bin/sh
# stub debugfs: '-R REQUEST FS'. Lists /boot from $EGW_STUB_BOOT_LS, dumps a few bytes whose
# magic depends on the name, answers stats with a UUID; records request and FS size.
[ "$1" = -R ] || { echo "stub debugfs: unsupported: $*" >&2; exit 1; }
req=$2
fs=$3
echo "debugfs 1.47.2 (stub)" >&2
if [ -n "${EGW_STUB_LOG:-}" ]; then printf '%s|%s\n' "$req" "$(wc -c < "$fs" | tr -d ' ')" >> "$EGW_STUB_LOG"; fi
case $req in
    "ls -p /boot") cat "$EGW_STUB_BOOT_LS" ;;
    "dump /boot/"*)
        [ "${EGW_STUB_DUMP_FAIL:-0}" = 1 ] && exit 0
        dst=${req##* }
        case $req in
            *vmlinuz*) printf '\037\213\010\000stub-kernel-payload' > "$dst" ;;
            *) printf '\050\265\057\375stub-initrd-payload' > "$dst" ;;
        esac ;;
    stats) printf 'Filesystem volume name:   <none>\nFilesystem UUID:          %s\nFilesystem magic number:  0xEF53\n' "$EGW_STUB_FS_UUID" ;;
    *) echo "stub debugfs: unknown request $req" >&2 ;;
esac
exit 0
"""

BLKID_STUB = r"""#!/bin/sh
# stub blkid: prints $EGW_STUB_BLKID_UUID, or nothing (exit 2) when unset, like blkid on a file it cannot probe.
[ -n "${EGW_STUB_BLKID_UUID:-}" ] || exit 2
printf '%s\n' "$EGW_STUB_BLKID_UUID"
"""


def boot_listing(kernels: list[str], initrds: list[str]) -> str:
    rows = ["/2/040755/0/0/.//", "/2/040755/0/0/..//", "/12/040755/0/0/grub//",
            f"/13/0100644/0/0/config-{KVER}/270011/", f"/14/0100644/0/0/System.map-{KVER}/4194999/"]
    rows += [f"/{20 + i}/0100644/0/0/{n}/{40000000 + i}/" for i, n in enumerate(kernels)]
    rows += [f"/{30 + i}/0100644/0/0/{n}/{60000000 + i}/" for i, n in enumerate(initrds)]
    return "\n".join(rows) + "\n"


def gpt_image(path: Path, parts: list[tuple[uuid.UUID, int, int, str]], total_sectors: int = 16384,
              break_header_crc: bool = False) -> None:
    """A GPT disk image: protective MBR, header at LBA 1, 128 entries at LBA 2, sparse body."""
    entries = bytearray(128 * 128)
    for i, (type_guid, first, last, name) in enumerate(parts):
        off = i * 128
        entries[off:off + 16] = type_guid.bytes_le
        entries[off + 16:off + 32] = uuid.UUID(int=0x1000 + i).bytes_le
        struct.pack_into("<QQQ", entries, off + 32, first, last, 0)
        encoded = name.encode("utf-16-le")
        entries[off + 56:off + 56 + len(encoded)] = encoded
    header = bytearray(92)
    struct.pack_into("<8sIIIIQQQQ16sQIII", header, 0, b"EFI PART", 0x00010000, 92, 0, 0, 1, total_sectors - 1,
                     34, total_sectors - 34, uuid.UUID(int=0xABC).bytes_le, 2, 128, 128, zlib.crc32(bytes(entries)))
    struct.pack_into("<I", header, 16, zlib.crc32(bytes(header)) ^ (1 if break_header_crc else 0))
    mbr = bytearray(512)
    mbr[450] = 0xEE
    struct.pack_into("<II", mbr, 454, 1, total_sectors - 1)
    mbr[510:512] = b"\x55\xaa"
    with open(path, "wb") as fh:
        fh.write(mbr)
        fh.write(header + bytes(SECTOR - len(header)))
        fh.write(entries)
        for _type_guid, first, _last, name in parts:
            fh.seek(first * SECTOR)
            fh.write(b"PART:" + name.encode())
        fh.truncate(total_sectors * SECTOR)


class ExtractBench:
    def __init__(self, tmp_path: Path):
        self.root = tmp_path
        self.bin = tmp_path / "bin"
        self.bin.mkdir()
        self.log = tmp_path / "stub.log"
        self.listing = tmp_path / "boot.ls"
        for name, text in (("qemu-img", QEMU_IMG_STUB), ("debugfs", DEBUGFS_STUB), ("blkid", BLKID_STUB),
                           ("python3", f'#!/bin/sh\nexec "{Path(sys.executable).as_posix()}" "$@"\n')):
            path = self.bin / name
            path.write_text(text, encoding="utf-8", newline="\n")
            path.chmod(0o755)
        self.listing.write_text(boot_listing([f"vmlinuz-{KVER}"], [f"initrd.img-{KVER}"]), encoding="utf-8", newline="\n")
        self.image = tmp_path / "debian.qcow2"
        # Debian-like: a root (the largest Linux partition), a smaller Linux partition, the ESP.
        self.parts = [(LINUX_FS, 4096, 16000, "root"), (LINUX_FS, 2048, 4095, "spare"),
                      (EFI_SYSTEM, 256, 2047, "EFI System Partition")]
        gpt_image(self.image, self.parts)
        self.out = tmp_path / "boot"

    def env(self, **extra: str) -> dict[str, str]:
        env = {k: v for k, v in os.environ.items() if not k.startswith("EGW_")}
        env["PATH"] = f"{self.bin}{os.pathsep}{env.get('PATH', '')}"
        env.update(EGW_STUB_LOG=str(self.log), EGW_STUB_BOOT_LS=str(self.listing),
                   EGW_STUB_BLKID_UUID=ROOT_UUID, EGW_STUB_FS_UUID=ROOT_UUID)
        env.update(extra)
        return env

    def run(self, *args: str, **extra: str) -> subprocess.CompletedProcess:
        argv = args if args else (str(self.image), str(self.out))
        return subprocess.run(["bash", str(EXTRACT_BOOT), *argv], capture_output=True, text=True,
                              timeout=120, env=self.env(**extra))


@pytest.fixture
def bench(tmp_path: Path) -> ExtractBench:
    return ExtractBench(tmp_path)


@bash_only
def test_extract_boot_usage_and_missing_tools_are_exit_2(bench):
    assert bench.run("only-one").returncode == 2
    assert bench.run(str(bench.root / "absent.qcow2"), str(bench.out)).returncode == 2
    spaced = bench.root / "out dir"
    done = bench.run(str(bench.image), str(spaced))
    assert done.returncode == 2 and "white space" in done.stderr
    done = bench.run(EGW_COMPARE_QEMU_IMG=str(bench.root / "nonexistent-qemu-img"))
    assert done.returncode == 2 and "tool missing" in done.stderr
    assert not bench.out.exists()


@bash_only
def test_extract_boot_takes_kernel_initrd_and_uuid_from_the_largest_linux_partition(bench):
    done = bench.run()
    assert done.returncode == 0, done.stdout + done.stderr
    assert f"kernel=vmlinuz-{KVER} initrd=initrd.img-{KVER} root_uuid={ROOT_UUID} root_partition=1" in done.stdout
    out = bench.out
    for name in ("vmlinuz", "initrd.img", "root-uuid.txt", "partitions.txt", "boot-files.sha256"):
        assert (out / name).is_file(), name
    assert not (out / "base.raw").exists() and not (out / "root.part").exists()
    assert (out / "root-uuid.txt").read_text() == ROOT_UUID + "\n"
    assert (out / "vmlinuz").read_bytes().startswith(b"\x1f\x8b\x08\x00")
    table = (out / "partitions.txt").read_text()
    assert "header crc ok" in table and "crc ok), protective MBR yes" in table
    assert re.search(r"^1  0FC63DAF-8483-4772-8E79-3D69D16ADBBF  \(Linux filesystem\)  4096  16000  6095360  'root'$", table, re.M), table
    assert re.search(r"^3  C12A7328-F81F-11D2-BA4B-00A0C93EC93B  \(EFI System\)  256  2047", table, re.M), table
    assert "root: index=1 first_lba=4096 start_bytes=2097152 size_bytes=6095360 name='root'" in table
    assert f"kernel=vmlinuz-{KVER} bytes=23 magic=1f8b0800 kind=gzip-compressed Image" in table
    assert f"initrd=initrd.img-{KVER} bytes=23 magic=28b52ffd kind=zstd" in table
    assert f"root_uuid={ROOT_UUID}" in table
    # 'HASH  NAME' (GNU on Linux; a binary-mode '*NAME' marker appears only on other hosts)
    sums = {name.lstrip("*"): digest for digest, name in
            (line.split() for line in (out / "boot-files.sha256").read_text().splitlines())}
    assert sums == {"vmlinuz": hashlib.sha256((out / "vmlinuz").read_bytes()).hexdigest(),
                    "initrd.img": hashlib.sha256((out / "initrd.img").read_bytes()).hexdigest()}
    # debugfs saw the root partition alone (its size) and was asked for the right files
    calls = bench.log.read_text().splitlines()
    assert all(call.endswith("|6095360") for call in calls), calls
    assert calls[0].startswith("ls -p /boot|")
    dumps = [call.split("|")[0] for call in calls if call.startswith("dump ")]
    assert len(dumps) == 2, calls
    assert dumps[0].startswith(f"dump /boot/vmlinuz-{KVER} ") and dumps[0].endswith("/vmlinuz"), dumps
    assert dumps[1].startswith(f"dump /boot/initrd.img-{KVER} ") and dumps[1].endswith("/initrd.img"), dumps


@bash_only
def test_extract_boot_falls_back_to_debugfs_for_the_uuid(bench):
    done = bench.run(EGW_STUB_BLKID_UUID="")
    assert done.returncode == 0, done.stdout + done.stderr
    assert (bench.out / "root-uuid.txt").read_text() == ROOT_UUID + "\n"
    assert any(call.startswith("stats|") for call in bench.log.read_text().splitlines())


@bash_only
@pytest.mark.parametrize("kernels, initrds, words", [
    ([], [], "found 0"),
    ([f"vmlinuz-{KVER}", "vmlinuz-6.12.99+deb13-cloud-arm64"], [f"initrd.img-{KVER}"], "found 2"),
    ([f"vmlinuz-{KVER}"], [], "is not next to"),
])
def test_extract_boot_refuses_other_than_one_kernel_with_its_initrd(bench, kernels, initrds, words):
    bench.listing.write_text(boot_listing(kernels, initrds), encoding="utf-8", newline="\n")
    done = bench.run()
    assert done.returncode == 3, done.stdout + done.stderr
    assert words in done.stderr
    assert not (bench.out / "vmlinuz").exists()
    assert not (bench.out / "base.raw").exists() and not (bench.out / "root.part").exists()


@bash_only
def test_extract_boot_refuses_an_image_without_a_linux_partition(bench):
    gpt_image(bench.image, [(EFI_SYSTEM, 256, 2047, "EFI System Partition")])
    done = bench.run()
    assert done.returncode == 3 and "no Linux filesystem partition" in done.stderr
    assert not bench.log.exists(), "debugfs must not have been reached"


@bash_only
def test_extract_boot_refuses_a_gpt_whose_header_crc_is_wrong(bench):
    gpt_image(bench.image, bench.parts, break_header_crc=True)
    done = bench.run()
    assert done.returncode == 3 and "CRC32 mismatch" in done.stderr


@bash_only
def test_extract_boot_refuses_a_non_gpt_file(bench):
    bench.image.write_bytes(b"\0" * 65536)
    done = bench.run()
    assert done.returncode == 3 and "no GPT header" in done.stderr


@bash_only
def test_extract_boot_reports_a_failed_dump_as_exit_4_and_cleans_up(bench):
    done = bench.run(EGW_STUB_DUMP_FAIL="1")
    assert done.returncode == 4, done.stdout + done.stderr
    assert "could not dump /boot/vmlinuz" in done.stderr
    assert not (bench.out / "base.raw").exists() and not (bench.out / "root.part").exists()
    assert not (bench.out / "boot-files.sha256").exists()
