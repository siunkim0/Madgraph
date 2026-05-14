# Monte Carlo Signal and Background Sample Generation for H → ZZ → 4μ Analysis

End-to-end pipeline for generating Monte Carlo samples using MadGraph5_aMC@NLO + Pythia8 + Delphes, with conversion to NanoAOD-compatible ROOT files for downstream physics analysis.

```
MadGraph5  ─►  Pythia8  ─►  Delphes (CMS)  ─►  delphes_to_sknano.py
   LHE        showered        detector-          NanoAOD-
                              level ROOT         style ROOT
```


## Overview

This repository provides an automated pipeline for producing analysis-ready Monte Carlo samples for the H → ZZ → 4μ search at √s = 13.6 TeV. The primary signal process is gluon-gluon fusion Higgs production (ggH) with subsequent decay to four muons via Z boson pairs. Leading-order matrix elements are generated using the Higgs Effective Field Theory (HEFT) model in MadGraph5, showered with Pythia8, passed through the Delphes fast detector simulation with the CMS detector card, and converted to a NanoAOD-mimicking flat ROOT tree for compatibility with standard CMS analysis frameworks.

**Signal process:** `g g > h > z z, z > mu+ mu-`

| Parameter | Value |
|-----------|-------|
| Model | HEFT (top-loop integrated out) |
| √s | 13.6 TeV |
| PDF | NN23LO1 |
| mH | 125.0 GeV |
| σ × BR | 0.00637 pb (LO) |
| Events | 100,000 |


## Prerequisites

| Tool | Notes |
|------|-------|
| MadGraph5_aMC@NLO | Set `MG5_ROOT` env var to the installation directory |
| Pythia8 | Bundled with MG5 (`HEPTools/pythia8/`) |
| Delphes | Install via `install Delphes` inside `mg5_aMC` |
| ROOT | Source the ROOT setup (e.g. `source /path/to/ROOT/bin/thisroot.sh`) |

The Delphes installation requires ROOT on `PATH`. Source the ROOT setup first:
```bash
source /path/to/ROOT/bin/thisroot.sh
```

If Delphes needs to be reinstalled:
```bash
cd "$MG5_ROOT"
echo "install Delphes" | ./bin/mg5_aMC
```
The path is configured in `input/mg5_configuration.txt`:
```
delphes_path = ./Delphes
```

---

## Project Structure

```
.
├── README.md                                      ← this file
├── run_signal.sh                                  ← full-chain driver script
├── cards/
│   ├── ggH_ZZ_4mu_proc.dat                        ← MG5 process card
│   └── ggH_ZZ_4mu_launch.txt                      ← MG5 launch script (run_card overrides)
├── scripts/
│   └── delphes_to_sknano.py                          ← Delphes → NanoAOD converter
├── condor/
│   ├── run_signal.sh                               ← HTCondor worker-node wrapper
│   ├── run_signal.sub                              ← HTCondor submit description
│   └── README.md                                   ← Condor-specific instructions
└── output/
    └── ggH_ZZ_4mu/                                 ← created by MG5 on first run
        ├── Events/run_01/
        │   ├── unweighted_events.lhe.gz
        │   ├── tag_1_pythia8_events.hepmc.gz
        │   └── tag_1_delphes_events.root           ← Delphes output
        └── nano/
            └── ggH_ZZ_4mu.root                     ← final NanoAOD-style output
```

---

## Running the Pipeline

### Full chain execution
From the repository root:
```bash
export MG5_ROOT=/path/to/MG5_aMC_v3_5_6
source /path/to/ROOT/bin/thisroot.sh
./run_signal.sh
```

The driver executes three stages:
1. **Process directory generation** (once) — runs MG5 on `cards/ggH_ZZ_4mu_proc.dat`, producing Fortran matrix element code in `output/ggH_ZZ_4mu/`.
2. **Event generation** — runs MG5 in script mode with `cards/ggH_ZZ_4mu_launch.txt`, enabling Pythia8 showering and Delphes detector simulation with `delphes_card_CMS.tcl`.
3. **NanoAOD conversion** — converts the Delphes ROOT output to a NanoAOD-compatible flat tree under `output/ggH_ZZ_4mu/nano/`.

### Step-by-step execution

Each stage can be run independently:

```bash
cd "$MG5_ROOT"
source /path/to/ROOT/bin/thisroot.sh
unset PYTHIA8DATA

# (a) Generate the process directory
./bin/mg5_aMC /path/to/repo/cards/ggH_ZZ_4mu_proc.dat

# (b) Launch event generation with Pythia8 + Delphes
./bin/mg5_aMC -f /path/to/repo/cards/ggH_ZZ_4mu_launch.txt

# (c) Convert Delphes output to NanoAOD format
python3 /path/to/repo/scripts/delphes_to_sknano.py \
    --example /path/to/example/NANOAOD.root \
    --delphes output/ggH_ZZ_4mu/Events/run_01/tag_1_delphes_events.root \
    --out     output/ggH_ZZ_4mu/nano/NANOAOD_1.root
```

### Modifying run parameters
- **Event count, beam energy, or PDF**: edit `cards/ggH_ZZ_4mu_launch.txt` (`set nevents …`, `set ebeam1 …`).
- **Physics process**: edit `cards/ggH_ZZ_4mu_proc.dat` and delete `output/ggH_ZZ_4mu/` to force MG5 to regenerate the process directory.
- **Run numbering**: each launch creates `run_01`, `run_02`, … under `output/ggH_ZZ_4mu/Events/`. The driver reads `run_01` by default; specify an explicit path to `delphes_to_sknano.py` for other runs.

### HTCondor batch submission
```bash
condor_submit condor/run_signal.sub    # submit from the repo root
```
See `condor/README.md` for monitoring and configuration details.

---

## Output Tree

The converter (`delphes_to_sknano.py`) produces a single `Events` TTree with NanoAOD-compatible branch names:

| Branch | Type | Source | Notes |
|--------|------|--------|-------|
| `run`, `luminosityBlock` | uint32 | dummy `1` | Delphes has no run/lumi concept |
| `event` | uint64 | sequential | unique within a file |
| `genWeight` | float32 | `Event.Weight[0]` | LO ggH: all positive |
| `nMuon` | uint32 | from `Muon` | per-event count |
| `Muon_pt/eta/phi/mass` | jagged float32 | `Muon.PT/Eta/Phi` + 0.10566 | sorted descending by pT |
| `Muon_charge` | jagged int32 | `Muon.Charge` | |
| `Muon_pfRelIso04_all` | jagged float32 | `Muon.IsolationVar` | Delphes cone iso ≈ NanoAOD pfRelIso |
| `Muon_dxy/dz/sip3d` | jagged float32 | **constant 0** | Delphes lacks impact parameters |
| `Muon_looseId` | jagged bool | **constant True** | Delphes lacks muon ID flags |
| `HLT_TripleMu_10_5_5_DZ` | bool | **constant True** | Delphes has no HLT simulation |
| `HLT_TripleMu_12_10_5` | bool | **constant True** | |
| `HLT_DoubleMu4_3_LowMass` | bool | **constant True** | |
| `HLT_Mu17_TrkIsoVVL_Mu8_TrkIsoVVL_DZ_Mass3p8` | bool | **constant True** | |

### Constant defaults

Several branches are filled with pass-through defaults because Delphes does not simulate the corresponding detector quantities. This ensures downstream analysis selections do not reject events on variables that cannot be modeled. For a more realistic acceptance, the constants in `scripts/delphes_to_sknano.py` can be replaced:

- `Muon_dxy/dz` → Gaussian smearing with σ ~ 50 μm
- `Muon_sip3d` → |N(0,1)| distribution
- `Muon_looseId` → `pT > 5 && |η| < 2.4` (effectively true after Delphes efficiency tables)
- HLT bits → emulate as `nMuon ≥ 3` with `pT > 5` and `≥ 2` with `pT > 10`

---

## Background Samples

The same pipeline applies to background processes. The process card is modified as follows:

| Sample | Process card key lines |
|--------|------------------------|
| `qqZZ_4mu` | `import model sm` <br> `generate p p > z z, z > mu+ mu-` |
| `DY_M50` | `import model sm` <br> `generate p p > mu+ mu-` <br> set `mmll > 50` in run_card |
| `TTto2L2Nu` | `import model sm` <br> `generate p p > t t~, (t > b mu+ vm), (t~ > b~ mu- vm~)` |

For each sample, copy `cards/ggH_ZZ_4mu_proc.dat` and `cards/ggH_ZZ_4mu_launch.txt`, modify the `generate` line and `output` directory, run the driver, and convert the Delphes output.

**Note:** Drell-Yan and tt̄ backgrounds produce four-muon final states only through jet → μ fakes, which Delphes models poorly. This is a fundamental limitation of fast detector simulation for the H → ZZ → 4μ analysis.

---

## Validation

After the pipeline completes, the following checks confirm the output is consistent:

```bash
source /path/to/ROOT/bin/thisroot.sh

# 1. Cross section (expect ~0.0064 pb)
grep -i "Cross-section" output/ggH_ZZ_4mu/Events/run_01/run_01_tag_1_banner.txt

# 2. Event count and branch structure
python3 -c "
import uproot
f = uproot.open('output/ggH_ZZ_4mu/nano/ggH_ZZ_4mu.root')
t = f['Events']
print('events:', t.num_entries)
print('branches:', len(t.keys()))
print('mean nMuon:', t['nMuon'].array().mean())
"

# 3. Four-lepton invariant mass peak (expect ~125 GeV)
python3 -c "
import uproot, awkward as ak, numpy as np, vector
vector.register_awkward()
t = uproot.open('output/ggH_ZZ_4mu/nano/ggH_ZZ_4mu.root:Events')
a = t.arrays(['Muon_pt','Muon_eta','Muon_phi','Muon_mass','nMuon'])
m = a[a.nMuon >= 4]
p = ak.zip({'pt':m.Muon_pt[:,:4],'eta':m.Muon_eta[:,:4],
            'phi':m.Muon_phi[:,:4],'mass':m.Muon_mass[:,:4]},
           with_name='Momentum4D')
m4 = (p[:,0]+p[:,1]+p[:,2]+p[:,3]).M
print('m4l mean=%.1f  median=%.1f  GeV (expect ~125)' %
      (float(ak.mean(m4)), float(np.median(ak.to_numpy(m4)))))
"
```

---

## Troubleshooting

| Symptom | Cause | Solution |
|---------|-------|----------|
| `ImportError: ROOT` or `install Delphes` fails | ROOT not on PATH | Source the ROOT setup script |
| `pythia8_path` warning at MG5 startup | Path points to wrong build | Edit `input/mg5_configuration.txt` |
| `tag_1_delphes_events.root` not produced | Shower/detector not enabled | Verify `shower=Pythia8` and `detector=Delphes` in `cards/ggH_ZZ_4mu_launch.txt` |
| Crash on `genWeight` sign | LO sample has all-positive weights | Expected behavior for LO ggH (`sum_sgn_gw == nevents`) |
| m4l peak not at 125 GeV | Incorrect Higgs mass or non-resonant process | Verify `set mh 125.0` in the launch script and `> h >` in the process card |

---

## Files Reference

| File | Description |
|------|-------------|
| `cards/ggH_ZZ_4mu_proc.dat` | MG5 process generation card |
| `cards/ggH_ZZ_4mu_launch.txt` | Runtime launch script (executed via `./bin/mg5_aMC -f`) |
| `scripts/delphes_to_sknano.py` | Delphes → NanoAOD converter (standalone: `--in / --out`) |
| `run_signal.sh` | Full-chain driver; skips process generation if `output/` exists |
| `condor/` | HTCondor batch submission files (see `condor/README.md`) |

## Author

**Siun Kim**
Department of Physics, Sungkyunkwan University
