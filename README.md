# BDT_MC — MadGraph MC samples for the H→ZZ→4μ BDT study

End-to-end pipeline to generate Monte Carlo samples with MadGraph5 +
Pythia8 + Delphes, and convert them to NanoAOD-mimicking ROOT files
that the [`BDT_git`](/data6/Users/snuintern2/BDT_git) project can read
without code changes.

```
MadGraph5  ─►  Pythia8  ─►  Delphes (CMS)  ─►  delphes_to_nano.py  ─►  BDT_git/src/skim.py
   LHE        showered        detector-          NanoAOD-            parquet ntuple
                              level ROOT         style ROOT          → train BDT
```

---

## 0. Prerequisites

Already done on this machine — listed for reference.

| Tool | Path | Notes |
|---|---|---|
| MadGraph5_aMC | `/data6/Users/snuintern2/folder/Madgraph/MG5_aMC_v3_5_6` | v3.5.6 |
| Pythia8 | `HEPTools/pythia8/` | bundled with MG5 |
| Delphes | `Delphes/` | installed via `install Delphes` inside `mg5_aMC` |
| ROOT | `/cvmfs/sft.cern.ch/lcg/views/LCG_105/...` | activated by your `rot` alias |
| Python pkgs | `uproot`, `awkward`, `numpy` | installed in the `ml` conda env used by `BDT_git` |

The Delphes install requires ROOT on `PATH`. Use your alias:
```bash
rot      # adds ROOT 6.30 from CVMFS to PATH
```

If Delphes ever needs to be reinstalled:
```bash
cd /data6/Users/snuintern2/folder/Madgraph/MG5_aMC_v3_5_6
rot
echo "install Delphes" | ./bin/mg5_aMC
```
The path is already enabled in `input/mg5_configuration.txt`:
```
delphes_path = ./Delphes
```

---

## 1. Directory layout

```
MC/
├── README.md                       ← this file
├── run_signal.sh                   ← one-shot driver (gen + shower + detector + convert)
├── cards/
│   ├── ggH_ZZ_4mu_proc.dat         ← MG5 process card
│   └── ggH_ZZ_4mu_launch.txt       ← MG5 launch script (run_card overrides)
├── scripts/
│   └── delphes_to_nano.py          ← Delphes → NanoAOD-mimic converter
└── output/
    └── ggH_ZZ_4mu/                 ← created by MG5 on first run
        ├── Events/run_01/
        │   ├── unweighted_events.lhe.gz
        │   ├── tag_1_pythia8_events.hepmc.gz
        │   └── tag_1_delphes_events.root      ← Delphes output
        └── nano/
            └── ggH_ZZ_4mu.root                ← what BDT_git reads
```

---

## 2. The signal sample (ggH → ZZ → 4μ)

### What it is
- Process: `g g > h > z z, z > mu+ mu-`
- Model: `heft` (top-loop integrated out, exact LO ggH)
- σ × BR ≈ **0.00637 pb** (matches `BDT_git/config/samples.yaml: ggH_ZZ_4l`)
- 13.6 TeV, NN23LO1 PDF, mH = 125.0 GeV
- 100,000 events (oversamples 17.794 fb⁻¹ by ~880×, fine for BDT training)

### Quick run
From the MG5 root dir:
```bash
cd /data6/Users/snuintern2/folder/Madgraph/MG5_aMC_v3_5_6
bash BDT_MC/run_signal.sh
```

The driver does three things:
1. **Generate process directory** (only once) — runs MG5 on
   `cards/ggH_ZZ_4mu_proc.dat`, creates Fortran code in
   `output/ggH_ZZ_4mu/`.
2. **Launch event generation** — runs MG5 in script mode with
   `cards/ggH_ZZ_4mu_launch.txt`, which enables Pythia8 + Delphes,
   sets nevents/energy/PDF/Higgs mass, and uses
   `delphes_card_CMS.tcl`.
3. **Convert** the Delphes ROOT to NanoAOD-style ROOT under
   `output/ggH_ZZ_4mu/nano/`.

### Manual (step-by-step) run

If you want to run each phase by hand:

```bash
cd /data6/Users/snuintern2/folder/Madgraph/MG5_aMC_v3_5_6
rot
unset PYTHIA8DATA
# (a) Build the process directory  (~1 minute)
./bin/mg5_aMC BDT_MC/cards/ggH_ZZ_4mu_proc.dat

# (b) Generate events  (slow — Pythia+Delphes are CPU-bound)
./bin/mg5_aMC -f BDT_MC/cards/ggH_ZZ_4mu_launch.txt

# (c) Convert Delphes → NanoAOD-mimic
python3 BDT_MC/scripts/delphes_to_nano.py \
    --in  BDT_MC/output/ggH_ZZ_4mu/Events/run_01/tag_1_delphes_events.root \
    --out BDT_MC/output/ggH_ZZ_4mu/nano/NANOAOD_1.root \
    --label 1
```

### Re-running with different settings
- **Change event count / energy / PDF**: edit
  `cards/ggH_ZZ_4mu_launch.txt` (`set nevents …`, `set ebeam1 …`).
- **Change the process**: edit `cards/ggH_ZZ_4mu_proc.dat`
  *and* delete `output/ggH_ZZ_4mu/` so MG5 regenerates the directory.
- **Different run name**: by default each launch creates `run_01`,
  `run_02`, … under `output/ggH_ZZ_4mu/Events/`. The driver script
  always reads `run_01`; pass an explicit path to
  `delphes_to_nano.py` if you want a different run.

---

## 3. The output tree (what `delphes_to_nano.py` writes)

A single `Events` TTree with these branches (mirrors NanoAOD names):

| Branch | Type | Source | Notes |
|---|---|---|---|
| `run`, `luminosityBlock` | uint32 | dummy `1` | Delphes has no concept of these |
| `event` | uint64 | sequential | unique within a file |
| `genWeight` | float32 | `Event.Weight[0]` | LO ggH ⇒ all positive |
| `nMuon` | uint32 | from `Muon` | per-event count |
| `Muon_pt/eta/phi/mass` | jagged float32 | `Muon.PT/Eta/Phi` + 0.10566 | sorted **descending** by pT |
| `Muon_charge` | jagged int32 | `Muon.Charge` | |
| `Muon_pfRelIso04_all` | jagged float32 | `Muon.IsolationVar` | Delphes cone iso ≈ NanoAOD pfRelIso |
| `Muon_dxy/dz/sip3d` | jagged float32 | **constant 0** | Delphes lacks IPs |
| `Muon_looseId` | jagged bool | **constant True** | Delphes lacks ID flags |
| `HLT_TripleMu_10_5_5_DZ` | bool | **constant True** | Delphes has no HLT |
| `HLT_TripleMu_12_10_5` | bool | **constant True** | |
| `HLT_DoubleMu4_3_LowMass` | bool | **constant True** | |
| `HLT_Mu17_TrkIsoVVL_Mu8_TrkIsoVVL_DZ_Mass3p8` | bool | **constant True** | |

**Why constant defaults?** `BDT_git/config/selection.yaml` cuts on all
of these. Setting them to "always pass" makes the BDT training run on
the full Delphes sample. If you want a more realistic acceptance,
replace the constants in `scripts/delphes_to_nano.py`:

- `Muon_dxy/dz` → smear with a Gaussian σ ~ 50 μm.
- `Muon_sip3d` → draw from |𝒩(0,1)|.
- `Muon_looseId` → `pt>5 && |eta|<2.4` (already true after Delphes muon
  efficiency table, so leaving True is OK in practice).
- HLT bits → emulate as `nMuon≥3 with pT>5 and ≥2 with pT>10`.

---

## 4. Wiring the output into `BDT_git`

Edit `BDT_git/config/samples.yaml`:

```yaml
era: "MC_2022postEE_simul"
lumi_fb: 17.794

signal:
  ggH_ZZ_4l:
    path: "/data6/Users/snuintern2/folder/Madgraph/MG5_aMC_v3_5_6/BDT_MC/output/ggH_ZZ_4mu/nano/ggH_ZZ_4mu.root"
    xsec: 0.00637
    label: 1
```

Then run the BDT pipeline:

```bash
cd /data6/Users/snuintern2/BDT_git
conda activate ml

# Phase 1 — skim
python -m src.skim --config config/samples.yaml \
                   --selection config/selection.yaml \
                   --out data/ntuples/ \
                   --only ggH_ZZ_4l

# Inspect the resulting parquet
python scripts/root_feature_stats.py data/ntuples/ggH_ZZ_4l.parquet
```

A trained BDT requires ≥1 background sample — see §6 for adding them.

---

## 5. Sanity checks

After the chain finishes, run these to confirm the sample looks right:

```bash
cd /data6/Users/snuintern2/folder/Madgraph/MG5_aMC_v3_5_6
rot

# 1. Cross-section MG reported (should be ~0.0064 pb)
grep -i "Cross-section" BDT_MC/output/ggH_ZZ_4mu/Events/run_01/run_01_tag_1_banner.txt

# 2. Number of events written
python3 -c "
import uproot
f = uproot.open('BDT_MC/output/ggH_ZZ_4mu/nano/ggH_ZZ_4mu.root')
t = f['Events']
print('events:', t.num_entries)
print('branches:', len(t.keys()))
print('mean nMuon:', t['nMuon'].array().mean())
"

# 3. m4l peak should be at 125 GeV
python3 -c "
import uproot, awkward as ak, numpy as np, vector
vector.register_awkward()
t = uproot.open('BDT_MC/output/ggH_ZZ_4mu/nano/ggH_ZZ_4mu.root:Events')
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

## 6. Adding background samples (later)

The same machinery works for backgrounds. Skeleton commands:

| Sample | proc card key lines |
|---|---|
| `qqZZ_4mu` | `import model sm` <br> `generate p p > z z, z > mu+ mu-` |
| `DY_M50` | `import model sm` <br> `generate p p > mu+ mu-` <br> set `mmll>50` in run_card |
| `TTto2L2Nu` | `import model sm` <br> `generate p p > t t~, (t > b mu+ vm), (t~ > b~ mu- vm~)` |

For each one, copy `cards/ggH_ZZ_4mu_proc.dat` and
`cards/ggH_ZZ_4mu_launch.txt`, change the `output` directory and the
`generate` line, run the same driver pattern, and convert the Delphes
ROOT.

⚠️ **DY and TTbar give 4μ only via jet→μ fakes**, which Delphes models
poorly. Expect badly-modelled fake-muon backgrounds; this is a
fundamental limitation of using Delphes for an HZZ analysis. For a
*learning* study the resulting BDT will still be educational.

---

## 7. Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| `ImportError: ROOT` or `install Delphes` fails | ROOT not on PATH | `rot` (or source CVMFS LCG view) |
| `pythia8_path` warning at MG5 startup | path points at the wrong build | edit `input/mg5_configuration.txt` |
| `tag_1_delphes_events.root` not produced | shower/detector not enabled | check `cards/ggH_ZZ_4mu_launch.txt` has `shower=Pythia8` and `detector=Delphes` |
| Skim writes 0 events | trigger or muon ID cuts rejecting everything | confirm constants in `delphes_to_nano.py` are True/0; loosen `selection.yaml` |
| BDT training crashes on `genWeight` sign | LO sample has all-positive weights | this is fine — `sum_sgn_gw == nevents` |
| m4l peak not at 125 GeV | wrong Higgs mass or a non-resonant process | check `set mh 125.0` in the launch script and `> h >` in the proc card |

---

## 8. Files reference

- `cards/ggH_ZZ_4mu_proc.dat` — process generation card
- `cards/ggH_ZZ_4mu_launch.txt` — runtime launch script (executed via
  `./bin/mg5_aMC -f`)
- `scripts/delphes_to_sknano.py` — converter, also usable standalone with
  `--in / --out / --label`
- `run_signal.sh` — wraps everything; safe to re-run (skips step 1 if
  the process directory already exists, but creates a new `run_NN/`
  every time you launch)
