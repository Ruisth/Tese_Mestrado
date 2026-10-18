"""tools/compare/provision_stack.sh and functional_check.sh on a bench of stubs.

The guest is this machine: a stub ssh runs every guest command under sh with the guest stubs (docker, stat) first on
PATH and /opt/egw moved under a fake root, so the marker files, the tar stream, the generated files and the copied
tree are real; a stub scp copies to and from that root; stub curl, ss and a stub venv python answer the host side.
The deployment tree comes from a fake repository whose scripts only log their names. Every stub appends its argv to
one call log, which is what the cases read: the order of the steps, the refusals before any guest contact, and the
absence of every password from every argv and every file the scripts write. Nothing here says anything about a
real guest, a real engine or the real simulator.
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

if sys.platform == "win32":
    pytest.skip("the comparison scripts are bash for the WSL2 host", allow_module_level=True)
if shutil.which("bash") is None:
    pytest.skip("bash is not installed", allow_module_level=True)

REPO_ROOT = Path(__file__).resolve().parents[2]
COMPARE = REPO_ROOT / "tools" / "compare"
PROVISION = COMPARE / "provision_stack.sh"
FUNCTIONAL = COMPARE / "functional_check.sh"
LOCK_FILE = REPO_ROOT / "src" / "deployment" / "images.lock.env"

PASSWORDS = {
    "MOSQUITTO_SIMULATOR_PASSWORD": "stub-simulator-secret-0123456789",
    "MOSQUITTO_CONTROLLER_PASSWORD": "stub-controller-secret-0123456789",
    "EGW_MQTT_PASSWORD": "stub-controller-secret-0123456789",
    "DITTO_DEVOPS_PASSWORD": "stub-devops-secret-0123456789",
}
GOOD_FACTS = (
    "FACT uid=1000\nFACT docker=/usr/bin/docker\nFACT compose=2.26.0\nFACT label=egw-data\n"
    "uid=1000(egw) gid=1000(egw) groups=1000(egw),986(docker)\n/usr/bin/docker\n"
    "Docker version 25.0.9, build stub\nDocker Compose version v2.26.0\n/dev/vdb ext4 32G\n"
)
NO_DATA_DISK_FACTS = GOOD_FACTS.replace("FACT label=egw-data", "FACT label=").replace("/dev/vdb ext4 32G", "/dev/vda ext4 8G")

SSH_STUB = """#!/bin/sh
# Stub ssh: options are skipped; no command = the tunnel (-N) or a control request (-O) answered from a marker;
# a command runs here under sh, guest stubs first on PATH, /opt/egw moved under the fake guest root.
echo "ssh $*" >> "$EGW_STUB_CALLS"
ctl=
while [ $# -gt 0 ]; do
    case $1 in
        -O) ctl=$2; shift 2 ;;
        -i|-p|-o|-S|-L|-F|-l|-J|-E|-R|-D|-W|-b|-c|-e|-I|-m|-Q|-w) shift 2 ;;
        -*) shift ;;
        *) break ;;
    esac
done
case $ctl in
    check) [ -e "$EGW_STUB_STATE/tunnel" ] && exit 0; exit 255 ;;
    exit) rm -f "$EGW_STUB_STATE/tunnel"; exit 0 ;;
esac
[ $# -ge 1 ] || { echo "stub ssh: no host" >&2; exit 255; }
shift
if [ $# -eq 0 ]; then touch "$EGW_STUB_STATE/tunnel"; exit "${EGW_STUB_TUNNEL_RC:-0}"; fi
[ -z "${EGW_STUB_SSH_RC:-}" ] || exit "$EGW_STUB_SSH_RC"
cmd=$*
case $cmd in
    *findmnt*) [ -z "${EGW_STUB_FACTS:-}" ] || { printf '%s\\n' "$EGW_STUB_FACTS"; exit 0; } ;;
esac
cmd=$(printf '%s\\n' "$cmd" | sed "s#/opt/egw#$EGW_STUB_GUEST_ROOT/opt/egw#g")
PATH=$EGW_STUB_GUEST_BIN:$PATH
export PATH
exec sh -c "$cmd"
"""

SCP_STUB = """#!/bin/sh
# Stub scp: copies between this machine and the fake guest root (egw@127.0.0.1:/path).
echo "scp $*" >> "$EGW_STUB_CALLS"
while [ $# -gt 0 ]; do case $1 in -i|-P|-o|-F|-J|-l|-c|-S) shift 2 ;; -*) shift ;; *) break ;; esac; done
[ $# -ge 2 ] || exit 1
for a; do dest=$a; done
case $dest in
    egw@127.0.0.1:*)
        target=$EGW_STUB_GUEST_ROOT${dest#egw@127.0.0.1:}
        case $target in */) mkdir -p "$target" ;; *) mkdir -p "$(dirname "$target")" ;; esac
        while [ $# -gt 1 ]; do cp -r "$1" "$target" || exit 1; shift; done ;;
    *)
        case $1 in egw@127.0.0.1:*) cp "$EGW_STUB_GUEST_ROOT${1#egw@127.0.0.1:}" "$dest" ;; *) exit 1 ;; esac ;;
esac
"""

CURL_STUB = """#!/bin/sh
# Stub curl (host through the tunnel, and the guest's own /ready): /metrics counts one accepted event once the
# stub simulator ran; the twin carries EGW_STUB_TWIN_RUN_ID, else the run id the stub simulator was given.
echo "curl $*" >> "$EGW_STUB_CALLS"
url=; w=0
for a; do case $a in http://*) url=$a ;; -w) w=1 ;; esac; done
st=$EGW_STUB_STATE
case $url in
    */ready) if [ $w = 1 ]; then printf '%s' "${EGW_STUB_READY:-200}"; else echo '{"status":"ok"}'; fi ;;
    */metrics) n=0; [ ! -e "$st/sim-ran" ] || n=1
        printf '{"accepted": %s, "rejected": 0, "duplicate": 0, "failed": 0, "dropped": 0, "queue_depth": 0, "started_at": "2026-10-18T00:00:00.000Z"}\\n' "$n" ;;
    */api/2/things/org.c2dta:*) uuid=${url##*org.c2dta:}; run=${EGW_STUB_TWIN_RUN_ID:-$(cat "$st/last-run-id" 2>/dev/null)}
        printf '{"thingId": "org.c2dta:%s", "attributes": {"device_type": "smartwatch", "egw_id": "egw-01"}, "features": {"vitals": {"properties": {"heart_rate_bpm": 70}}, "ingestion": {"properties": {"last_run_id": "%s", "last_seq": 0, "accepted_count": 1}}}}\\n' "$uuid" "$run" ;;
    *) echo "stub curl: $url" >&2; exit 22 ;;
esac
"""

SS_STUB = """#!/bin/sh
echo "ss $*" >> "$EGW_STUB_CALLS"
echo 'State  Recv-Q Send-Q Local Address:Port Peer Address:Port'
for p in ${EGW_STUB_BUSY_PORTS:-}; do echo "LISTEN 0 128 127.0.0.1:$p 0.0.0.0:*"; done
"""

DOCKER_STUB = """#!/bin/sh
# Stub docker of the guest: image state lives in marker files (pulled, controller-loaded).
echo "docker $*" >> "$EGW_STUB_CALLS"
st=$EGW_STUB_STATE
for a; do last=$a; done
case "$*" in
    --version) echo "Docker version 25.0.9, build stub" ;;
    "compose version --short") echo 2.26.0 ;;
    "compose version"*) echo "Docker Compose version v2.26.0" ;;
    "compose "*" pull "*) touch "$st/pulled"; echo "stub: pulled"; exit "${EGW_STUB_PULL_RC:-0}" ;;
    "compose "*" up -d") echo "stub: up"; exit "${EGW_STUB_UP_RC:-0}" ;;
    "compose "*" config -q") ;;
    "image inspect "*"egw-controller:0.1.0"*)
        [ -e "$st/controller-loaded" ] || { echo "Error: No such image: egw-controller:0.1.0" >&2; exit 1; }
        echo sha256:stub ;;
    "image inspect --format "*"@sha256:"*)
        [ -e "$st/pulled" ] || exit 1
        printf '[%s@%s] arm64/linux\\n' "${last%%@*}" "${last##*@}" ;;
    load) cat > /dev/null; touch "$st/controller-loaded"; echo "Loaded image: egw-controller:0.1.0" ;;
    "inspect --format "*) shift 3; for n; do echo "/$n running/${EGW_STUB_HEALTH:-healthy}"; done ;;
    *) echo "stub docker: unsupported: $*" >&2; exit 1 ;;
esac
"""

STAT_STUB = """#!/bin/sh
echo "stat $*" >> "$EGW_STUB_CALLS"
echo 1000:1000
"""

PYTHON_STUB = """#!/bin/sh
# Stub venv python: `-c import egw_simulator` answers 0; `-m egw_simulator run` writes one sent event and refuses a
# password on its argv or a missing EGW_MQTT_PASSWORD, as the check of 'no secret on a command line' needs.
echo "python $*" >> "$EGW_STUB_CALLS"
case " $* " in *" import egw_simulator"*) exit 0 ;; esac
[ "$1" = -m ] && [ "$2" = egw_simulator ] && [ "$3" = run ] || { echo "stub python: unsupported $*" >&2; exit 9; }
shift 3
out=; run=
while [ $# -gt 0 ]; do
    case $1 in
        --output) out=$2; shift 2 ;;
        --run-id) run=$2; shift 2 ;;
        --password) echo "stub python: a password on the command line" >&2; exit 8 ;;
        --*) shift 2 ;;
        *) shift ;;
    esac
done
[ -n "${EGW_MQTT_PASSWORD:-}" ] || { echo "stub python: EGW_MQTT_PASSWORD is not set" >&2; exit 7; }
[ "${EGW_STUB_SIM_RC:-0}" = 0 ] || exit "$EGW_STUB_SIM_RC"
mkdir -p "$out/$run" || exit 6
printf '{"message_id": "%s", "device_uuid": "%s", "run_id": "%s", "seq": 0}\\n' "$EGW_STUB_MESSAGE_ID" "$EGW_STUB_DEVICE_UUID" "$run" > "$out/$run/sent_events.jsonl"
printf '%s' "$run" > "$EGW_STUB_STATE/last-run-id"
touch "$EGW_STUB_STATE/sim-ran"
echo "egw_simulator: done sent=1 intended_invalid=0" >&2
"""

# The deployment scripts of the fake repository: each logs its name; auth needs the password in ITS environment
# (sourced from .env on the guest), tls writes the CA the host fetches, verify prints the line the host looks for.
DEPLOY_SCRIPTS = {
    "generate-dev-tls.sh": 'd=$(dirname "$0")/../mosquitto/config/certs; mkdir -p "$d" && echo "stub ca" > "$d/ca.crt"\n',
    "generate-dev-auth.sh": '[ -n "${MOSQUITTO_SIMULATOR_PASSWORD:-}" ] && [ -n "${MOSQUITTO_CONTROLLER_PASSWORD:-}" ] '
                            '|| { echo "ERROR: simulator password missing." >&2; exit 2; }\n'
                            'echo "hash" > "$(dirname "$0")/../mosquitto/config/passwd"\n',
    "prepare-broker-secrets.sh": 'echo "OK: broker secrets ($*)"\n',
    "verify-controller-image.sh": 'echo "CONTROLLER IMAGE IDENTITY: verified (egw-controller:0.1.0 = sha256:stub)"\n',
    "validate-config.sh": 'echo "OK: validate-config"\n',
}
DEVICE_UUID = "4b2c0c1e-6f1a-4d6b-9c7e-2f3a1b5d8e90"
MESSAGE_ID = "9f3d2c1b-0a4e-4f5b-8c6d-7e8f9a0b1c2d"


def _write(path: Path, text: str, executable: bool = False) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    if executable:
        path.chmod(0o755)


class Bench:
    def __init__(self, tmp_path: Path) -> None:
        self.tmp = tmp_path
        self.home = tmp_path / "home"
        self.bin = tmp_path / "bin"
        self.guest_bin = tmp_path / "gbin"
        self.guest_root = tmp_path / "guest"
        self.state = tmp_path / "stub-state"
        self.calls = tmp_path / "calls.log"
        self.repo = tmp_path / "repo"
        self.compare_root = tmp_path / "egw-compare"
        self.venv = tmp_path / "venv"
        self.secrets = self.home / "egw-tcg" / ".env"
        self.images = self.home / "egw-images"
        self.s_dir = self.compare_root / "scenarios" / "yocto"
        for d in (self.home, self.bin, self.guest_bin, self.guest_root, self.state, self.compare_root):
            d.mkdir(parents=True)
        for name, text in (("ssh", SSH_STUB), ("scp", SCP_STUB), ("curl", CURL_STUB), ("ss", SS_STUB)):
            _write(self.bin / name, text, executable=True)
        for name, text in (("docker", DOCKER_STUB), ("stat", STAT_STUB)):
            _write(self.guest_bin / name, text, executable=True)
        _write(self.venv / "bin" / "python", PYTHON_STUB, executable=True)
        _write(self.secrets, "".join(f"{k}={v}\n" for k, v in PASSWORDS.items()) + "EGW_HOST=\n")
        archive = b"stub controller archive\n"
        (self.images).mkdir()
        (self.images / "egw-controller-0.1.0-arm64.tar").write_bytes(archive)
        _write(self.images / "egw-controller-0.1.0-arm64.identity.txt",
               "image_ref=egw-controller:0.1.0\nimage_id=sha256:stub\nimage_architecture=arm64\nimage_os=linux\n"
               "image_revision_label=deadbeef\nsource_tree_state=clean\narchive_file=egw-controller-0.1.0-arm64.tar\n"
               f"archive_sha256={hashlib.sha256(archive).hexdigest()}\n")
        deploy = self.repo / "src" / "deployment"
        _write(deploy / "compose.yaml", "name: egw\nservices: {}\n")
        shutil.copy(LOCK_FILE, deploy / "images.lock.env")
        _write(deploy / "mosquitto" / "config" / "acl", "topic read $SYS/#\n")
        _write(deploy / "mosquitto" / "config" / "mosquitto.conf", "listener 8883\n")
        for name, body in DEPLOY_SCRIPTS.items():
            _write(deploy / "scripts" / name, f'#!/bin/sh\necho "script {name} $*" >> "$EGW_STUB_CALLS"\n{body}', executable=True)
        _write(tmp_path / "ssh-key", "stub private key\n")

    def env(self, **extra: str) -> dict[str, str]:
        environment = dict(os.environ)
        environment.update({
            "HOME": self.home.as_posix(),
            "PATH": f"{self.bin.as_posix()}{os.pathsep}{os.environ['PATH']}",
            "EGW_COMPARE_ROOT": self.compare_root.as_posix(),
            "EGW_COMPARE_REPO": self.repo.as_posix(),
            "EGW_COMPARE_SSH_KEY": (self.tmp / "ssh-key").as_posix(),
            "EGW_COMPARE_SECRETS_ENV": self.secrets.as_posix(),
            "EGW_IMAGES_DIR": self.images.as_posix(),
            "EGW_EXEC_VENV": self.venv.as_posix(),
            "EGW_COMPARE_HEALTH_STEP_S": "0",
            "EGW_COMPARE_ACCEPT_STEP_S": "0",
            "EGW_STUB_CALLS": self.calls.as_posix(),
            "EGW_STUB_GUEST_BIN": self.guest_bin.as_posix(),
            "EGW_STUB_GUEST_ROOT": self.guest_root.as_posix(),
            "EGW_STUB_STATE": self.state.as_posix(),
            "EGW_STUB_FACTS": GOOD_FACTS,
            "EGW_STUB_DEVICE_UUID": DEVICE_UUID,
            "EGW_STUB_MESSAGE_ID": MESSAGE_ID,
        })
        environment.update(extra)
        return environment

    def provision(self, **extra: str) -> subprocess.CompletedProcess:
        return subprocess.run(["bash", str(PROVISION), "yocto"], env=self.env(**extra), stdin=subprocess.DEVNULL,
                              capture_output=True, text=True, timeout=120)

    def functional(self, run_id: str = "fc-01", seed: str = "42", **extra: str) -> subprocess.CompletedProcess:
        (self.s_dir / "state").mkdir(parents=True, exist_ok=True)
        (self.s_dir / "state" / "ca.crt").write_text("stub ca\n", encoding="utf-8")
        return subprocess.run(["bash", str(FUNCTIONAL), "yocto", run_id, seed], env=self.env(**extra),
                              stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=120)

    def log(self) -> str:
        return self.calls.read_text(encoding="utf-8") if self.calls.exists() else ""

    def reset_log(self) -> None:
        self.calls.unlink(missing_ok=True)

    def record(self) -> dict:
        return json.loads((self.s_dir / "state" / "provision.json").read_text(encoding="utf-8"))

    def written_text(self) -> str:
        """Every file the scripts wrote under the compare root, concatenated (the secrets must be in none)."""
        return "".join(p.read_text(encoding="utf-8", errors="replace") for p in self.compare_root.rglob("*") if p.is_file())


@pytest.fixture
def bench(tmp_path) -> Bench:
    return Bench(tmp_path)


def _report(result: subprocess.CompletedProcess) -> str:
    return f"exit {result.returncode}\nstdout:\n{result.stdout}\nstderr:\n{result.stderr}"


def _assert_no_secret(bench: Bench) -> None:
    text = bench.log() + bench.written_text()
    for value in PASSWORDS.values():
        assert value not in text, f"the password value {value!r} reached an argv or a written file"


def test_provision_refuses_a_missing_secrets_file_before_any_guest_contact(bench) -> None:
    bench.secrets.unlink()
    result = bench.provision()
    assert result.returncode == 2, _report(result)
    assert "STOP: secrets file missing" in result.stdout
    assert result.stdout.rstrip().splitlines()[-1].startswith("PROVISION yocto: result=prerequisites log=")
    assert bench.log() == ""


def test_provision_refuses_a_change_me_placeholder(bench) -> None:
    bench.secrets.write_text("MOSQUITTO_SIMULATOR_PASSWORD=CHANGE_ME_simulator_password\n"
                             "MOSQUITTO_CONTROLLER_PASSWORD=x\nEGW_MQTT_PASSWORD=x\nDITTO_DEVOPS_PASSWORD=x\n", encoding="utf-8")
    result = bench.provision()
    assert result.returncode == 2, _report(result)
    assert "CHANGE_ME" in result.stdout and bench.log() == ""


def test_provision_refuses_a_guest_without_the_egw_data_mount(bench) -> None:
    result = bench.provision(EGW_STUB_FACTS=NO_DATA_DISK_FACTS)
    assert result.returncode == 2, _report(result)
    assert "STOP: guest facts" in result.stdout and "egw-data" in result.stdout
    log = bench.log()
    assert len([line for line in log.splitlines() if line.startswith("ssh ")]) == 1, log
    assert "pull" not in log and "docker load" not in log
    assert bench.record()["result"] == "prerequisites"


def test_provision_happy_path_runs_the_steps_in_order_and_keeps_the_secrets_off_every_argv(bench) -> None:
    result = bench.provision()
    assert result.returncode == 0, _report(result)
    assert result.stdout.rstrip().splitlines()[-1].startswith("PROVISION yocto: result=ok log=")
    log = bench.log()
    marks = ["pull mosquitto mongodb ditto-policies ditto-things ditto-gateway", "docker load", "script generate-dev-tls.sh",
             "script generate-dev-auth.sh", "script prepare-broker-secrets.sh --acl", "script validate-config.sh", "up -d"]
    positions = [log.find(m) for m in marks]
    assert all(p >= 0 for p in positions), f"missing step in the call log: {dict(zip(marks, positions))}\n{log}"
    assert positions == sorted(positions), f"steps out of order: {dict(zip(marks, positions))}"
    assert "chmod 600 " in log and "tar -C " in log and "-xf -" in log
    _assert_no_secret(bench)
    record = bench.record()
    assert record["result"] == "ok" and record["exit"] == 0
    assert [s["name"] for s in record["steps"]] == ["guest-facts", "deployment-tree", "env-file", "images-pull", "controller-load",
                                                     "tls", "auth", "secrets", "validate", "up", "healthy-wait"]
    assert all(s["status"] == "done" and s["rc"] == 0 for s in record["steps"]), record["steps"]
    assert record["seconds_to_healthy"] is not None and record["seconds_to_ready"] is not None
    guest_deploy = bench.guest_root / "opt" / "egw" / "deployment"
    assert (guest_deploy / "scripts" / "validate-config.sh").is_file() and (guest_deploy / ".env").is_file()
    assert (guest_deploy / "mosquitto" / "config" / "passwd").is_file()
    assert (bench.s_dir / "state" / "ca.crt").read_text(encoding="utf-8") == "stub ca\n"
    assert (bench.guest_root / "opt" / "egw" / "evidence" / "images-pull-identity.txt").read_text(encoding="utf-8").count("OK   ") == 5
    assert sorted(p.name for p in (bench.guest_root / "opt" / "egw" / "evidence" / "provision").iterdir()) == [
        "02-tree.done", "03-env.done", "04-images.done", "05-controller.done", "06-tls.done", "07-auth.done",
        "08-secrets.done", "09-validate.done", "10-up.done", "11-healthy.done"]


def test_provision_second_run_skips_the_tree_the_pull_and_the_load(bench) -> None:
    first = bench.provision()
    assert first.returncode == 0, _report(first)
    bench.reset_log()
    second = bench.provision()
    assert second.returncode == 0, _report(second)
    log = bench.log()
    assert " pull mosquitto" not in log and "docker load" not in log and "-xf -" not in log, log
    assert "script generate-dev-tls.sh" not in log and "script generate-dev-auth.sh" not in log
    assert "script prepare-broker-secrets.sh --acl" in log and "script validate-config.sh" in log and "up -d" in log
    status = {s["name"]: s["status"] for s in bench.record()["steps"]}
    assert status["deployment-tree"] == "skipped" and status["images-pull"] == "skipped"
    assert status["up"] == "done" and status["healthy-wait"] == "done"
    _assert_no_secret(bench)


def test_provision_reports_unhealthy_with_exit_1_when_the_limit_passes(bench) -> None:
    result = bench.provision(EGW_STUB_HEALTH="starting", EGW_COMPARE_HEALTH_LIMIT_S="0")
    assert result.returncode == 1, _report(result)
    assert "result=unhealthy" in result.stdout.rstrip().splitlines()[-1]
    assert bench.record()["steps"][-1]["status"] == "unhealthy"


def test_functional_check_passes_on_one_accepted_event_and_a_twin_carrying_the_run_id(bench) -> None:
    result = bench.functional()
    assert result.returncode == 0, _report(result)
    last = result.stdout.rstrip().splitlines()[-1]
    assert last.startswith("FUNCTIONAL yocto fc-01: result=pass sent=1 accepted_delta=1 twin_ok=true"), last
    log = bench.log()
    assert "-m egw_simulator run --scenario smoke --seed 42 --devices smartwatch --rate 1.0 --duration 1 --run-id fc-01" in log
    assert "--password" not in log
    assert "-N -M -S " in log and "-L 8000:127.0.0.1:8000 -L 8080:127.0.0.1:8080" in log and "-O exit" in log
    assert "x-ditto-pre-authenticated: pre:egw-controller" in log and f"org.c2dta:{DEVICE_UUID}" in log
    _assert_no_secret(bench)
    out = next((bench.s_dir / "results").glob("functional-*-fc-01"))
    check = json.loads((out / "check.json").read_text(encoding="utf-8"))
    assert check["run_id"] == "fc-01" and check["seed"] == 42 and check["sent"] == 1
    assert check["device_uuid"] == DEVICE_UUID and check["message_id"] == MESSAGE_ID
    assert check["accepted_delta"] == 1 and check["twin_ok"] is True and check["result"] == "pass"
    assert check["twin_run_id_path"] == "features.ingestion.properties.last_run_id"
    assert isinstance(check["seconds_to_accept"], float)
    for name in ("metrics.before.json", "metrics.after.json", "twin.json", "simulator.stderr.txt", "functional.log"):
        assert (out / name).is_file(), name
    assert (out / "sim" / "fc-01" / "sent_events.jsonl").is_file()
    assert not (bench.state / "tunnel").exists(), "the tunnel master was not closed"


def test_functional_check_fails_when_the_twin_lacks_the_run_id(bench) -> None:
    result = bench.functional(run_id="fc-02", EGW_STUB_TWIN_RUN_ID="some-other-run")
    assert result.returncode == 1, _report(result)
    assert "FUNCTIONAL yocto fc-02: result=fail" in result.stdout.rstrip().splitlines()[-1]
    check = json.loads(next((bench.s_dir / "results").glob("functional-*-fc-02/check.json")).read_text(encoding="utf-8"))
    assert check["twin_ok"] is False and check["twin_run_id_path"] == "none" and check["accepted_delta"] == 1
    assert not (bench.state / "tunnel").exists(), "the tunnel master was not closed"


def test_functional_check_refuses_a_busy_host_port_before_the_simulator(bench) -> None:
    result = bench.functional(run_id="fc-03", EGW_STUB_BUSY_PORTS="8080")
    assert result.returncode == 2, _report(result)
    assert "8000 or 8080" in result.stderr and "egw_simulator run" not in bench.log()


def test_the_scripts_are_shellcheck_clean_at_error_severity() -> None:
    shellcheck = shutil.which("shellcheck") or str(Path(sys.executable).parent / "shellcheck")
    if not Path(shellcheck).is_file():
        pytest.skip("shellcheck is not installed")
    result = subprocess.run([shellcheck, "-S", "error", str(PROVISION), str(FUNCTIONAL)], capture_output=True, text=True)
    assert result.returncode == 0, _report(result)
