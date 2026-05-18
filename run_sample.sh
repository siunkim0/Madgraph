#!/usr/bin/env bash
# Generic driver: run the full MG5 -> Pythia8 -> Delphes -> NanoAOD chain
# for any sample that has cards/<SAMPLE>_proc.dat and cards/<SAMPLE>_launch.txt.
#
# Usage:
#   ./run_sample.sh <sample_name>
#
# Examples:
#   ./run_sample.sh ZZto4L
#   ./run_sample.sh DYJetsToLL_M-50
#   ./run_sample.sh VBFHToZZTo4L
#   ./run_sample.sh VHToNonbb
#
# Requirements:
#   - MG5_ROOT env var must point to your MadGraph5 installation, OR
#     mg5_aMC must be on PATH.
#   - ROOT must be on PATH (source your ROOT setup before running).

set -euo pipefail

# --- Parse arguments -------------------------------------------------------
if [[ $# -lt 1 ]]; then
    echo "Usage: $0 <sample_name>"
    echo ""
    echo "Available samples (based on cards/*_proc.dat):"
    for f in "$(cd "$(dirname "$0")" && pwd)"/cards/*_proc.dat; do
        name="$(basename "$f" _proc.dat)"
        echo "  - ${name}"
    done
    exit 1
fi

SAMPLE="$1"

# --- Auto-detect paths ------------------------------------------------------
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROC_CARD="${SCRIPT_DIR}/cards/${SAMPLE}_proc.dat"
LAUNCH_CARD="${SCRIPT_DIR}/cards/${SAMPLE}_launch.txt"
PROC_DIR="${SCRIPT_DIR}/output/${SAMPLE}"

if [[ ! -f "${PROC_CARD}" ]]; then
    echo "ERROR: process card not found: ${PROC_CARD}" >&2
    exit 1
fi
if [[ ! -f "${LAUNCH_CARD}" ]]; then
    echo "ERROR: launch card not found: ${LAUNCH_CARD}" >&2
    exit 1
fi

# --- Find MadGraph5 ---------------------------------------------------------
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

# Check that ROOT is available
if ! command -v root-config &>/dev/null; then
    echo "ERROR: ROOT not found on PATH." >&2
    echo "  Source your ROOT setup script, e.g.:" >&2
    echo "    source /path/to/ROOT/bin/thisroot.sh" >&2
    exit 1
fi

cd "${MG5_ROOT}"

echo "=========================================="
echo "  Sample:  ${SAMPLE}"
echo "  MG5:     ${MG5}"
echo "  ROOT:    $(root-config --version)"
echo "=========================================="

# --- Step 1: generate the process directory if missing ----------------------
if [[ ! -d "${PROC_DIR}" ]]; then
    echo "[1/3] Generating process directory ..."
    "${MG5}" "${PROC_CARD}"
else
    echo "[1/3] Process dir already exists: ${PROC_DIR} (skip)"
fi

# --- Step 2: launch with Pythia8 + Delphes ----------------------------------
echo "[2/3] Launching event generation (Pythia8 + Delphes) ..."
"${MG5}" -f "${LAUNCH_CARD}"

# --- Step 3: convert Delphes -> NanoAOD-mimic -------------------------------
# Find the most recent run directory
RUN_DIR=$(ls -td "${PROC_DIR}/Events"/run_* 2>/dev/null | head -1)
if [[ -z "${RUN_DIR}" ]]; then
    echo "ERROR: no run directories found in ${PROC_DIR}/Events/" >&2
    exit 1
fi

DELPHES_OUT="${RUN_DIR}/tag_1_delphes_events.root"
if [[ ! -f "${DELPHES_OUT}" ]]; then
    echo "ERROR: no Delphes ROOT found at ${DELPHES_OUT}" >&2
    exit 1
fi

RUN_TAG=$(basename "${RUN_DIR}")
NANO_OUT="${PROC_DIR}/nano/${SAMPLE}_${RUN_TAG}.root"
mkdir -p "$(dirname "${NANO_OUT}")"

echo "[3/3] Converting ${DELPHES_OUT} -> ${NANO_OUT}"
python3 "${SCRIPT_DIR}/scripts/delphes_to_nano.py" \
    --in  "${DELPHES_OUT}" \
    --out "${NANO_OUT}" \
    --label 1

echo ""
echo "Done. Output: ${NANO_OUT}"
