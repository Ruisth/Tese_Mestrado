"""The controller image is prebuilt: pins for deployment/ and its two image scripts.

First part (every platform, text only): the decision itself. On the gateway
``docker compose --env-file .env --env-file images.lock.env up -d`` must never
build or pull the controller, no other service may change with that decision,
and no deployment file may tell the gateway to build.

Second part (POSIX hosts only): ``scripts/build-controller-image.sh`` and
``scripts/verify-controller-image.sh`` are run unmodified under dash and bash
in a throw-away git checkout, with a stub ``docker`` first on PATH. The stub
plays buildx, ``docker save`` (it writes a small archive in either layout) and
``docker image inspect``. What these cases show is the DECISION LOGIC of the
scripts for a given set of observations; they say nothing about Docker, buildx
or the gateway, against which neither script has been executed. The last case
runs step 1 of ``scripts/validate-config.sh`` the same way, against the
``.env`` that the README and the runbook tell the operator to make.
"""
from __future__ import annotations

import hashlib
import os
import re
import shutil
import signal
import stat
import subprocess
import sys
import time
from pathlib import Path

import pytest

SRC_DIR = Path(__file__).resolve().parents[1]
DEPLOY_DIR = SRC_DIR / "deployment"
COMPOSE = DEPLOY_DIR / "compose.yaml"
README = DEPLOY_DIR / "README.md"
LOCK = DEPLOY_DIR / "images.lock.env"
DOCKERFILE = SRC_DIR / "Dockerfile"
SCRIPTS = DEPLOY_DIR / "scripts"
BUILD_SCRIPT = SCRIPTS / "build-controller-image.sh"
VERIFY_SCRIPT = SCRIPTS / "verify-controller-image.sh"
VALIDATE_SCRIPT = SCRIPTS / "validate-config.sh"

CONTROLLER_IMAGE = "egw-controller:0.1.0"
EXTERNAL_SERVICES = {
    "mosquitto": "IMAGE_MOSQUITTO",
    "mongodb": "IMAGE_MONGODB",
    "ditto-policies": "IMAGE_DITTO_POLICIES",
    "ditto-things": "IMAGE_DITTO_THINGS",
    "ditto-gateway": "IMAGE_DITTO_GATEWAY",
}


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _code_lines(text: str) -> list[str]:
    """Lines that are not comments (YAML and shell share the ``#`` rule used here)."""
    return [line for line in text.splitlines() if line.strip() and not line.lstrip().startswith("#")]


def _service_blocks() -> dict[str, list[str]]:
    """Non-comment lines of every service of compose.yaml, keyed by service name."""
    blocks: dict[str, list[str]] = {}
    current: str | None = None
    in_services = False
    for line in _code_lines(_read(COMPOSE)):
        if re.match(r"^\S", line):
            in_services = line.startswith("services:")
            current = None
            continue
        if not in_services:
            continue
        name = re.match(r"^  ([A-Za-z0-9_-]+):\s*$", line)
        if name:
            current = name.group(1)
            blocks[current] = []
        elif current is not None:
            blocks[current].append(line)
    return blocks


def _fenced_code(text: str) -> list[str]:
    lines: list[str] = []
    inside = False
    for line in text.splitlines():
        if line.lstrip().startswith("```"):
            inside = not inside
        elif inside:
            lines.append(line)
    return lines


# --- the decision, as text ---------------------------------------------------------


def test_controller_is_a_prebuilt_image_that_is_never_built_or_pulled() -> None:
    controller = [line.strip() for line in _service_blocks()["controller"]]

    assert f"image: {CONTROLLER_IMAGE}" in controller
    assert "pull_policy: never" in controller
    assert "platform: linux/arm64" in controller
    assert not [line for line in controller if line.startswith(("build:", "context:", "dockerfile:"))]


def test_compose_file_has_no_build_section_at_all() -> None:
    # One file, one invocation shape on the gateway: there is no override file
    # to forget, so "no build: anywhere" is the whole guarantee.
    # The glob covers the names Compose loads by itself next to compose.yaml
    # (compose.override.*, docker-compose.yml, docker-compose.override.*).
    assert not [line for line in _code_lines(_read(COMPOSE)) if re.match(r"^\s*build\s*:", line)]
    assert sorted(path.name for path in DEPLOY_DIR.glob("*compose*.y*ml")) == ["compose.yaml"]
    assert not [line for line in _code_lines(_read(DEPLOY_DIR / ".env.example")) if line.startswith("COMPOSE_")]


def test_the_five_external_services_still_come_from_the_digest_lock_only() -> None:
    blocks = _service_blocks()
    assert sorted(blocks) == sorted([*EXTERNAL_SERVICES, "controller"])
    for service, variable in EXTERNAL_SERVICES.items():
        lines = [line.strip() for line in blocks[service]]
        images = [line for line in lines if line.startswith("image:")]
        assert images == [f"image: ${{{variable}:?set via images.lock.env (pass --env-file images.lock.env)}}"]
        assert not [line for line in lines if line.startswith(("pull_policy:", "build:", "platform:"))]

    entries = dict(
        line.split("=", 1) for line in _read(LOCK).splitlines() if re.match(r"^IMAGE_[A-Z0-9_]+=", line)
    )
    assert sorted(entries) == sorted(EXTERNAL_SERVICES.values())
    assert all(re.fullmatch(r"[^@\s]+:[^@\s]+@sha256:[0-9a-f]{64}", ref) for ref in entries.values())


def test_ports_and_memory_limits_are_the_values_the_records_justify() -> None:
    """The three Ditto services were raised from 512M to 768M on 2026-09-18: on the
    emulated guest they sat at 94-95 per cent of 512M when idle and ditto-things reached
    98.1 per cent after a 672-message run, and a memory-cgroup OOM killed that JVM during
    a power-off. Any further change belongs with its own measurement in compose.yaml.
    """
    text = "\n".join(_code_lines(_read(COMPOSE)))
    assert re.findall(r'^\s+- "([0-9.:]+)"\s*$', text, re.M) == [
        "8883:8883",
        "127.0.0.1:8080:8080",
        "127.0.0.1:8000:8000",
    ]
    assert re.findall(r"^\s+memory: (\S+)\s*$", text, re.M) == ["128M", "512M", "768M", "768M", "768M", "256M"]


def test_no_deployment_file_tells_the_gateway_to_build() -> None:
    offenders = []
    for path in sorted(DEPLOY_DIR.rglob("*")):
        if path.is_file() and path.suffix in {".md", ".sh", ".yaml", ".yml", ".env", ".example"}:
            text = _read(path)
            if "up -d --build" in text or "images.offline.env" in text:
                offenders.append(path.relative_to(DEPLOY_DIR).as_posix())
    assert offenders == []

    commands = _fenced_code(_read(README))
    assert not [line for line in commands if "--build" in line]
    assert not [line for line in commands if re.search(r"docker compose\b.*\bbuild\b", line)]
    assert "docker compose --env-file .env --env-file images.lock.env up -d" in commands

    hint = _read(VALIDATE_SCRIPT).splitlines()[-1]
    assert hint == 'echo "    docker compose --env-file .env --env-file images.lock.env up -d"'


def test_readme_says_where_the_image_comes_from_and_states_the_unlocked_dependencies() -> None:
    readme = " ".join(_read(README).split())

    assert "sh src/deployment/scripts/build-controller-image.sh <output-dir>" in readme
    assert "docker load -i egw-controller-0.1.0-arm64.tar" in readme
    assert "sh scripts/verify-controller-image.sh egw-controller-0.1.0-arm64.identity.txt" in readme
    # The limitation stays in the README for as long as the Dockerfile installs without hashes.
    if "--require-hashes" not in "\n".join(_code_lines(_read(DOCKERFILE))):
        assert "**not locked**" in readme
        assert "unlocked Python dependencies" in readme
        assert readme.count("before the experimental freeze") >= 2
        assert "scripts/generate-runtime-lock.sh" in readme


def test_scripts_agree_on_the_image_and_the_provisioning_script_cannot_push() -> None:
    build = _read(BUILD_SCRIPT)
    assert f'IMAGE="{CONTROLLER_IMAGE}"' in build
    assert 'PLATFORM="linux/arm64"' in build
    assert f'CONTROLLER_IMAGE="{CONTROLLER_IMAGE}"' in _read(VALIDATE_SCRIPT)
    # runbook 5.1/5.5 guard: grep -q "3b\." scripts/validate-config.sh
    assert "3b." in _read(VALIDATE_SCRIPT)

    code = "\n".join(_code_lines(build))
    assert "push" not in code
    assert "login" not in code
    for needle in ("docker buildx build", "--provenance=false", "docker save", "-m pip freeze --all", "--version"):
        assert needle in code

    froms = re.findall(r"^FROM\s+(\S+)", _read(DOCKERFILE), re.M)
    assert len(froms) == 1 and "@sha256:" in froms[0]


# --- the two scripts, executed against a stub docker ------------------------------

STUB_DOCKER = r"""#!/bin/sh
S=$STUB_STATE
printf '%s\n' "$*" >>"$S/calls.log"
beh() { if [ -f "$S/$1" ]; then cat "$S/$1"; else echo "$2"; fi; }
case "$1 ${2:-}" in
    "buildx version") echo "github.com/docker/buildx v0.0.0-stub"; exit 0 ;;
    "buildx build") exit "$(beh build_rc 0)" ;;
    "version --format") [ ! -f "$S/hang" ] || sleep 30; echo "0.0.0-stub"; exit 0 ;;
    "save --help") echo "      --platform string   Save only the given platform variant"; exit 0 ;;
    "image inspect")
        [ ! -f "$S/image_absent" ] || { echo "Error response from daemon: No such image" >&2; exit 1; }
        case "$4" in
            "{{.Architecture}}") beh arch arm64 ;;
            "{{.Os}}") echo linux ;;
            "{{.Id}}") beh engine_id sha256:manifest-digest-of-the-builder ;;
            *revision*) beh revision none ;;
        esac
        exit 0 ;;
    "run --rm")
        case "$*" in
            *"pip freeze --all") printf 'fastapi==0.0.1\npip==0.0.2\n' ;;
            *--version) echo "Python 3.12.13" ;;
        esac
        exit 0 ;;
esac
[ "$1" = save ] || { echo "stub docker: unexpected call: $*" >&2; exit 97; }
out=
while [ $# -gt 0 ]; do
    if [ "$1" = -o ]; then out=$2; fi
    shift
done
T=$S/layout
rm -rf "$T"; mkdir -p "$T/blobs/sha256"
printf '{"architecture":"arm64","os":"linux","stub":true}' >"$T/config"
hex=$(sha256sum "$T/config" | awk '{print $1}')
[ "$(beh archive ok)" != corrupt ] || echo tampered >>"$T/config"
if [ "$(beh layout oci)" = oci ]; then
    cfg="blobs/sha256/$hex"; mv "$T/config" "$T/$cfg"; members="manifest.json blobs"
else
    cfg="$hex.json"; mv "$T/config" "$T/$cfg"; members="manifest.json $cfg"
fi
printf '[{"Config":"%s","RepoTags":["egw-controller:0.1.0"],"Layers":[]}]' "$cfg" >"$T/manifest.json"
tar -cf "$out" -C "$T" $members
"""

posix_only = pytest.mark.skipif(
    sys.platform == "win32" or shutil.which("bash") is None or shutil.which("git") is None,
    reason="needs a POSIX host with bash, git, tar and sha256sum",
)
SHELLS = [
    pytest.param("dash", marks=pytest.mark.skipif(shutil.which("dash") is None, reason="dash is not installed")),
    pytest.param("bash"),
]
STUB_CONFIG_ID = "sha256:" + hashlib.sha256(b'{"architecture":"arm64","os":"linux","stub":true}').hexdigest()


class Checkout:
    def __init__(self, tmp_path: Path, shell: str) -> None:
        self.shell = shell
        self.repo = tmp_path / "repo"
        self.out = tmp_path / "out"
        self.state = tmp_path / "state"
        self.bin = tmp_path / "bin"
        scripts = self.repo / "src" / "deployment" / "scripts"
        scripts.mkdir(parents=True)
        self.state.mkdir()
        self.bin.mkdir()
        shutil.copy(BUILD_SCRIPT, scripts)
        shutil.copy(VERIFY_SCRIPT, scripts)
        shutil.copy(DOCKERFILE, self.repo / "src" / "Dockerfile")
        (self.repo / "NOTES.md").write_text("outside the build context\n", encoding="utf-8")
        stub = self.bin / "docker"
        stub.write_text(STUB_DOCKER, encoding="utf-8")
        stub.chmod(stub.stat().st_mode | stat.S_IXUSR)
        self.git("init", "-q")
        self.commit_all("fixture")

    def git(self, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(["git", "-C", str(self.repo), *args], capture_output=True, text=True, check=True)

    def commit_all(self, message: str) -> None:
        self.git("add", "-A")
        self.git("-c", "user.name=t", "-c", "user.email=t@example.invalid", "-c", "commit.gpgsign=false",
                 "commit", "-q", "-m", message)
        self.commit = self.git("rev-parse", "HEAD").stdout.strip()

    def env(self) -> dict[str, str]:
        return dict(os.environ, PATH=f"{self.bin}{os.pathsep}{os.environ['PATH']}", STUB_STATE=str(self.state))

    def script(self, name: str) -> str:
        return str(self.repo / "src" / "deployment" / "scripts" / name)

    def run(self, script: str, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [self.shell, self.script(script), *args], capture_output=True, text=True, env=self.env(), check=False
        )

    def build(self, *args: str) -> subprocess.CompletedProcess[str]:
        return self.run("build-controller-image.sh", *args, str(self.out))

    def record(self) -> dict[str, list[str]]:
        fields: dict[str, list[str]] = {}
        for line in (self.out / "egw-controller-0.1.0-arm64.identity.txt").read_text(encoding="utf-8").splitlines():
            key, _, value = line.partition("=")
            fields.setdefault(key, []).append(value)
        return fields

    def calls(self) -> str:
        log = self.state / "calls.log"
        return log.read_text(encoding="utf-8") if log.exists() else ""

    def left_behind(self) -> list[str]:
        return sorted(p.name for p in self.out.iterdir()) if self.out.exists() else []


@posix_only
@pytest.mark.parametrize("shell", SHELLS)
@pytest.mark.parametrize("layout", ["oci", "legacy"])
def test_build_script_writes_an_identity_record_from_a_clean_checkout(tmp_path, shell, layout) -> None:
    checkout = Checkout(tmp_path, shell)
    (checkout.state / "layout").write_text(layout, encoding="utf-8")
    (checkout.repo / "NOTES.md").write_text("changed outside src/\n", encoding="utf-8")

    result = checkout.build()

    assert result.returncode == 0, result.stderr
    record = checkout.record()
    archive = checkout.out / "egw-controller-0.1.0-arm64.tar"
    assert record["image_ref"] == [CONTROLLER_IMAGE]
    assert record["image_id"] == [STUB_CONFIG_ID]  # from the archive, not from the builder's inspect
    assert record["builder_image_id"] == ["sha256:manifest-digest-of-the-builder"]
    assert (record["image_os"], record["image_architecture"]) == (["linux"], ["arm64"])
    assert record["source_commit"] == [checkout.commit]
    assert record["source_tree_state"] == ["clean"]
    assert record["source_tree_scope"][0].endswith("files changed outside it: 1")
    assert record["dockerfile_base_image"] == re.findall(r"^FROM\s+(\S+)", _read(DOCKERFILE), re.M)
    assert record["archive_sha256"] == [hashlib.sha256(archive.read_bytes()).hexdigest()]
    assert record["archive_size_bytes"] == [str(archive.stat().st_size)]
    assert record["python_version"] == ["Python 3.12.13"]
    assert record["pip_freeze"] == ["fastapi==0.0.1", "pip==0.0.2"]
    assert record["python_dependencies"][0].startswith("UNLOCKED")
    assert re.fullmatch(r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ", record["built_utc"][0])
    assert checkout.left_behind() == ["egw-controller-0.1.0-arm64.identity.txt", archive.name]

    build_call = next(line for line in checkout.calls().splitlines() if line.startswith("buildx build"))
    assert "--platform linux/arm64" in build_call and "--load" in build_call and "--no-cache" in build_call
    assert f"org.opencontainers.image.revision={checkout.commit} " in build_call
    assert "push" not in checkout.calls()

    # write-once: a second run refuses and leaves the first result alone
    again = checkout.build()
    assert again.returncode == 2 and "refusing to overwrite" in again.stderr
    assert record == checkout.record()


@posix_only
@pytest.mark.parametrize("shell", SHELLS)
def test_build_script_refuses_a_dirty_build_context_unless_told_otherwise(tmp_path, shell) -> None:
    checkout = Checkout(tmp_path, shell)
    (checkout.repo / "src" / "untracked.py").write_text("x = 1\n", encoding="utf-8")

    refused = checkout.build()

    assert refused.returncode == 3
    assert "untracked.py" in refused.stderr
    assert "buildx build" not in checkout.calls()
    assert checkout.left_behind() == []

    allowed = checkout.build("--allow-dirty")

    assert allowed.returncode == 0, allowed.stderr
    assert checkout.record()["source_tree_state"] == ["dirty"]
    assert checkout.record()["image_revision_label"] == [f"{checkout.commit}-dirty"]


@posix_only
@pytest.mark.parametrize("shell", SHELLS)
def test_build_script_counts_git_ignored_files_that_the_dockerfile_would_copy(tmp_path, shell) -> None:
    # `git status` is silent about ignored files, and the root .gitignore ignores
    # names that src/.dockerignore lets through (data/, .env, *.log).
    checkout = Checkout(tmp_path, shell)
    (checkout.repo / ".gitignore").write_text("data/\n.env\n*.log\n__pycache__/\n*.egg-info/\n", encoding="utf-8")
    checkout.commit_all("ignore rules")
    src = checkout.repo / "src"
    for litter in ("egw_controller/__pycache__/app.pyc", "egw_edge_gateway.egg-info/PKG-INFO", "deployment/.env"):
        (src / litter).parent.mkdir(parents=True, exist_ok=True)
        (src / litter).write_text("not copied into the image\n", encoding="utf-8")

    assert checkout.build().returncode == 0
    assert checkout.record()["source_tree_state"] == ["clean"]

    shutil.rmtree(checkout.out)
    (src / "egw_controller" / "data").mkdir()
    (src / "egw_controller" / "data" / "payload.py").write_text("x = 1\n", encoding="utf-8")
    (src / "schemas" / "debug.log").parent.mkdir(exist_ok=True)
    (src / "schemas" / "debug.log").write_text("x\n", encoding="utf-8")
    refused = checkout.build()

    assert refused.returncode == 3
    assert "!! src/egw_controller/data/" in refused.stderr and "!! src/schemas/debug.log" in refused.stderr
    assert "__pycache__" not in refused.stderr and "deployment/.env" not in refused.stderr
    assert checkout.left_behind() == []

    allowed = checkout.build("--allow-dirty")
    assert allowed.returncode == 0, allowed.stderr
    assert checkout.record()["source_tree_state"] == ["dirty"]


@posix_only
@pytest.mark.parametrize("shell", SHELLS)
@pytest.mark.parametrize(("signame", "status"), [("SIGINT", 130), ("SIGTERM", 143), ("SIGHUP", 129)])
def test_build_script_leaves_nothing_behind_when_it_is_interrupted(tmp_path, shell, signame, status) -> None:
    # The stub hangs in step 6, after `docker save` wrote the archive. The signal
    # goes to the process group, as Ctrl-C does; dash runs no EXIT trap on a signal.
    checkout = Checkout(tmp_path, shell)
    (checkout.state / "hang").write_text("1", encoding="utf-8")
    process = subprocess.Popen(
        [shell, checkout.script("build-controller-image.sh"), str(checkout.out)],
        env=checkout.env(), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True,
    )
    # Generous deadlines: a loaded runner is slow, and bash may hold the signal
    # back until the stub's sleep returns before it runs the trap.
    deadline = time.monotonic() + 60
    while "version --format" not in checkout.calls() and time.monotonic() < deadline:
        time.sleep(0.05)
    assert (checkout.out / "egw-controller-0.1.0-arm64.tar").exists(), checkout.calls()

    os.killpg(process.pid, getattr(signal, signame))  # names, not members: SIGHUP does not exist on Windows

    assert process.wait(timeout=60) == status
    assert checkout.left_behind() == []


@posix_only
@pytest.mark.parametrize("shell", SHELLS)
@pytest.mark.parametrize(
    ("behaviour", "value", "message"),
    [
        ("arch", "amd64", "expected linux/arm64"),
        ("archive", "corrupt", "does not hash to its name"),
        ("build_rc", "1", ""),
    ],
)
def test_build_script_leaves_nothing_behind_when_a_step_fails(tmp_path, shell, behaviour, value, message) -> None:
    checkout = Checkout(tmp_path, shell)
    (checkout.state / behaviour).write_text(value, encoding="utf-8")

    result = checkout.build()

    assert result.returncode == 1
    assert message in result.stderr
    assert checkout.left_behind() == []


@posix_only
@pytest.mark.parametrize("shell", SHELLS)
def test_build_script_refuses_an_output_directory_inside_the_build_context(tmp_path, shell) -> None:
    checkout = Checkout(tmp_path, shell)
    checkout.out = checkout.repo / "src" / "out"

    result = checkout.build()

    assert result.returncode == 2
    assert "outside the build context" in result.stderr
    assert "buildx build" not in checkout.calls()


@posix_only
@pytest.mark.parametrize("shell", SHELLS)
def test_verify_script_compares_the_loaded_image_with_the_record(tmp_path, shell) -> None:
    checkout = Checkout(tmp_path, shell)
    assert checkout.build().returncode == 0
    record = str(checkout.out / "egw-controller-0.1.0-arm64.identity.txt")

    # the engine reports another id (here: the builder's manifest digest)
    different = checkout.run("verify-controller-image.sh", record)
    assert different.returncode == 1
    assert "image id differs" in different.stderr and "NOT verified" in different.stderr

    (checkout.state / "engine_id").write_text(STUB_CONFIG_ID, encoding="utf-8")
    (checkout.state / "revision").write_text(checkout.commit, encoding="utf-8")
    identical = checkout.run("verify-controller-image.sh", record)
    assert identical.returncode == 0, identical.stderr
    assert f"CONTROLLER IMAGE IDENTITY: verified ({CONTROLLER_IMAGE} = {STUB_CONFIG_ID})" in identical.stdout
    assert f"OK: revision label {checkout.commit}" in identical.stdout
    assert f"OK: source commit {checkout.commit}, clean build context" in identical.stdout
    assert "UNLOCKED" in identical.stdout

    (checkout.state / "arch").write_text("amd64", encoding="utf-8")
    assert checkout.run("verify-controller-image.sh", record).returncode == 1
    (checkout.state / "arch").unlink()

    (checkout.state / "revision").write_text("0" * 40, encoding="utf-8")
    relabelled = checkout.run("verify-controller-image.sh", record)
    assert relabelled.returncode == 1 and "revision label differs" in relabelled.stderr
    (checkout.state / "revision").write_text(checkout.commit, encoding="utf-8")

    (checkout.state / "image_absent").write_text("1", encoding="utf-8")
    absent = checkout.run("verify-controller-image.sh", record)
    assert absent.returncode == 1 and "is not present" in absent.stderr

    assert checkout.run("verify-controller-image.sh").returncode == 2
    assert checkout.run("verify-controller-image.sh", str(checkout.repo / "NOTES.md")).returncode == 2


@posix_only
@pytest.mark.parametrize("shell", SHELLS)
def test_verify_script_refuses_a_record_from_a_dirty_build_context(tmp_path, shell) -> None:
    checkout = Checkout(tmp_path, shell)
    (checkout.repo / "src" / "untracked.py").write_text("x = 1\n", encoding="utf-8")
    assert checkout.build("--allow-dirty").returncode == 0
    record = str(checkout.out / "egw-controller-0.1.0-arm64.identity.txt")
    (checkout.state / "engine_id").write_text(STUB_CONFIG_ID, encoding="utf-8")
    (checkout.state / "revision").write_text(f"{checkout.commit}-dirty", encoding="utf-8")

    refused = checkout.run("verify-controller-image.sh", record)

    assert refused.returncode == 1
    assert "DIRTY build context" in refused.stderr and "NOT verified" in refused.stderr
    assert "IDENTITY: verified" not in refused.stdout

    allowed = checkout.run("verify-controller-image.sh", "--allow-dirty", record)

    assert allowed.returncode == 0, allowed.stderr
    assert "WARNING" in allowed.stderr and "not for evidence" in allowed.stderr


# --- validate-config.sh steps 1 and 7, with the .env the documents tell the operator to make ---

STUB_DOCKER_ACCEPTS_ALL = "#!/bin/sh\nexit 0\n"
STUB_DOCKER_WITHOUT_THE_CONTROLLER_IMAGE = """#!/bin/sh
case "$1 ${2:-}" in
    "image inspect") echo "Error response from daemon: No such image: $3" >&2; exit 1 ;;
esac
exit 0
"""


@posix_only
@pytest.mark.parametrize("shell", SHELLS)
def test_validate_config_accepts_an_env_file_copied_from_the_example_and_filled_in(tmp_path, shell) -> None:
    # README step 1 and runbook 5.2: cp .env.example .env, then replace the four
    # values. The header comment of .env.example keeps the word CHANGE_ME.
    deploy = tmp_path / "deployment"
    shutil.copytree(SCRIPTS, deploy / "scripts")
    for name in (".env.example", "images.lock.env", "compose.yaml"):
        shutil.copy(DEPLOY_DIR / name, deploy)
    stub = tmp_path / "bin" / "docker"
    stub.parent.mkdir()
    stub.write_text(STUB_DOCKER_ACCEPTS_ALL, encoding="utf-8")
    stub.chmod(stub.stat().st_mode | stat.S_IXUSR)
    env = dict(os.environ, PATH=f"{stub.parent}{os.pathsep}{os.environ['PATH']}")
    example = _read(deploy / ".env.example")
    assert [line for line in example.splitlines() if line.startswith("#") and "CHANGE_ME" in line]

    def validate(text: str) -> subprocess.CompletedProcess[str]:
        (deploy / ".env").write_text(text, encoding="utf-8")
        return subprocess.run(
            [shell, str(deploy / "scripts" / "validate-config.sh")], capture_output=True, text=True, env=env, check=False
        )

    filled_env = re.sub(r"(?m)^([A-Za-z_][A-Za-z0-9_]*=)CHANGE_ME\w*$", r"\g<1>0123456789abcdefghij", example)
    filled = validate(filled_env)
    assert "OK: .env present, no placeholders" in filled.stdout
    assert "CHANGE_ME" not in filled.stderr
    # no TLS material in this copy: steps 2 and 3 are the only failures, 3b is skipped
    assert filled.returncode == 1 and "FAILED: 4 problem(s)" in filled.stderr
    assert f"OK: controller image {CONTROLLER_IMAGE} present" in filled.stdout

    one_left = validate(example.replace("DITTO_DEVOPS_PASSWORD=CHANGE_ME", "DITTO_DEVOPS_PASSWORD=x", 1))
    assert "still contains CHANGE_ME placeholder value(s)" in one_left.stderr
    assert "OK: .env present" not in one_left.stdout

    # step 7 asks the engine rather than trusting the file: with the controller
    # image absent the same .env yields one failure more, and the hint is to load
    # the archive — nothing on the gateway ever builds or pulls it.
    stub.write_text(STUB_DOCKER_WITHOUT_THE_CONTROLLER_IMAGE, encoding="utf-8")
    absent = validate(filled_env)
    assert f"controller image {CONTROLLER_IMAGE} is not present on this engine" in absent.stderr
    assert "docker load -i" in absent.stderr
    assert absent.returncode == 1 and "FAILED: 5 problem(s)" in absent.stderr
    assert f"OK: controller image {CONTROLLER_IMAGE} present" not in absent.stdout
