#!/usr/bin/env bash
# End-to-end driver: ggH -> ZZ -> 4mu signal sample.
#
# Steps:
#   1. (once) generate the process directory     [proc_card -> output/]
#   2. launch with Pythia8 + Delphes              [-> tag_1_delphes_events.root]
#   3. convert Delphes -> NanoAOD-mimic ROOT      [-> nano/ggH_ZZ_4mu.root]
#
# Run from the repo root:
#   bash run_signal.sh
#
# Requirements:
#   - MG5_ROOT env var must point to your MadGraph5 installation, OR
#     mg5_aMC must be on PATH.
#   - ROOT must be on PATH (source your ROOT setup before running).

set -euo pipefail

# --- Auto-detect paths ----------------------------------------------------
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
SAMPLE="ggH_ZZ_4mu"
PROC_DIR="${SCRIPT_DIR}/output/${SAMPLE}"
RUN_DIR="${PROC_DIR}/Events/run_01"

# Source local overrides if present (gitignored)
if [[ -f "${SCRIPT_DIR}/local.conf" ]]; then
    # shellcheck disable=SC1091
    source "${SCRIPT_DIR}/local.conf"
fi

# Defaults (can be overridden in local.conf)
CONVERTER_SCRIPT="${CONVERTER_SCRIPT:-${SCRIPT_DIR}/scripts/delphes_to_nano.py}"
NANO_OUT="${NANO_OUTPUT_DIR:-${PROC_DIR}/nano/${SAMPLE}.root}"

# Find MadGraph5
if [[ -n "${MG5_ROOT:-}" ]] && [[ -x "${MG5_ROOT}/bin/mg5_aMC" ]]; then
    MG5="${MG5_ROOT}/bin/mg5_aMC"
elif command -v mg5_aMC &>/dev/null; then
    MG5="$(command -v mg5_aMC)"
    MG5_ROOT="$(dirname "$(dirname "${MG5}")")"
else
    echo "ERROR: MadGraph5 not found." >&2
    echo "  Set MG5_ROOT to your MG5 installation directory," >&2
    echo "  or add mg5_aMC to your PATH." >&2
    exit 1
fi

cd "${MG5_ROOT}"

# Check that ROOT is available
if ! command -v root-config &>/dev/null; then
    echo "ERROR: ROOT not found on PATH." >&2
    echo "  Source your ROOT setup script, e.g.:" >&2
    echo "    source /path/to/ROOT/bin/thisroot.sh" >&2
    exit 1
fi

# --- Step 1: generate the process directory if missing ------------------
if [[ ! -d "${PROC_DIR}" ]]; then
    echo "[1/3] Generating process directory ..."
    "${MG5}" "${SCRIPT_DIR}/cards/ggH_ZZ_4mu_proc.dat"
else
    echo "[1/3] Process dir already exists: ${PROC_DIR} (skip)"
fi

# --- Step 2: launch with Pythia8+Delphes --------------------------------
echo "[2/3] Launching event generation (100k evts, Pythia8+Delphes) ..."
"${MG5}" -f "${SCRIPT_DIR}/cards/ggH_ZZ_4mu_launch.txt"

# --- Step 3: convert Delphes -> NanoAOD-mimic ---------------------------
DELPHES_OUT=$(ls -t "${RUN_DIR}"/tag_1_delphes_events.root 2>/dev/null | head -1)
if [[ -z "${DELPHES_OUT}" ]]; then
    echo "ERROR: no Delphes ROOT found in ${RUN_DIR}" >&2
    exit 1
fi

echo "[3/3] Converting ${DELPHES_OUT} -> ${NANO_OUT}"
mkdir -p "$(dirname "${NANO_OUT}")"
python3 "${CONVERTER_SCRIPT}" \
    --in  "${DELPHES_OUT}" \
    --out "${NANO_OUT}" \
    --label 1

echo
echo "Done. Output: ${NANO_OUT}"

