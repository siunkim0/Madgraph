#!/usr/bin/env bash
# Condor worker-node wrapper for the ggH -> ZZ -> 4mu MC chain.
#
# This is invoked by run_signal.sub via Condor. It runs on a worker node,
# reading & writing directly to the shared filesystem at /data6 (assumes
# /data6 is mounted on the execute hosts; tamsa cluster mounts it).
#
# Arguments: none (paths are hardcoded; intentional, so the Condor log
#            tells you exactly which run produced which file).

set -eo pipefail

# --- Environment -------------------------------------------------------
MG5_ROOT="/data6/Users/snuintern2/folder/Madgraph/MG5_aMC_v3_5_6"
WORK="${MG5_ROOT}/BDT_MC"
PROC_DIR="${WORK}/output/ggH_ZZ_4mu"

# ROOT from CVMFS (needed for Delphes). Use LCG view directly so we don't
# depend on the user's ~/.bashrc on the worker node.
LCG_SETUP="/cvmfs/sft.cern.ch/lcg/views/LCG_105/x86_64-el9-gcc11-opt/setup.sh"
if [[ -r "${LCG_SETUP}" ]]; then
    set +u
    source "${LCG_SETUP}"
    set -u
fi
command -v root >/dev/null || { echo "ERROR: ROOT not on PATH" >&2; exit 1; }

# CRITICAL: LCG setup exports PYTHIA8DATA pointing at Pythia 8.310 xmldoc,
# but MG5's bundled Pythia is 8.316. Version mismatch -> every PY8 shard
# aborts -> empty DJR histogram -> "Histogram with run_id '0' was not
# found" at the merge step. Unset to fall back to the local install's
# compiled-in xmldoc path.
unset PYTHIA8DATA

# Optional: cap parallelism per job. With nb_core=48 the multicore PY8
# split can be flaky on a shared worker. Use min(NCPUS, 16).
NCPUS="${_CONDOR_NCORES:-${NCPUS:-8}}"

cd "${MG5_ROOT}"

# --- Step 1: build process dir if missing -----------------------------
if [[ ! -d "${PROC_DIR}" ]]; then
    echo "[$(date)] [1/3] generating process directory"
    ./bin/mg5_aMC "${WORK}/cards/ggH_ZZ_4mu_proc.dat"
else
    echo "[$(date)] [1/3] process dir exists: ${PROC_DIR}"
fi

# --- Step 2: launch event generation ----------------------------------
echo "[$(date)] [2/3] launching event generation (${NCPUS} cores)"

# Build a per-job launch script: same as the interactive one but force
# multicore run with NCPUS, never cluster mode (we ARE the cluster job).
JOB_LAUNCH="${WORK}/condor/_launch_$$.txt"
cat > "${JOB_LAUNCH}" <<EOF
launch ${PROC_DIR}
shower=Pythia8
detector=Delphes
done
set run_mode 2
set nb_core ${NCPUS}
set nevents 100000
set ebeam1 6800.0
set ebeam2 6800.0
set pdlabel nn23lo1
set lhaid 230000
set mh 125.0
set wh auto
set delphes_card delphes_card_CMS
done
EOF

./bin/mg5_aMC -f "${JOB_LAUNCH}"
rm -f "${JOB_LAUNCH}"

# --- Step 3: pick the newest run, convert to NanoAOD-mimic ------------
RUN_DIR=$(ls -td "${PROC_DIR}/Events"/run_* 2>/dev/null | head -1)
DELPHES_OUT="${RUN_DIR}/tag_1_delphes_events.root"
[[ -f "${DELPHES_OUT}" ]] || { echo "ERROR: no Delphes ROOT at ${DELPHES_OUT}" >&2; exit 1; }

RUN_TAG=$(basename "${RUN_DIR}")
NANO_OUT="${PROC_DIR}/nano/ggH_ZZ_4mu_${RUN_TAG}.root"
mkdir -p "$(dirname "${NANO_OUT}")"

echo "[$(date)] [3/3] converting ${DELPHES_OUT}"
python3 "${WORK}/scripts/delphes_to_nano.py" \
    --in  "${DELPHES_OUT}" \
    --out "${NANO_OUT}" \
    --label 1

echo "[$(date)] DONE. Output: ${NANO_OUT}"
