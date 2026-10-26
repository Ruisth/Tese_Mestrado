# Reproducing the build, the deployment and the analysis

This page says how to repeat what the dissertation reports:

- prepare the environment;
- build the image;
- deploy the stack;
- run the comparison measurement;
- re-run the analysis.

The results themselves, with their data and code, are listed in [results.md](results.md).
Normal use of the system, without measurement, is in [demo.md](demo.md).

**Reproduction is only partly available from the repository.** Several inputs exist only on the
student's workstation (section 7). The repository alone is enough for:

- the unit tests;
- verifying the evidence seals;
- re-running the analysis of the published G3 raw runs;
- recomputing figures from the published summary data.

Every measured figure came from an ARM64 guest emulated by QEMU/TCG on an x86-64 host, with the
load generator on the same host. A new execution produces new data under the same procedure. It
does not reproduce the published bytes, and it says nothing about physical ARM hardware.

## 1. What can be reproduced, and from what

| Level | What you need | What you get |
|---|---|---|
| A. Offline, repository only | Python 3.11 or later | Unit tests. Seal checks. The G3 analysis re-run from sealed raw runs. The Table 5.2 medians recomputed (section 6) |
| B. a02 summary rebuilt from the original records | Level A, plus the local a02 raw package (section 7) | `summary.csv` of [`evidence/compare-a02/`](evidence/compare-a02/README.md), byte for byte (section 6.4) |
| C. New executions | The full environment of sections 2–5, including the local inputs of section 7 | New executions of the a02 procedure: new data, not the published records |

## 2. Prepare the environment

### 2.1 Host

The recorded host was:

- an x86-64 workstation with Windows 11 and WSL2 Ubuntu 24.04;
- 16 logical CPUs and 31 GiB visible to WSL;
- Python 3.12.3 in WSL.

Set-up guides:

- WSL2, disk space (at least 120 GB free) and the Yocto build packages:
  [setup/wsl2_ubuntu_yocto.md](setup/wsl2_ubuntu_yocto.md);
- host packages, Docker Desktop, the SSH key pair and working directories: runbook
  [setup/qemu_integrated_gateway.md](setup/qemu_integrated_gateway.md) §1.

Build and run from a clone on the WSL ext4 file system, never under `/mnt/*`. Run the scripts in a
WSL login shell (`bash -l`). The comparison tools take their settings from `EGW_*` environment
variables (section 7), so set any non-default values in the login profile.

### 2.2 Python environment

The package root is `src/`. These are the commands of the CI workflow
([`.github/workflows/technical-ci.yml`](../.github/workflows/technical-ci.yml)):

```bash
python3 -m venv ~/egw-exec/venv && . ~/egw-exec/venv/bin/activate
cd src
python -m pip install -e '.[dev,analysis]'
python -m pytest tests -q
```

The comparison tools find this environment through `EGW_EXEC_VENV` (default `~/egw-exec/venv`).
`import egw_simulator, egw_experiments` must work there.

### 2.3 Other tools

| Tool | Version as recorded | Where it is described |
|---|---|---|
| kas | 5.4 (pipx) | [setup/wsl2_ubuntu_yocto.md](setup/wsl2_ubuntu_yocto.md) §5 |
| QEMU | 8.2.7, from the Yocto build's `qemu-helper-native` sysroot, not Ubuntu's package | [tools/compare/README.md](../tools/compare/README.md) §3 |
| Terraform | 1.16.6, checked against HashiCorp's published `SHA256SUMS`, in `$EGW_COMPARE_ROOT/bin` | [tools/compare/README.md](../tools/compare/README.md) §3. The provider lock `tools/compare/terraform/.terraform.lock.hcl` is committed |
| Docker Desktop on Windows | buildx for `linux/arm64` | Runbook §1.4 and §4.1. It builds the controller image only. Inside the guest, Docker comes from the image |

### 2.4 Inputs you create once

None of these is in the repository. Section 7 lists them again.

- **An SSH key pair.** The public half is built into the image (`EGW_AUTHORIZED_KEYS_FILE`); the
  tools use the private half (`EGW_COMPARE_SSH_KEY`, default `~/.ssh/egw_campaign`). See runbook
  §1.5.
- **A secrets file** holding the four broker and service passwords, made from the template
  [`src/deployment/.env.example`](../src/deployment/.env.example). Keep it outside the clone, at
  `EGW_COMPARE_SECRETS_ENV` (default `~/egw-tcg/.env`). The tools check that the names are
  assigned; they never print a value.
- **The controller image archive** and its identity record. Build them with
  `src/deployment/scripts/build-controller-image.sh` (runbook §4.1) and place them in
  `EGW_IMAGES_DIR` (default `~/egw-images`).
- **The runbook helper file**, `~/egw-tcg/itest-helpers.sh`. Only the measurement needs it.
  Generate it from the runbook's §6.1 with `tools/session/regen_helpers.py`:

  ```bash
  python3 tools/session/regen_helpers.py docs/setup/qemu_integrated_gateway.md ~/egw-tcg/itest-helpers.sh
  ```

  `tools/session/proof_hook_drained.sh` always reads it at that path.

## 3. Build the Yocto image

The evaluated image is `egw-gateway-image` for `qemuarm64` (Poky 5.0.19, Scarthgap). It is built
from the integrated kas profile. The full procedure, with the expected outputs and the acceptance
checks, is runbook §2. The layer and the manifests are described in
[src/yocto/README.md](../src/yocto/README.md).

```bash
cd src/yocto
export EGW_AUTHORIZED_KEYS_FILE=$HOME/.ssh/egw_campaign.pub
./scripts/build-profile.sh integrated     # kas checkout + kas build kas/egw-qemuarm64-integrated.yml into build-integrated/
```

- **Layer pins.** `kas/egw-qemuarm64-integrated.lock.yml` pins poky `bb983546…`,
  meta-openembedded `ef3df29f…` and meta-virtualization `0d9fb7fe…`.
- **Output.** `build-integrated/tmp/deploy/images/qemuarm64/` holds the `Image` and
  `egw-gateway-image-qemuarm64.rootfs-<stamp>.ext4`.

**A rebuild reproduces the recipe, not the measured bytes.** The comparison used the deploy file
of stamp `20260918120819` (named in `tools/compare/scenarios/yocto.env`) as it was on disk after
the pilot sessions had booted it read-write. A rebuild has a new stamp and a new root file-system
hash.

- The base copy recorded for the comparison is `bd15040f…` (tools/compare/README.md §9).
- To use a rebuilt image, the scenario must point at the new file. Its manifest identity then
  differs from the published one.

The G1 image (`kas/egw-qemuarm64.yml`, `scripts/build.sh`) is historical. It is not the evaluated
system.

## 4. Deploy the stack

The six-container stack is defined in [`src/deployment/`](../src/deployment/):

- `compose.yaml`;
- `images.lock.env`, which pins five image digests;
- the Mosquitto configuration;
- `scripts/`.

The controller image is built from [`src/Dockerfile`](../src/Dockerfile) with the hashed
`src/requirements-runtime.lock`. Components and ports are described in
[architecture.md](architecture.md).

**Comparison path, as used for every reported comparison figure.** `tools/compare/tf.sh <scenario>
apply` boots one guest and runs `provision_stack.sh`, which automates runbook §5.1–5.6
idempotently. It:

- copies the deployment tree and the secrets file;
- pulls the five pinned images;
- loads and verifies the controller archive;
- generates TLS and broker credentials on the guest;
- starts the stack and waits for six healthy services and `/ready`.

`tf.sh <scenario> stop` stops it in a controlled way. One guest runs at a time.

- Commands, prerequisites and guards: [tools/compare/README.md](../tools/compare/README.md) §0–5.
- A guided walk-through: [demo.md](demo.md).

**Debian 13 base.** The first `prepare` of `debian13` downloads the dated cloud image
`20261017-2634` and checks its SHA512. It runs only with `EGW_COMPARE_ALLOW_DOWNLOAD=1`. That
first boot then installs packages with `apt update` against the live Debian archive, with no
snapshot pin. A new preparation can therefore receive newer package versions than the recorded
one (tools/compare/README.md §4 and §6).

**Manual path.** The runbook's §4–5 give the same steps by hand on the integrated guest. Its
status notes of 2026-09-18/19 are historical. §1–5 are the procedure.

## 5. Run the comparison measurement

The executed procedure is [tools/compare/README.md](../tools/compare/README.md) §10. The record of
series a02 is [`evidence/compare-a02/`](evidence/compare-a02/README.md).
[tools/compare/PROTOCOL.md](../tools/compare/PROTOCOL.md) is an earlier proposal; it was not
the procedure that ran.

```bash
# once per scenario, guest off: the measured base (fresh disks, stack installed by apply, closed by stop, copied with sha256)
bash tools/compare/measure_base.sh yocto
bash tools/compare/measure_base.sh debian13
# the plan: six nominal entries, one seed per pair; write-once
PYTHONPATH=src "${EGW_EXEC_VENV:-$HOME/egw-exec/venv}/bin/python" tools/compare/measure_plan.py write \
    --out "${EGW_COMPARE_ROOT:-$HOME/egw-compare}/measure/plan.json" --seeds S1 S2 S3 [--id-suffix SUFFIX]
# the executions in the plan's order, one guest at a time, then the harness analysis and the summary
bash tools/compare/measure_series.sh "${EGW_COMPARE_ROOT:-$HOME/egw-compare}/measure/plan.json"
```

- **Seeds.** Series a02 used seeds 2026101801, 2026101802 and 2026101803 and the suffix `a02`. Its
  sealed plan is `evidence/compare-a02/plan-a02.json`.
- **Load.** Each execution runs the harness's frozen `nominal` condition: 120 s warm-up, 600 s at
  11.2 msg/s, 60 s confirmation window. These are experimental parameters, not requirements.
- **What the series does.** `measure_series.sh` runs `measure_run.sh` for each planned entry.
  After the last entry it runs `python -m egw_experiments analyze --base-dir <harness> --plan
  <working plan>`, then `measure_summary.py`.
- **Inputs.** `measure_run.sh` stops before starting anything when an input is missing:
  - the virtual environment;
  - the secrets file;
  - the helper file;
  - the measured base;
  - `tools/session/proof_hook_drained.sh` and `nominal_account.py`.

  The comparison depends on `tools/session/`; that folder must stay where it is.
- **Duration.** A pair of executions took roughly an hour on the recorded host. All six ran from
  2026-10-18 21:37Z to 2026-10-19 00:39Z.

The third scenario, `yoctowrynose`, is for demonstration only and was never measured. The plan
and the summary know the measured pair only, and the harness identity check I1 needs a kernel
passed by QEMU, which its UEFI boot does not have (tools/compare/README.md §11).

## 6. Reproduce the analysis offline

Nothing in this section starts a guest. It needs only the clone and the Python environment of
§2.2. Level B (§6.4) also needs the local a02 package.

### 6.1 Tests

```bash
cd src && python -m pytest tests -q
```

The suite uses fakes for MQTT and Ditto. No test is marked `integration`.

- The comparison tests (`test_compare_env.py`, `test_compare_debian.py`,
  `test_compare_provision.py`) run on stubs. Several of them skip on Windows.
- Static checks of the comparison tools: [tools/compare/README.md](../tools/compare/README.md) §8.

### 6.2 Verify the evidence seals

From the repository root, verify every `SHA256SUMS` under `docs/evidence/`, as CI does:

```bash
python tools/ci/verify_evidence.py
```

To check one capsule or package by hand:

```bash
(cd docs/evidence/g3-battery-2026-10 && sha256sum -c PACKAGES.sha256)   # the 38 package seals
(cd docs/evidence/g2-complete-flow && sha256sum -c SHA256SUMS)
```

### 6.3 Re-run the harness analysis on a published G3 run

`analyze` writes `processed/` and `figures/` under its base directory. Run it on a **copy**, never
inside `docs/evidence/`.

```bash
pkg=docs/evidence/g3-battery-2026-10/2026-10-02/20261002T152710Z_g3-qualification-t1-harness_attempt01
work=$(mktemp -d)
mkdir -p "$work/raw" && cp -r "$pkg/raw/nominal-r02" "$work/raw/"
cp "$pkg/other/campaign_plan.after-harness.json" "$work/plan.json"
python -m egw_experiments analyze --base-dir "$work" --plan "$work/plan.json"
```

**Expected.** The `nominal-r02` row of `$work/processed/per_run.csv` equals the sealed
`$pkg/other/processed.after/per_run.csv` row:

| Column | Value |
|---|---|
| `validity` | `valid` |
| `delivered_unique` | 4,584 |
| `lost` | 2,136 |
| `late_confirmations` | 111 |
| `latency_ms_p50` | 178,846.605952 |
| `latency_ms_p95` | 247,078.921324 |

- **Checked on 2026-10-26.** The standard library alone was enough for this. Figures are skipped
  without `matplotlib`.
- **Plan-wide warnings.** Checks across the whole plan, such as the controller-restart summary,
  report the runs that are absent from the copy. That is expected.
- **Test 6.** Use `2026-10-07/20261007T121121Z_g3-qualification-t6_attempt02`,
  `raw/controller_restart-r04` and the plan `other/campaign_plan.after.json` (this package has no
  `campaign_plan.after-harness.json`). Expected row: `valid`, 4,567, 2,153, 67, 128,042.535456,
  250,648.74948.

### 6.4 Rebuild the a02 summary from the original records (level B)

This needs the local raw package of section 7, which holds `measure/runs/` and
`measure/harness/`.

```bash
pkgm=<a02 package>/measure
python3 tools/compare/measure_summary.py --measure-root "$pkgm" \
    --plan docs/evidence/compare-a02/plan-a02.json \
    --per-run-csv "$pkgm/harness/processed/per_run.csv" --out "$(mktemp -d)"
```

**Checked on 2026-10-26.**

- The output `summary.csv` was byte-identical to `evidence/compare-a02/summary.csv`.
- `table.md` and `summary.json` differed only in the generation time and the paths recorded in
  their provenance.
- The one warning, about the failed post-drain fetch of `cmp-p1-yocto-a02`, is expected.

### 6.5 Recompute the Table 5.2 medians from sealed samples

The per-container samples of the two 600 s G3 runs are sealed in their packages. This sums the six
containers per sampling instant and takes the medians (results.md, R8):

```bash
python3 - docs/evidence/g3-battery-2026-10/2026-10-02/20261002T152710Z_g3-qualification-t1-harness_attempt01/raw/nominal-r02/resources.csv <<'PY'
import csv, collections, statistics, sys
mem, cpu, n = collections.defaultdict(float), collections.defaultdict(float), collections.Counter()
for r in csv.DictReader(open(sys.argv[1])):
    mem[r["ts_utc"]] += float(r["mem_bytes"]); cpu[r["ts_utc"]] += float(r["cpu_pct"]); n[r["ts_utc"]] += 1
ts = [t for t in mem if n[t] == 6]
print(len(ts), "instants; memory median", round(statistics.median(mem[t] / 1e6 for t in ts)), "MB;",
      "CPU median", round(statistics.median(cpu[t] for t in ts)), "%")
PY
```

**Expected:** `682 instants; memory median 2000 MB; CPU median 218 %`. For
`controller_restart-r04` the same script gives 601 instants, 2003 MB and 237 %.

The p95 values of Table 5.2 came from a separate local script, which is not in the repository.

### 6.6 What cannot be recomputed from the repository

Some analyses use data or scripts that are local only (results.md, R10 and R11):

- the Table D.8 per-container comparison;
- the a03h host-contention figures;
- the plotting of Figures 5.1 and 5.2. Their input, `evidence/compare-a02/summary.csv`, is in the
  repository; the plotting scripts are not.

## 7. Inputs that exist only locally

None of these is in the repository. Without them, levels B and C are not available.

| Input | Default location (setting) | Needed for |
|---|---|---|
| Yocto build tree and deploy directory of the integrated build, with the QEMU 8.2.7 binary | `~/yocto/egw/src/yocto/build-integrated/` (`EGW_YOCTO_DEPLOY`, `EGW_COMPARE_YOCTO_NATIVE_BIN`) | Booting the `yocto` scenario. The QEMU binary is used by every scenario |
| Base copies and measured bases | `$EGW_COMPARE_ROOT/base/`, `$EGW_COMPARE_ROOT/measure/base/` (default `~/egw-compare`) | Starting and measuring the scenarios |
| Debian 13 prepared base | `$EGW_COMPARE_ROOT/base/debian13/prepared.qcow2` | The `debian13` scenario. A new preparation differs (section 4) |
| yoctoWrynose image package | `EGW_WRYNOSE_PACKAGE` (default `~/images/yoctoWrynose`) | The demonstration-only `yoctowrynose` scenario. It was built outside this repository |
| SSH private keys | `EGW_COMPARE_SSH_KEY`, `EGW_WRYNOSE_SSH_KEY` | Any guest access |
| Secrets file with the four passwords | `EGW_COMPARE_SECRETS_ENV` (default `~/egw-tcg/.env`) | Deployment, simulator, measurement |
| Controller image archive and identity record | `EGW_IMAGES_DIR` (default `~/egw-images`) | Deployment |
| Runbook helper file | `~/egw-tcg/itest-helpers.sh` (generated, §2.4) | The drain step of the measurement |
| Terraform binary, state and plugin cache | `$EGW_COMPARE_ROOT/{bin,tfstate,plugin-cache}` | `tf.sh` |
| Python virtual environment | `EGW_EXEC_VENV` | Simulator, harness, measurement |
| Raw records of series a02 | `output_test/runs/2026-10-19/HIST_2026-10-19-compare-measurements-a02` (583 files, `SHA256SUMS` `87d7ada7…`) | Level B; Table D.8 |
| Run a03h package | `output_test/runs/2026-10-24/HIST_2026-10-24-req10-req11-host-contention-and-storage` (`SHA256SUMS` `b993b395…`) | Tables D.5–D.7 |
| Other local packages | `output_test/runs/…`, `output_test/decisions/…` | The 2026-10-08 unit-test run, the G4 pilot, finite proofs r01 and r02, and the 2026-09-18 candidate archives (results.md) |
| Dissertation analysis and plotting scripts | The dissertation working folder | Tables 5.2 (p95), D.5–D.8 and Figures 5.1–5.2 |

`output_test` is the student's local evidence tree, outside the repository
([setup/local_test_outputs.md](setup/local_test_outputs.md)). Never commit a secrets file, a
private key, or the `keys/` directory that the yoctoWrynose package contains.
