#!/usr/bin/env python3
"""Convert Delphes ROOT output -> NanoAOD-mimicking flat tree.

Produces a TTree named "Events" with NanoAOD-compatible branches:

    run, luminosityBlock, event, genWeight,
    nMuon,
    Muon_pt, Muon_eta, Muon_phi, Muon_mass, Muon_charge,
    Muon_pfRelIso04_all,
    Muon_dxy, Muon_dz, Muon_sip3d,
    Muon_looseId,
    HLT_TripleMu_10_5_5_DZ, HLT_TripleMu_12_10_5,
    HLT_DoubleMu4_3_LowMass, HLT_Mu17_TrkIsoVVL_Mu8_TrkIsoVVL_DZ_Mass3p8

Delphes lacks dxy/dz/sip3d/looseId/HLT bits, so those are filled with
benign defaults (0 for IPs, True for ID/triggers). Downstream analysis
cuts on these will then pass automatically; if you want them to do real
work, replace the constants with a more realistic emulation.

Muons inside each event are sorted by pT (matches NanoAOD convention).

Usage:
    python delphes_to_nano.py \\
        --in  output/ggH_ZZ_4mu/Events/run_01/tag_1_delphes_events.root \\
        --out output/ggH_ZZ_4mu/nano/ggH_ZZ_4mu.root

Requires: uproot, awkward, numpy. (No PyROOT needed for writing.)
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import awkward as ak
import numpy as np
import uproot


# Branches written to the output tree. Order matches NanoAOD where it matters.
HLT_PATHS = [
    "HLT_TripleMu_10_5_5_DZ",
    "HLT_TripleMu_12_10_5",
    "HLT_DoubleMu4_3_LowMass",
    "HLT_Mu17_TrkIsoVVL_Mu8_TrkIsoVVL_DZ_Mass3p8",
]


def convert(in_path: str, out_path: str, label: int = 1,
            xsec_pb: float | None = None) -> None:
    Path(out_path).parent.mkdir(parents=True, exist_ok=True)

    f = uproot.open(in_path)
    if "Delphes" not in f:
        raise RuntimeError(f"No 'Delphes' tree in {in_path}; keys={f.keys()}")
    t = f["Delphes"]

    # Read Muon collection + event weight.
    arrs = t.arrays([
        "Muon.PT", "Muon.Eta", "Muon.Phi",
        "Muon.Charge", "Muon.IsolationVar",
        "Event.Weight",
    ], library="ak")

    pt   = arrs["Muon.PT"]
    eta  = arrs["Muon.Eta"]
    phi  = arrs["Muon.Phi"]
    chg  = arrs["Muon.Charge"]
    iso  = arrs["Muon.IsolationVar"]

    # Sort each event's muons by pT desc (NanoAOD convention).
    order = ak.argsort(pt, axis=1, ascending=False)
    pt   = pt[order]
    eta  = eta[order]
    phi  = phi[order]
    chg  = chg[order]
    iso  = iso[order]

    n_evt = len(pt)
    nmu   = ak.num(pt, axis=1)

    # Constant muon mass (PDG, GeV).
    mass = ak.full_like(pt, 0.10566, dtype=np.float32)

    # Fields Delphes does not provide -> safe defaults.
    dxy = ak.zeros_like(pt, dtype=np.float32)
    dz  = ak.zeros_like(pt, dtype=np.float32)
    sip = ak.zeros_like(pt, dtype=np.float32)
    # Muon_looseId is a bool branch in NanoAOD; we use uint8 (0/1) which uproot
    # writes as a branch readable as a boolean array.
    looseId = ak.values_astype(ak.ones_like(pt, dtype=np.int8), np.bool_)

    # genWeight: take Event.Weight[0] per event (Delphes stores one entry).
    ew = arrs["Event.Weight"]
    # Event.Weight may be a jagged array; flatten the first slot per event.
    ew_first = ak.firsts(ew, axis=1)
    ew_first = ak.fill_none(ew_first, 1.0)
    gw = ak.values_astype(ew_first, np.float32)

    # Bookkeeping branches.
    run    = ak.Array(np.ones(n_evt, dtype=np.uint32))
    lumi   = ak.Array(np.ones(n_evt, dtype=np.uint32))
    event  = ak.Array(np.arange(1, n_evt + 1, dtype=np.uint64))

    # Trigger bits: all True (Delphes has no HLT). The BDT trigger OR will
    # therefore pass for every event. If you want realistic trigger losses,
    # replace this with a pT/multiplicity emulation.
    trig_true = ak.Array(np.ones(n_evt, dtype=np.bool_))

    # xsec_weight is computed downstream by skim.py from xsec*lumi/sum_sgn_gw,
    # so we don't add it here. We DO write a constant 'genWeight' = +1 by
    # default (positive weights); replace with Delphes Event.Weight if you want
    # NLO-style negative weights. ggH at LO has all positive weights anyway.
    out = {
        "run": run,
        "luminosityBlock": lumi,
        "event": event,
        "genWeight": gw,
        "nMuon": ak.values_astype(nmu, np.uint32),
        "Muon_pt":   ak.values_astype(pt,  np.float32),
        "Muon_eta":  ak.values_astype(eta, np.float32),
        "Muon_phi":  ak.values_astype(phi, np.float32),
        "Muon_mass": mass,
        "Muon_charge":         ak.values_astype(chg, np.int32),
        "Muon_pfRelIso04_all": ak.values_astype(iso, np.float32),
        "Muon_dxy":     dxy,
        "Muon_dz":      dz,
        "Muon_sip3d":   sip,
        "Muon_looseId": looseId,
    }
    for h in HLT_PATHS:
        out[h] = trig_true

    with uproot.recreate(out_path) as fout:
        fout["Events"] = out

    print(f"[delphes_to_nano] {in_path}")
    print(f"  -> {out_path}")
    print(f"  events written: {n_evt}")
    print(f"  branches: {len(out)}  (sample mu mult <n>={float(ak.mean(nmu)):.2f})")


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--in",  dest="in_path",  required=True,
                   help="Delphes ROOT file (tag_1_delphes_events.root)")
    p.add_argument("--out", dest="out_path", required=True,
                   help="Output NanoAOD-style ROOT file")
    p.add_argument("--label", type=int, default=1,
                   help="Class label (1=signal, 0=bkg). Currently unused; "
                        "skim.py reads label from samples.yaml.")
    args = p.parse_args()
    convert(args.in_path, args.out_path, label=args.label)


if __name__ == "__main__":
    main()
