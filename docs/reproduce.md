# How to reproduce

How to rebuild the gateway image, deploy it, repeat the comparison measurements and re-run the
analysis. The results are on the [results page](results.md). Everyday use, without measurement, is
in the [demonstration guide](demo.md).

> Every figure came from an ARM64 computer **emulated** by QEMU (TCG) on an x86-64 PC, with the
> simulated devices on the same PC. A new run follows the same procedure and gives new data. It
> does not reproduce the recorded files, and it says nothing about physical ARM hardware.

## What you can repeat

| With | You can |
|---|---|
| The repository and Python 3.11 or later | Run the unit tests, check the evidence checksums, re-run the analysis of a recorded run and recompute its resource medians (§5) |
| The above, plus the local raw records of the comparison (§6) | Rebuild the comparison summary byte for byte (§5.3) |
| The full environment (§1–4) and the local inputs (§6) | Run the comparison again: new data, not the recorded files |

**The demonstration kit is not a reproduction.** A PC prepared with the demonstration kit
([tools/setup](../tools/setup/README.md)) runs the [demonstration](demo.md) only. It uses Ubuntu's QEMU
8.2.x and a sanitised copy of the image, whose checksum differs from that of the measured image.
Repeating the measurements needs the original inputs: QEMU 8.2.7 from the Yocto build, the original
sealed root file system of the measurements (§2; a rebuild gives a new file with a new checksum) and
the inputs kept locally (§6).

## 1. Environment

**Recorded PC:** x86-64, Windows 11 with WSL2 Ubuntu 24.04, 16 logical CPUs and 31 GiB visible to
WSL, Python 3.12.3 in WSL.

- WSL2, disk space (at least 120 GB free) and the Yocto build packages:
  [setup/wsl2_ubuntu_yocto.md](setup/wsl2_ubuntu_yocto.md).
- Host packages, Docker Desktop, the SSH key pair and the working folders: the runbook
  [setup/qemu_integrated_gateway.md](setup/qemu_integrated_gateway.md) §1.
- Work in a clone on the WSL ext4 file system, never under `/mnt/*`, in a login shell (`bash -l`).
  The tools read `EGW_*` environment variables; put any non-default value in the login profile.

**Python environment.** The package root is `src/`; the tools find the environment through
`EGW_EXEC_VENV` (default `~/egw-exec/venv`). These are the commands of the automatic checks, run from
the root of the clone:

```bash
python3 -m venv ~/egw-exec/venv && . ~/egw-exec/venv/bin/activate
cd src
python -m pip install -e '.[dev,analysis]'
python -m pytest tests -q
cd ..                                     # back to the root of the clone
```

The commands in the rest of this page also run from the root of the clone, with this environment
active.

**Other tools**

| Tool | Version | Notes |
|---|---|---|
| kas | 5.4 (pipx) | [setup/wsl2_ubuntu_yocto.md](setup/wsl2_ubuntu_yocto.md) |
| QEMU | 8.2.7 | Taken from the Yocto build (`qemu-helper-native`), not Ubuntu's package |
| Terraform | 1.16.6 | Checked against HashiCorp's `SHA256SUMS` and installed in `$EGW_COMPARE_ROOT/bin`. The provider lock `tools/compare/terraform/.terraform.lock.hcl` is in the repository |
| Docker Desktop (Windows) | buildx for `linux/arm64` | Builds the controller image only. Inside the gateway, Docker comes from the image |

**Created once, never stored in the repository**

- An **SSH key pair**. The public key goes into the image (`EGW_AUTHORIZED_KEYS_FILE`); the tools
  use the private key (`EGW_COMPARE_SSH_KEY`, default `~/.ssh/egw_campaign`). Runbook §1.5.
- A **secrets file** with the four passwords, made from
  [`src/deployment/.env.example`](../src/deployment/.env.example) and kept outside the clone
  (`EGW_COMPARE_SECRETS_ENV`, default `~/egw-tcg/.env`). The tools never print a value.
- The **controller image archive** and its identity record, built with
  `src/deployment/scripts/build-controller-image.sh` (runbook §4.1) and placed in `EGW_IMAGES_DIR`
  (default `~/egw-images`).
- For the measurements only, the **helper file** `~/egw-tcg/itest-helpers.sh`, generated from the
  runbook. It is always read from this path.

  ```bash
  mkdir -p ~/egw-tcg
  python3 tools/session/regen_helpers.py docs/setup/qemu_integrated_gateway.md ~/egw-tcg/itest-helpers.sh
  ```

## 2. Build the Yocto image

The measured image is `egw-gateway-image` for `qemuarm64` (Poky 5.0.19, Scarthgap). Full procedure,
expected outputs and checks: runbook §2. The layer and kas files:
[src/yocto/README.md](../src/yocto/README.md).

```bash
cd src/yocto
export EGW_AUTHORIZED_KEYS_FILE=$HOME/.ssh/egw_campaign.pub
./scripts/build-profile.sh integrated     # kas build of kas/egw-qemuarm64-integrated.yml into build-integrated/
cd ../..                                  # back to the root of the clone
```

- **Layer versions** (`kas/egw-qemuarm64-integrated.lock.yml`): poky `bb983546…`,
  meta-openembedded `ef3df29f…`, meta-virtualization `0d9fb7fe…`.
- **Output** (`build-integrated/tmp/deploy/images/qemuarm64/`): `Image` and
  `egw-gateway-image-qemuarm64.rootfs-<stamp>.ext4`.
- **A rebuild repeats the recipe, not the measured file.** The measurements used the root file
  system of stamp `20260918120819` (named in `tools/compare/scenarios/yocto.env`), which had already
  been booted read-write; its recorded base copy is `bd15040f…`. A rebuild has a new stamp and a
  new hash. To use it, point the scenario file at the new file.
- `kas/egw-qemuarm64.yml` (`scripts/build.sh`) builds an earlier base image without containers.

## 3. Deploy the services

```bash
bash tools/compare/tf.sh yocto apply      # or debian13
bash tools/compare/tf.sh yocto stop
```

`apply` starts one gateway and runs `provision_stack.sh` (safe to run twice). It copies the
deployment folder and the secrets file, pulls the five pinned images, loads and checks the
controller archive, creates the TLS certificates and the broker's password file on the gateway (from
the passwords in the secrets file), starts the six services and waits until they are healthy and `/ready` answers.

`stop` powers the gateway off in a controlled way. Only one gateway runs at a time. Commands and
checks: [tools/compare/README.md](../tools/compare/README.md). A guided walk-through:
[demo.md](demo.md). The same steps by hand: runbook §4–5.

**Debian 13.** The first `apply` downloads the cloud image `20261017-2634` and checks its SHA512,
but only when `EGW_COMPARE_ALLOW_DOWNLOAD=1` is set. Its first boot installs packages from the live
Debian archive, so a new preparation can get newer package versions than the recorded one.

## 4. Repeat the comparison measurements

The procedure that ran is in [tools/compare/README.md](../tools/compare/README.md); its records are
in the [Yocto–Debian comparison records](evidence/compare-a02/README.md). `tools/compare/PROTOCOL.md`
is an earlier proposal, not what ran.

```bash
# once per configuration, with no gateway running: the measured base (the disks right after installation)
bash tools/compare/measure_base.sh yocto
bash tools/compare/measure_base.sh debian13
# the plan: three pairs, one seed per pair (the recorded seeds); written once.
# --id-suffix is optional and names the runs of a new series; "rerun1" is only an example.
PYTHONPATH=src "${EGW_EXEC_VENV:-$HOME/egw-exec/venv}/bin/python" tools/compare/measure_plan.py write \
    --out "${EGW_COMPARE_ROOT:-$HOME/egw-compare}/measure/plan.json" \
    --seeds 2026101801 2026101802 2026101803 --id-suffix rerun1
# the six runs in the plan's order, then the analysis and the summary
bash tools/compare/measure_series.sh "${EGW_COMPARE_ROOT:-$HOME/egw-compare}/measure/plan.json"
```

- **Recorded plan:** `evidence/compare-a02/plan-a02.json` (suffix `a02`). Give a new series a new
  suffix (1 to 16 letters, digits or hyphens).
- **One run** (`measure_run.sh`): restore the measured base, start, send one test message to its
  twin, rest for 120 s, then the load: 120 s warm-up, 600 s at 11.2 msg/s, 60 s to confirm. Then
  wait until the controller has been quiet for 130 s (at most 900 s) and power off. The load is an
  experimental setting, not a requirement. After the six runs, `measure_series.sh` runs
  `python -m egw_experiments analyze` and `measure_summary.py`. Each pair took about an hour.
- **Before starting anything**, each run checks its inputs: the Python environment, the secrets
  file, the helper file, the measured base, and `tools/session/proof_hook_drained.sh` and
  `nominal_account.py`. Keep `tools/session/` where it is.
- `yoctowrynose` was never measured. The plan covers only the other two, and one identity check
  needs a kernel passed directly by QEMU, which its UEFI boot does not have.

## 5. Re-run the analysis offline

Nothing here starts a gateway. You need the clone and the Python environment of §1. §5.3 also needs
the local raw records.

### 5.1 Tests and evidence checksums

The tests are the `pytest` command of §1; MQTT and Ditto are replaced by fakes, and some tests of
the comparison tools are skipped on Windows. To check every `SHA256SUMS` under `docs/evidence/`
from the repository root, as the automatic checks do:

```bash
python tools/ci/verify_evidence.py
```

### 5.2 Re-run the analysis of a recorded 10-minute run

`analyze` writes `processed/` and `figures/` into its base folder, so work on a **copy**, never
inside `docs/evidence/`.

```bash
pkg=docs/evidence/g3-battery-2026-10/2026-10-02/20261002T152710Z_g3-qualification-t1-harness_attempt01
work=$(mktemp -d)
mkdir -p "$work/raw" && cp -r "$pkg/raw/nominal-r02" "$work/raw/"
cp "$pkg/other/campaign_plan.after-harness.json" "$work/plan.json"
python -m egw_experiments analyze --base-dir "$work" --plan "$work/plan.json"
```

**Expected:** the row for this run in `$work/processed/per_run.csv` equals the recorded row in
`$pkg/other/processed.after/per_run.csv`: `validity` `valid`, `delivered_unique` 4,584, `lost`
2,136, `late_confirmations` 111, `latency_ms_p50` 178,846.605952, `latency_ms_p95` 247,078.921324.

- `lost` means "not confirmed within the time limit". This run has no record taken after the backlog
  cleared, so its final count is not known.
- The standard library is enough (figures are skipped without `matplotlib`). Warnings about the
  runs that are not in the copy are expected.
- **The run with a controller restart:** use the package
  `2026-10-07/20261007T121121Z_g3-qualification-t6_attempt02`, its `raw/controller_restart-r04` and
  the plan `other/campaign_plan.after.json`. Expected, in the same order: `valid`, 4,567, 2,153, 67,
  128,042.535456, 250,648.74948.

### 5.3 Rebuild the comparison summary (needs the local raw records)

```bash
# set this to the measure/ folder of your local copy of the comparison's raw records (§6)
pkgm="/path/to/HIST_2026-10-19-compare-measurements-a02/measure"
python3 tools/compare/measure_summary.py --measure-root "$pkgm" \
    --plan docs/evidence/compare-a02/plan-a02.json \
    --per-run-csv "$pkgm/harness/processed/per_run.csv" --out "$(mktemp -d)"
```

**Expected:** `summary.csv` is byte-identical to `evidence/compare-a02/summary.csv`. `table.md` and
`summary.json` differ only in the generation time and the paths they record. One warning is
expected: in the first Yocto run, the copy of the controller's event log after the final wait failed.

### 5.4 Recompute the resource medians of a 10-minute run

The per-container samples are in the recorded package. This adds up the six containers at each
sampling instant and takes the medians:

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

**Expected:** `682 instants; memory median 2000 MB; CPU median 218 %`. For the controller-restart
run (`raw/controller_restart-r04/resources.csv` of its package) it gives 601 instants, 2003 MB and
237 %. The p95 values in the dissertation came from a local script that is not in the repository.

## 6. Inputs kept only locally

None of these is in the repository. Without them, only the first row of "What you can repeat" applies.

| Input | Default location (setting) | Needed for |
|---|---|---|
| Yocto build folder, with the QEMU 8.2.7 binary | `~/yocto/egw/src/yocto/build-integrated/` (`EGW_YOCTO_DEPLOY`, `EGW_COMPARE_YOCTO_NATIVE_BIN`) | Starting `yocto`. Every configuration uses this QEMU |
| Base copies and measured bases | `$EGW_COMPARE_ROOT/base/`, `$EGW_COMPARE_ROOT/measure/base/` (default `~/egw-compare`) | Starting and measuring |
| Prepared Debian 13 disk | `$EGW_COMPARE_ROOT/base/debian13/prepared.qcow2` | `debian13`. A new preparation differs (§3) |
| yoctoWrynose image package | `EGW_WRYNOSE_PACKAGE` (default `~/images/yoctoWrynose`) | `yoctowrynose`, demonstration only |
| The inputs created once (§1): SSH keys, secrets file, controller archive, helper file, Python environment | See §1; `EGW_WRYNOSE_SSH_KEY` for `yoctowrynose` | Deployment, simulator, measurements |
| Terraform binary, state and plugin cache | `$EGW_COMPARE_ROOT/{bin,tfstate,plugin-cache}` | `tf.sh` |
| Raw records of the comparison | `output_test/runs/2026-10-19/HIST_2026-10-19-compare-measurements-a02` (583 files, `SHA256SUMS` `87d7ada7…`) | §5.3 and the per-container comparison |
| Host-contention and storage records | `output_test/runs/2026-10-24/HIST_2026-10-24-req10-req11-host-contention-and-storage` (`SHA256SUMS` `b993b395…`) | The host-contention and storage figures |
| Other local records | `output_test/` | Some earlier runs listed on the results page |
| Dissertation analysis and plotting scripts | the dissertation's working folder | The resource p95 values, the per-container comparison, the host-contention figures and the comparison plots (their input, `evidence/compare-a02/summary.csv`, is in the repository) |

`output_test` is the student's local evidence folder, outside the repository
([setup/local_test_outputs.md](setup/local_test_outputs.md)). Never commit a secrets file, a private
key, or the `keys/` folder inside the yoctoWrynose package.
