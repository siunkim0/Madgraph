# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

**IMPORTANT: Always update this file when making structural changes to the repository (new files, new samples, changed commands, changed architecture).**

## Project Overview

MadGraph5_aMC@NLO (v3.5.6) MC sample generation pipeline for HEP physics analysis (H → ZZ → 4l at 13.6 TeV). The pipeline generates Monte Carlo event samples through four stages:

```
MadGraph5 (LHE) → Pythia8 (shower) → Delphes (CMS detector sim) → NanoAOD-style ROOT
```

## Samples

| Sample | Model | Process | Events | CMS ref xsec (pb) |
|--------|-------|---------|--------|--------------------|
| `ggH_ZZ_4mu` (signal) | heft | `g g > h > z z, z > mu+ mu-` | 100k | 0.01434 |
| `ZZto4L` | sm | `p p > z z, z > l+ l-` | 500k | 1.529 |
| `DYJetsToLL_M-50` | sm | `p p > l+ l-` (mmll>50) | 500k | 6345.99 |
| `DYJetsToLL_M-10to50` | sm | `p p > l+ l-` (10<mmll<50) | 500k | 19982.5 |
| `VBFHToZZTo4L` | sm | `p p > h j j QCD<=0, h > z z, z > l+ l-` | 250k | 0.00112 |
| `VHToNonbb` | sm | `p p > w+/w-/z h` (inclusive H decay) | 500k | 1.0132 |

Each sample has a pair of cards: `cards/<name>_proc.dat` and `cards/<name>_launch.txt`.

## Key Commands

### Run any sample
```bash
export MG5_ROOT=/path/to/MG5_aMC_v3_5_6
source /path/to/ROOT/bin/thisroot.sh
./run_sample.sh <sample_name>        # e.g. ./run_sample.sh ZZto4L
```

### Run the signal only
```bash
./run_signal.sh
```

### Run each step manually
```bash
cd "$MG5_ROOT"
# Step 1: Generate process directory (once)
./bin/mg5_aMC /path/to/repo/cards/<sample>_proc.dat
# Step 2: Event generation with shower + detector
./bin/mg5_aMC -f /path/to/repo/cards/<sample>_launch.txt
# Step 3: Convert Delphes ROOT to NanoAOD-style
python3 scripts/delphes_to_nano.py --in <delphes.root> --out <nano.root>
```

### Run tests
```bash
./tests/test_manager.py <test_name_pattern>        # Run tests matching pattern
./tests/test_manager.py -t0 test_color_basis        # Fast tests only (-t0)
./tests/test_manager.py -t0 testIO_modification_to_cuts -e test_to_skip  # Exclude specific tests with -e
```

### HTCondor batch submission
```bash
condor_submit condor/run_signal.sub   # Submit from repo root
condor_q                               # Monitor jobs
```

## Architecture

### Pipeline components

- **`cards/`** — MG5 process cards (`*_proc.dat`) define the physics process; launch scripts (`*_launch.txt`) set runtime parameters (nevents, energy, PDF, masses, shower/detector settings). One pair per sample.
- **`scripts/delphes_to_nano.py`** — Converts Delphes ROOT trees to NanoAOD-compatible flat TTrees using `uproot`/`awkward`. Fills missing Delphes info (dxy/dz/sip3d, looseId, HLT bits) with pass-through defaults
- **`run_sample.sh`** — Generic driver; takes a sample name as argument, finds the matching cards, runs the full chain. Auto-detects MG5 from `$MG5_ROOT` or `PATH`.
- **`run_signal.sh`** — Signal-only driver (ggH → ZZ → 4μ); same three-step chain hardcoded for the signal sample
- **`condor/`** — HTCondor wrappers; sources LCG view from CVMFS, must `unset PYTHIA8DATA` to avoid conflicts with MG5's bundled Pythia8

### MadGraph5 core library (`madgraph/`)

- **`core/base_objects.py`** — Physics object hierarchy (`PhysicsObject(dict)` base): `Particle`, `Interaction`, `Model`, `Process`, `Diagram`, `Leg`, `Vertex`. All use validated dict-based property access
- **`core/diagram_generation.py`** — Generates Feynman diagrams from process definitions via recursive s/t-channel topology construction
- **`core/color_algebra.py`** — Color algebra: `Tr`, `T`, `f`, `d`, `Epsilon`, `ColorString`, `ColorFactor`
- **`core/helas_objects.py`** — HELAS wavefunction/amplitude objects for matrix element computation
- **`interface/madgraph_interface.py`** — Main CLI (extends Python `cmd`): commands include `import`, `define`, `generate`, `output`, `launch`
- **`interface/madevent_interface.py`** — LO event generation interface
- **`iolibs/`** — Code export (Fortran, C++, Python) and file I/O

### Bundled tools

- **`HEPTools/pythia8/`** — Pre-built Pythia8 for shower/hadronization
- **`Delphes/`** — Fast CMS detector simulation (full source tree, compiled with ROOT)
- **`models/`** — UFO physics models: `heft/` (used for ggH signal), `sm/` (used for all backgrounds), `MSSM_SLHA2/`
- **`Template/LO/`** — Fortran/C++ templates for generated matrix element code

### Configuration

- **`input/mg5_configuration.txt`** — Main MG5 config; sets `delphes_path=./Delphes`, `pythia8_path=./HEPTools/pythia8`
- Process changes require deleting the `output/<process>/` directory so MG5 regenerates it
- Event count/energy/PDF changes only need edits to the launch card

## Important Conventions

- Process syntax: `p1 p2 > p3 p4 [, p3 > p5 p6]` with `/` for excluded particles and `$` for required intermediates
- `QCD<=0` in VBF process ensures only electroweak diagrams (VBF topology)
- Output NanoAOD trees: muons sorted descending by pT; `run`/`luminosityBlock` are dummy values
- Delphes limitations: no tracking IPs, no muon ID flags, no HLT simulation — all filled with pass-through constants in the converter
- CMS reference cross sections (NLO/NNLO) are used for luminosity normalization, not the LO values from MadGraph
- VHToNonbb generates all H decays inclusively; to exclude H→bb at generation level, modify the pythia8 card
- Adding a new sample: create `cards/<name>_proc.dat` and `cards/<name>_launch.txt`, then run `./run_sample.sh <name>`
- This repository should contain NO server-specific paths — all scripts use relative paths or environment variables
