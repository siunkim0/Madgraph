#!/usr/bin/env bash
# End-to-end driver: ggH -> ZZ -> 4mu signal sample for the BDT_git project.
#
# Steps:
#   1. (once) generate the process directory     [proc_card -> output/]
#   2. launch with Pythia8 + Delphes              [-> tag_1_delphes_events.root]
#   3. convert Delphes -> NanoAOD-mimic ROOT      [-> nano/ggH_ZZ_4mu.root]
#
# Run from the MG5 root dir:
#   bash BDT_MC/run_signal.sh

set -euo pipefail

MG5_ROOT="/data6/Users/snuintern2/folder/Madgraph/MG5_aMC_v3_5_6"
WORK="${MG5_ROOT}/BDT_MC"
PROC_DIR="${WORK}/output/ggH_ZZ_4mu"
RUN_DIR="${PROC_DIR}/Events/run_01"
NANO_OUT="${PROC_DIR}/nano/ggH_ZZ_4mu.root"

cd "${MG5_ROOT}"

# Activate ROOT (user has 'rot' alias defined in ~/.bashrc).
# When run from a non-interactive shell, aliases aren't loaded by default,
# so we re-source .bashrc. Adjust if your alias lives elsewhere.
shopt -s expand_aliases
source ~/.bashrc 2>/dev/null || true
type rot &>/dev/null && rot

# --- Step 1: generate the process directory if missing ------------------
if [[ ! -d "${PROC_DIR}" ]]; then
    echo "[1/3] Generating process directory ..."
    ./bin/mg5_aMC "${WORK}/cards/ggH_ZZ_4mu_proc.dat"
else
    echo "[1/3] Process dir already exists: ${PROC_DIR} (skip)"
fi

# --- Step 2: launch with Pythia8+Delphes --------------------------------
echo "[2/3] Launching event generation (100k evts, Pythia8+Delphes) ..."
./bin/mg5_aMC -f "${WORK}/cards/ggH_ZZ_4mu_launch.txt"

# --- Step 3: convert Delphes -> NanoAOD-mimic ---------------------------
DELPHES_OUT=$(ls -t "${RUN_DIR}"/tag_1_delphes_events.root 2>/dev/null | head -1)
if [[ -z "${DELPHES_OUT}" ]]; then
    echo "ERROR: no Delphes ROOT found in ${RUN_DIR}" >&2
    exit 1
fi

echo "[3/3] Converting ${DELPHES_OUT} -> ${NANO_OUT}"
mkdir -p "$(dirname "${NANO_OUT}")"
python3 "${WORK}/scripts/delphes_to_nano.py" \
    --in  "${DELPHES_OUT}" \
    --out "${NANO_OUT}" \
    --label 1

echo
echo "Done. Point BDT_git samples.yaml -> ${NANO_OUT}"
