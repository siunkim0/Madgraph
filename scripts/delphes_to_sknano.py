#!/usr/bin/env python3
"""delphes_to_sknano.py — Convert Delphes ROOT to full NanoAOD-compatible ROOT.

Uses CloneTree(0) from an EXAMPLE NanoAOD file to clone the exact branch
structure (1800+ branches, proper shared counters, correct types).
Then fills from Delphes where possible; everything else defaults to 0/False.

Usage:
    python3 scripts/delphes_to_sknano.py \
        --example path/to/NANOAOD_example.root \
        --delphes output/ggH_ZZ_4mu/Events/run_01/tag_1_delphes_events.root \
        --out     output/ggH_ZZ_4mu/nano/NANOAOD_1.root

All three arguments (--example, --delphes, --out) are required.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import awkward as ak
import uproot
import ROOT

# ========================= DEFAULTS =====================================
DEF_EXAMPLE = None
DEF_DELPHES = None
DEF_OUTPUT  = None

# ========================= CONSTANTS =====================================
MUON_MASS     = 0.10566   # GeV
ELECTRON_MASS = 0.000511  # GeV
MAX_ARR       = 500       # max objects per collection per event
PRINT_EVERY   = 10000     # progress print interval

# ROOT type name -> numpy dtype (Bool_t stored as uint8 for PyROOT compat)
DTYPE_MAP = {
    "Float_t":    np.float32,
    "Double_t":   np.float64,
    "Int_t":      np.int32,
    "UInt_t":     np.uint32,
    "Short_t":    np.int16,
    "UShort_t":   np.uint16,
    "Char_t":     np.int8,
    "UChar_t":    np.uint8,
    "Long64_t":   np.int64,
    "ULong64_t":  np.uint64,
    "Bool_t":     np.uint8,
}


# ========================= DELPHES READER ================================

def _flatten_jagged(arr):
    """Convert awkward jagged array to (flat_numpy, counts_numpy)."""
    counts = ak.to_numpy(ak.num(arr, axis=1)).astype(np.int32)
    flat = ak.to_numpy(ak.flatten(arr))
    offsets = np.empty(len(counts) + 1, dtype=np.int64)
    offsets[0] = 0
    np.cumsum(counts, out=offsets[1:])
    return flat, counts, offsets


def read_delphes(path: str) -> dict:
    """Read Delphes collections into flat numpy arrays for fast event access."""
    t = uproot.open(f"{path}:Delphes")
    n_evt = t.num_entries
    data: dict = {"n_events": n_evt}

    def _read(branches):
        return t.arrays(branches, library="ak")

    # --- Muon ---
    try:
        a = _read(["Muon.PT", "Muon.Eta", "Muon.Phi", "Muon.Charge",
                    "Muon.IsolationVar", "Muon.D0", "Muon.DZ"])
        # Sort by pT descending (NanoAOD convention)
        order = ak.argsort(a["Muon.PT"], axis=1, ascending=False)
        mu = {}
        for key in a.fields:
            short = key.split(".")[-1]
            mu[short] = _flatten_jagged(a[key][order])
        data["Muon"] = mu
    except Exception as e:
        print(f"  [warn] Muon read failed: {e}")

    # --- Electron ---
    try:
        a = _read(["Electron.PT", "Electron.Eta", "Electron.Phi",
                    "Electron.Charge", "Electron.IsolationVar",
                    "Electron.D0", "Electron.DZ"])
        order = ak.argsort(a["Electron.PT"], axis=1, ascending=False)
        el = {}
        for key in a.fields:
            short = key.split(".")[-1]
            el[short] = _flatten_jagged(a[key][order])
        data["Electron"] = el
    except Exception as e:
        print(f"  [warn] Electron read failed: {e}")

    # --- Photon ---
    try:
        a = _read(["Photon.PT", "Photon.Eta", "Photon.Phi", "Photon.E",
                    "Photon.IsolationVar"])
        order = ak.argsort(a["Photon.PT"], axis=1, ascending=False)
        ph = {}
        for key in a.fields:
            short = key.split(".")[-1]
            ph[short] = _flatten_jagged(a[key][order])
        data["Photon"] = ph
    except Exception as e:
        print(f"  [warn] Photon read failed: {e}")

    # --- Jet ---
    try:
        a = _read(["Jet.PT", "Jet.Eta", "Jet.Phi", "Jet.Mass",
                    "Jet.BTag", "Jet.Flavor"])
        order = ak.argsort(a["Jet.PT"], axis=1, ascending=False)
        jt = {}
        for key in a.fields:
            short = key.split(".")[-1]
            jt[short] = _flatten_jagged(a[key][order])
        data["Jet"] = jt
    except Exception as e:
        print(f"  [warn] Jet read failed: {e}")

    # --- GenPart (from Delphes Particle) ---
    try:
        a = _read(["Particle.PID", "Particle.PT", "Particle.Eta",
                    "Particle.Phi", "Particle.Mass", "Particle.Status",
                    "Particle.M1", "Particle.Charge"])
        gp = {}
        for key in a.fields:
            short = key.split(".")[-1]
            gp[short] = _flatten_jagged(a[key])
        data["GenPart"] = gp
    except Exception as e:
        print(f"  [warn] GenPart (Particle) read failed: {e}")

    # --- GenJet ---
    try:
        a = _read(["GenJet.PT", "GenJet.Eta", "GenJet.Phi", "GenJet.Mass"])
        gj = {}
        for key in a.fields:
            short = key.split(".")[-1]
            gj[short] = _flatten_jagged(a[key])
        data["GenJet"] = gj
    except Exception as e:
        print(f"  [warn] GenJet read failed: {e}")

    # --- MissingET (scalar per event, Delphes stores as 1-element array) ---
    try:
        a = _read(["MissingET.MET", "MissingET.Phi"])
        data["MET_pt"]  = ak.to_numpy(ak.firsts(a["MissingET.MET"])).astype(np.float32)
        data["MET_phi"] = ak.to_numpy(ak.firsts(a["MissingET.Phi"])).astype(np.float32)
    except Exception as e:
        print(f"  [warn] MET read failed: {e}")

    # --- GenMissingET ---
    try:
        a = _read(["GenMissingET.MET", "GenMissingET.Phi"])
        data["GenMET_pt"]  = ak.to_numpy(ak.firsts(a["GenMissingET.MET"])).astype(np.float32)
        data["GenMET_phi"] = ak.to_numpy(ak.firsts(a["GenMissingET.Phi"])).astype(np.float32)
    except Exception as e:
        print(f"  [warn] GenMET read failed: {e}")

    # --- Event weight ---
    try:
        a = _read(["Event.Weight", "Event.Number"])
        ew = ak.firsts(a["Event.Weight"])
        data["genWeight"] = ak.to_numpy(ak.fill_none(ew, 1.0)).astype(np.float32)
        en = ak.firsts(a["Event.Number"])
        data["eventNumber"] = ak.to_numpy(ak.fill_none(en, 0)).astype(np.int64)
    except Exception as e:
        print(f"  [warn] Event read failed: {e}")

    return data


# ========================= TREE SETUP ====================================

def setup_tree(example_path: str):
    """Open example NanoAOD, CloneTree(0) the Events tree.

    Returns (f_ex, t_out, buffers, branch_meta) where:
      - buffers[name] = numpy array backing the branch
      - branch_meta[name] = (kind, counter_name, dtype)
        kind is 'scalar', 'array', or 'counter'
    """
    f_ex = ROOT.TFile.Open(example_path, "READ")
    if not f_ex or f_ex.IsZombie():
        raise RuntimeError(f"Cannot open example: {example_path}")
    t_ex = f_ex.Get("Events")
    if not t_ex:
        raise RuntimeError("No 'Events' tree in example file")

    # Clone structure with 0 entries
    t_out = t_ex.CloneTree(0)
    t_out.SetDirectory(ROOT.nullptr)  # detach from example file

    buffers = {}
    branch_meta = {}
    skipped = []

    for i in range(t_out.GetNbranches()):
        br = t_out.GetListOfBranches().At(i)
        name = br.GetName()
        leaf = br.GetLeaf(name)
        if not leaf:
            skipped.append(name)
            continue

        type_name = leaf.GetTypeName()
        if type_name not in DTYPE_MAP:
            skipped.append(f"{name} ({type_name})")
            continue

        dt = DTYPE_MAP[type_name]
        count_leaf = leaf.GetLeafCount()

        if count_leaf:
            # Variable-length array
            counter = count_leaf.GetName()
            buf = np.zeros(MAX_ARR, dtype=dt)
            t_out.SetBranchAddress(name, buf)
            branch_meta[name] = ("array", counter, dt)
        else:
            # Scalar (includes counter branches like nMuon)
            buf = np.zeros(1, dtype=dt)
            t_out.SetBranchAddress(name, buf)
            branch_meta[name] = ("scalar", None, dt)

        buffers[name] = buf

    if skipped:
        print(f"  [info] skipped {len(skipped)} branches with unsupported types")

    return f_ex, t_out, buffers, branch_meta


# ========================= FILL HELPERS ==================================

def _set_buf(buffers, name, n, val):
    """Fill buffers[name][:n] with val. val can be scalar or flat array slice."""
    if name not in buffers:
        return
    buf = buffers[name]
    if n == 0:
        return
    if isinstance(val, (int, float, np.integer, np.floating)):
        buf[:n] = val
    else:
        m = min(n, len(val))
        buf[:m] = np.asarray(val[:m], dtype=buf.dtype)


def _set_scalar(buffers, name, val):
    """Set a scalar branch to val."""
    if name not in buffers:
        return
    buffers[name][0] = val


def _get_slice(coll, field, offsets, i, n):
    """Get flat slice of coll[field] for event i, length n."""
    flat, _, _ = coll[field]
    start = offsets[i]
    return flat[start:start + n]


def fill_event(i, data, buffers, branch_meta):
    """Fill all buffers for event i from Delphes data."""

    # ---- Scalars: event ID, weight ----------------------------------------
    _set_scalar(buffers, "run", 1)
    _set_scalar(buffers, "luminosityBlock", 1)
    if "eventNumber" in data:
        _set_scalar(buffers, "event", data["eventNumber"][i])
    else:
        _set_scalar(buffers, "event", i + 1)
    if "genWeight" in data:
        _set_scalar(buffers, "genWeight", data["genWeight"][i])
    else:
        _set_scalar(buffers, "genWeight", 1.0)

    # ---- HLT / L1 / Flag: all True (pass everything) ---------------------
    for name, meta in branch_meta.items():
        if meta[0] != "scalar":
            continue
        if name.startswith("HLT_") or name.startswith("L1_") or name.startswith("Flag_"):
            buffers[name][0] = 1
        elif name.startswith("L1Reco") or name.startswith("L1simulation"):
            buffers[name][0] = 1
        elif name.startswith("HLTrigger"):
            buffers[name][0] = 1

    # ---- PV (primary vertex) stub ----------------------------------------
    _set_scalar(buffers, "PV_ndof", 4.0)
    _set_scalar(buffers, "PV_x", 0.0)
    _set_scalar(buffers, "PV_y", 0.0)
    _set_scalar(buffers, "PV_z", 0.0)
    _set_scalar(buffers, "PV_chi2", 1.0)
    _set_scalar(buffers, "PV_score", 1.0)
    _set_scalar(buffers, "PV_npvs", 1)
    _set_scalar(buffers, "PV_npvsGood", 1)

    # ---- Pileup stub -----------------------------------------------------
    _set_scalar(buffers, "Pileup_nTrueInt", 0.0)
    _set_scalar(buffers, "Pileup_nPU", 0)
    _set_scalar(buffers, "Pileup_gpudensity", 0.0)
    _set_scalar(buffers, "Pileup_pudensity", 0.0)
    _set_scalar(buffers, "Pileup_sumEOOT", 0)
    _set_scalar(buffers, "Pileup_sumLOOT", 0)

    # ---- Rho stub --------------------------------------------------------
    _set_scalar(buffers, "Rho_fixedGridRhoAll", 20.0)
    _set_scalar(buffers, "Rho_fixedGridRhoFastjetAll", 20.0)
    _set_scalar(buffers, "Rho_fixedGridRhoFastjetCentral", 20.0)
    _set_scalar(buffers, "Rho_fixedGridRhoFastjetCentralCalo", 20.0)
    _set_scalar(buffers, "Rho_fixedGridRhoFastjetCentralChargedPileUp", 20.0)
    _set_scalar(buffers, "Rho_fixedGridRhoFastjetCentralNeutral", 20.0)

    # ---- MET -------------------------------------------------------------
    if "MET_pt" in data:
        _set_scalar(buffers, "MET_pt", data["MET_pt"][i])
        _set_scalar(buffers, "MET_phi", data["MET_phi"][i])
        # Copy to other MET variants
        for pfx in ("PuppiMET", "RawMET", "RawPuppiMET", "CaloMET",
                     "ChsMET", "TkMET", "DeepMETResolutionTune",
                     "DeepMETResponseTune"):
            _set_scalar(buffers, f"{pfx}_pt", data["MET_pt"][i])
            _set_scalar(buffers, f"{pfx}_phi", data["MET_phi"][i])
    if "GenMET_pt" in data:
        _set_scalar(buffers, "GenMET_pt", data["GenMET_pt"][i])
        _set_scalar(buffers, "GenMET_phi", data["GenMET_phi"][i])

    # ---- Generator stub --------------------------------------------------
    _set_scalar(buffers, "Generator_weight", data.get("genWeight", np.ones(1))[i]
                if "genWeight" in data else 1.0)
    _set_scalar(buffers, "Generator_scalePDF", 125.0)
    _set_scalar(buffers, "Generator_x1", 0.01)
    _set_scalar(buffers, "Generator_x2", 0.01)
    _set_scalar(buffers, "Generator_id1", 21)  # gluon
    _set_scalar(buffers, "Generator_id2", 21)

    # ---- LHE stub --------------------------------------------------------
    _set_scalar(buffers, "LHEWeight_originalXWGTUP", 1.0)
    _set_scalar(buffers, "LHE_HT", 0.0)
    _set_scalar(buffers, "LHE_Vpt", 0.0)

    # ---- HTXS stub (Higgs template xsec) ---------------------------------
    _set_scalar(buffers, "HTXS_stage_0", 0)
    _set_scalar(buffers, "HTXS_stage_1_pTjet30", 0)
    _set_scalar(buffers, "HTXS_stage1_2_cat_pTjet30GeV", 0)
    _set_scalar(buffers, "HTXS_Higgs_pt", 0.0)
    _set_scalar(buffers, "HTXS_Higgs_y", 0.0)
    _set_scalar(buffers, "HTXS_njets30", 0)

    # ====== COLLECTIONS (jagged) ==========================================

    # ---- Muon ------------------------------------------------------------
    mu = data.get("Muon")
    if mu:
        _, counts, offsets = mu["PT"]
        n = min(int(counts[i]), MAX_ARR)
    else:
        n = 0
    _set_scalar(buffers, "nMuon", n)

    if n > 0:
        o = offsets[i]
        pt  = mu["PT"][0][o:o+n]
        eta = mu["Eta"][0][o:o+n]
        phi = mu["Phi"][0][o:o+n]
        chg = mu["Charge"][0][o:o+n]
        iso = mu["IsolationVar"][0][o:o+n]
        d0  = mu["D0"][0][o:o+n]
        dz  = mu["DZ"][0][o:o+n]

        _set_buf(buffers, "Muon_pt", n, pt)
        _set_buf(buffers, "Muon_eta", n, eta)
        _set_buf(buffers, "Muon_phi", n, phi)
        _set_buf(buffers, "Muon_mass", n, MUON_MASS)
        _set_buf(buffers, "Muon_charge", n, chg)
        _set_buf(buffers, "Muon_pdgId", n,
                 np.where(chg > 0, -13, 13).astype(np.int32))
        _set_buf(buffers, "Muon_pfRelIso04_all", n, iso)
        _set_buf(buffers, "Muon_pfRelIso03_all", n, iso)
        _set_buf(buffers, "Muon_pfRelIso03_chg", n, iso * 0.7)
        _set_buf(buffers, "Muon_miniPFRelIso_all", n, iso * 0.5)
        _set_buf(buffers, "Muon_miniPFRelIso_chg", n, iso * 0.3)
        _set_buf(buffers, "Muon_tkRelIso", n, iso * 0.5)
        _set_buf(buffers, "Muon_jetRelIso", n, 0.0)
        _set_buf(buffers, "Muon_jetPtRelv2", n, 0.0)
        _set_buf(buffers, "Muon_dxy", n, d0)
        _set_buf(buffers, "Muon_dz", n, dz)
        _set_buf(buffers, "Muon_dxybs", n, d0)
        _set_buf(buffers, "Muon_dxyErr", n, 0.001)
        _set_buf(buffers, "Muon_dzErr", n, 0.001)
        _set_buf(buffers, "Muon_ip3d", n, np.abs(d0))
        _set_buf(buffers, "Muon_sip3d", n,
                 np.abs(d0) / np.maximum(np.float32(0.001), np.float32(0.001)))
        _set_buf(buffers, "Muon_ptErr", n, pt * 0.01)
        _set_buf(buffers, "Muon_segmentComp", n, 0.9)
        _set_buf(buffers, "Muon_nTrackerLayers", n, 10)
        _set_buf(buffers, "Muon_nStations", n, 2)
        _set_buf(buffers, "Muon_tightCharge", n, 2)
        _set_buf(buffers, "Muon_tunepRelPt", n, 1.0)
        _set_buf(buffers, "Muon_bsConstrainedPt", n, pt)
        _set_buf(buffers, "Muon_bsConstrainedPtErr", n, pt * 0.01)
        _set_buf(buffers, "Muon_bsConstrainedChi2", n, 1.0)
        # Boolean IDs: all True (pass everything)
        for bid in ("looseId", "mediumId", "mediumPromptId", "tightId",
                     "softId", "softMvaId", "triggerIdLoose",
                     "highPurity", "inTimeMuon",
                     "isGlobal", "isTracker", "isStandalone", "isPFcand"):
            _set_buf(buffers, f"Muon_{bid}", n, 1)
        # Working-point IDs (uint8)
        _set_buf(buffers, "Muon_highPtId", n, 2)
        _set_buf(buffers, "Muon_miniIsoId", n, 4)
        _set_buf(buffers, "Muon_multiIsoId", n, 2)
        _set_buf(buffers, "Muon_pfIsoId", n, 4)
        _set_buf(buffers, "Muon_puppiIsoId", n, 4)
        _set_buf(buffers, "Muon_tkIsoId", n, 2)
        _set_buf(buffers, "Muon_mvaMuID_WP", n, 2)
        # MVA scores
        _set_buf(buffers, "Muon_mvaMuID", n, 0.9)
        _set_buf(buffers, "Muon_softMva", n, 0.9)
        _set_buf(buffers, "Muon_mvaLowPt", n, 5.0)
        _set_buf(buffers, "Muon_mvaTTH", n, 0.5)
        # Gen matching stubs
        _set_buf(buffers, "Muon_genPartFlav", n, 1)   # prompt muon
        _set_buf(buffers, "Muon_genPartIdx", n, -1)
        _set_buf(buffers, "Muon_jetIdx", n, -1)
        _set_buf(buffers, "Muon_fsrPhotonIdx", n, -1)
        _set_buf(buffers, "Muon_svIdx", n, -1)
        _set_buf(buffers, "Muon_jetNDauCharged", n, 0)

    # ---- Electron --------------------------------------------------------
    el = data.get("Electron")
    if el:
        _, counts_e, offsets_e = el["PT"]
        ne = min(int(counts_e[i]), MAX_ARR)
    else:
        ne = 0
    _set_scalar(buffers, "nElectron", ne)

    if ne > 0:
        o = offsets_e[i]
        pt  = el["PT"][0][o:o+ne]
        eta = el["Eta"][0][o:o+ne]
        phi = el["Phi"][0][o:o+ne]
        chg = el["Charge"][0][o:o+ne]
        iso = el["IsolationVar"][0][o:o+ne]
        d0  = el["D0"][0][o:o+ne]
        dz  = el["DZ"][0][o:o+ne]

        _set_buf(buffers, "Electron_pt", ne, pt)
        _set_buf(buffers, "Electron_eta", ne, eta)
        _set_buf(buffers, "Electron_phi", ne, phi)
        _set_buf(buffers, "Electron_mass", ne, ELECTRON_MASS)
        _set_buf(buffers, "Electron_charge", ne, chg)
        _set_buf(buffers, "Electron_pdgId", ne,
                 np.where(chg > 0, -11, 11).astype(np.int32))
        _set_buf(buffers, "Electron_pfRelIso03_all", ne, iso)
        _set_buf(buffers, "Electron_miniPFRelIso_all", ne, iso * 0.5)
        _set_buf(buffers, "Electron_miniPFRelIso_chg", ne, iso * 0.3)
        _set_buf(buffers, "Electron_dxy", ne, d0)
        _set_buf(buffers, "Electron_dz", ne, dz)
        _set_buf(buffers, "Electron_dxyErr", ne, 0.001)
        _set_buf(buffers, "Electron_dzErr", ne, 0.001)
        _set_buf(buffers, "Electron_ip3d", ne, np.abs(d0))
        _set_buf(buffers, "Electron_sip3d", ne, 0.0)
        # Electron IDs: all passing
        for eid in ("mvaIso_WP80", "mvaIso_WP90", "mvaNoIso_WP80",
                     "mvaNoIso_WP90", "cutBased_HEEP",
                     "isPFcand", "convVeto"):
            _set_buf(buffers, f"Electron_{eid}", ne, 1)
        _set_buf(buffers, "Electron_cutBased", ne, 4)  # tight
        _set_buf(buffers, "Electron_genPartFlav", ne, 1)
        _set_buf(buffers, "Electron_genPartIdx", ne, -1)
        _set_buf(buffers, "Electron_jetIdx", ne, -1)
        _set_buf(buffers, "Electron_photonIdx", ne, -1)
        _set_buf(buffers, "Electron_svIdx", ne, -1)
        _set_buf(buffers, "Electron_tightCharge", ne, 2)
        _set_buf(buffers, "Electron_lostHits", ne, 0)
        _set_buf(buffers, "Electron_seedGain", ne, 1)
        _set_buf(buffers, "Electron_mvaIso", ne, 0.9)
        _set_buf(buffers, "Electron_mvaNoIso", ne, 0.9)
        _set_buf(buffers, "Electron_mvaTTH", ne, 0.5)
        _set_buf(buffers, "Electron_r9", ne, 0.9)
        _set_buf(buffers, "Electron_energyErr", ne, pt * 0.01)
        _set_buf(buffers, "Electron_eCorr", ne, 1.0)
        _set_buf(buffers, "Electron_scEtOverPt", ne, 0.0)
        _set_buf(buffers, "Electron_deltaEtaSC", ne, 0.0)
        _set_buf(buffers, "Electron_hoe", ne, 0.01)
        _set_buf(buffers, "Electron_eInvMinusPInv", ne, 0.0)
        _set_buf(buffers, "Electron_sieie", ne, 0.01)
        _set_buf(buffers, "Electron_jetRelIso", ne, 0.0)
        _set_buf(buffers, "Electron_jetPtRelv2", ne, 0.0)
        _set_buf(buffers, "Electron_pfRelIso03_chg", ne, iso * 0.7)

    # ---- Photon ----------------------------------------------------------
    ph = data.get("Photon")
    if ph:
        _, counts_p, offsets_p = ph["PT"]
        nph = min(int(counts_p[i]), MAX_ARR)
    else:
        nph = 0
    _set_scalar(buffers, "nPhoton", nph)

    if nph > 0:
        o = offsets_p[i]
        pt  = ph["PT"][0][o:o+nph]
        eta = ph["Eta"][0][o:o+nph]
        phi = ph["Phi"][0][o:o+nph]
        iso = ph["IsolationVar"][0][o:o+nph]

        _set_buf(buffers, "Photon_pt", nph, pt)
        _set_buf(buffers, "Photon_eta", nph, eta)
        _set_buf(buffers, "Photon_phi", nph, phi)
        _set_buf(buffers, "Photon_mass", nph, 0.0)
        _set_buf(buffers, "Photon_pfRelIso03_all", nph, iso)
        _set_buf(buffers, "Photon_pfRelIso03_chg", nph, iso * 0.7)
        _set_buf(buffers, "Photon_r9", nph, 0.9)
        _set_buf(buffers, "Photon_hoe", nph, 0.01)
        _set_buf(buffers, "Photon_sieie", nph, 0.01)
        _set_buf(buffers, "Photon_mvaID", nph, 0.9)
        _set_buf(buffers, "Photon_cutBased", nph, 3)
        _set_buf(buffers, "Photon_electronVeto", nph, 1)
        _set_buf(buffers, "Photon_pixelSeed", nph, 0)
        _set_buf(buffers, "Photon_isScEtaEB", nph, 1)
        _set_buf(buffers, "Photon_isScEtaEE", nph, 0)
        _set_buf(buffers, "Photon_genPartFlav", nph, 1)
        _set_buf(buffers, "Photon_genPartIdx", nph, -1)
        _set_buf(buffers, "Photon_jetIdx", nph, -1)
        _set_buf(buffers, "Photon_energyErr", nph, pt * 0.01)
        _set_buf(buffers, "Photon_energyRaw", nph, pt)
        _set_buf(buffers, "Photon_eCorr", nph, 1.0)
        _set_buf(buffers, "Photon_pdgId", nph, 22)

    # ---- Jet -------------------------------------------------------------
    jt = data.get("Jet")
    if jt:
        _, counts_j, offsets_j = jt["PT"]
        nj = min(int(counts_j[i]), MAX_ARR)
    else:
        nj = 0
    _set_scalar(buffers, "nJet", nj)

    if nj > 0:
        o = offsets_j[i]
        pt   = jt["PT"][0][o:o+nj]
        eta  = jt["Eta"][0][o:o+nj]
        phi  = jt["Phi"][0][o:o+nj]
        mass = jt["Mass"][0][o:o+nj]
        btag = jt["BTag"][0][o:o+nj]

        _set_buf(buffers, "Jet_pt", nj, pt)
        _set_buf(buffers, "Jet_eta", nj, eta)
        _set_buf(buffers, "Jet_phi", nj, phi)
        _set_buf(buffers, "Jet_mass", nj, mass)
        _set_buf(buffers, "Jet_btagDeepFlavB", nj,
                 np.where(btag > 0, 0.9, 0.01))
        _set_buf(buffers, "Jet_btagPNetB", nj,
                 np.where(btag > 0, 0.9, 0.01))
        _set_buf(buffers, "Jet_jetId", nj, 7)
        _set_buf(buffers, "Jet_nConstituents", nj, 10)
        _set_buf(buffers, "Jet_area", nj, 0.5)
        _set_buf(buffers, "Jet_hadronFlavour", nj, 0)
        _set_buf(buffers, "Jet_partonFlavour", nj, 0)
        if "Flavor" in jt:
            flav = jt["Flavor"][0][o:o+nj]
            _set_buf(buffers, "Jet_hadronFlavour", nj, np.abs(flav))
            _set_buf(buffers, "Jet_partonFlavour", nj, flav)
        _set_buf(buffers, "Jet_genJetIdx", nj, -1)
        _set_buf(buffers, "Jet_muonIdx1", nj, -1)
        _set_buf(buffers, "Jet_muonIdx2", nj, -1)
        _set_buf(buffers, "Jet_electronIdx1", nj, -1)
        _set_buf(buffers, "Jet_electronIdx2", nj, -1)
        _set_buf(buffers, "Jet_svIdx1", nj, -1)
        _set_buf(buffers, "Jet_svIdx2", nj, -1)
        _set_buf(buffers, "Jet_nMuons", nj, 0)
        _set_buf(buffers, "Jet_nElectrons", nj, 0)
        _set_buf(buffers, "Jet_chEmEF", nj, 0.1)
        _set_buf(buffers, "Jet_chHEF", nj, 0.5)
        _set_buf(buffers, "Jet_neEmEF", nj, 0.1)
        _set_buf(buffers, "Jet_neHEF", nj, 0.2)
        _set_buf(buffers, "Jet_muEF", nj, 0.0)
        _set_buf(buffers, "Jet_rawFactor", nj, 0.0)

    # ---- GenPart (from Delphes Particle) ---------------------------------
    gp = data.get("GenPart")
    if gp:
        _, counts_g, offsets_g = gp["PID"]
        ng = min(int(counts_g[i]), MAX_ARR)
    else:
        ng = 0
    _set_scalar(buffers, "nGenPart", ng)

    if ng > 0:
        o = offsets_g[i]
        _set_buf(buffers, "GenPart_pt", ng, gp["PT"][0][o:o+ng])
        _set_buf(buffers, "GenPart_eta", ng, gp["Eta"][0][o:o+ng])
        _set_buf(buffers, "GenPart_phi", ng, gp["Phi"][0][o:o+ng])
        _set_buf(buffers, "GenPart_mass", ng, gp["Mass"][0][o:o+ng])
        _set_buf(buffers, "GenPart_pdgId", ng, gp["PID"][0][o:o+ng])
        _set_buf(buffers, "GenPart_status", ng, gp["Status"][0][o:o+ng])
        # Mother index: Delphes M1 is absolute index within the event
        m1 = gp["M1"][0][o:o+ng].astype(np.int16)
        # Clamp to valid range for this event
        m1 = np.where((m1 >= 0) & (m1 < ng), m1, -1).astype(np.int16)
        _set_buf(buffers, "GenPart_genPartIdxMother", ng, m1)
        # statusFlags: set isLastCopy for status==1 particles, isPrompt
        # bit 0 = isPrompt, bit 12 = isLastCopy, bit 13 = isLastCopyBeforeFSR
        status = gp["Status"][0][o:o+ng].astype(np.int32)
        flags = np.where(status == 1,
                         (1 << 0) | (1 << 12),   # isPrompt | isLastCopy
                         (1 << 0)).astype(np.uint16)
        _set_buf(buffers, "GenPart_statusFlags", ng, flags)

    # ---- GenJet ----------------------------------------------------------
    gj = data.get("GenJet")
    if gj:
        _, counts_gj, offsets_gj = gj["PT"]
        ngj = min(int(counts_gj[i]), MAX_ARR)
    else:
        ngj = 0
    _set_scalar(buffers, "nGenJet", ngj)
    if ngj > 0:
        o = offsets_gj[i]
        _set_buf(buffers, "GenJet_pt", ngj, gj["PT"][0][o:o+ngj])
        _set_buf(buffers, "GenJet_eta", ngj, gj["Eta"][0][o:o+ngj])
        _set_buf(buffers, "GenJet_phi", ngj, gj["Phi"][0][o:o+ngj])
        _set_buf(buffers, "GenJet_mass", ngj, gj["Mass"][0][o:o+ngj])
        _set_buf(buffers, "GenJet_hadFlavour", ngj, 0)
        _set_buf(buffers, "GenJet_partonFlavour", ngj, 0)

    # ---- Empty collections (0 per event) ---------------------------------
    for counter_name in ("nFatJet", "nSubJet", "nTau", "nboostedTau",
                         "nSV", "nTrigObj", "nIsoTrack", "nFsrPhoton",
                         "nCorrT1METJet", "nGenDressedLepton",
                         "nGenIsolatedPhoton", "nGenJetAK8",
                         "nGenVisTau", "nLowPtElectron", "nOtherPV",
                         "nSubGenJetAK8", "nLHEPart", "nTauProd",
                         "nGenProton"):
        _set_scalar(buffers, counter_name, 0)

    # ---- LHE/PS weights (1-element arrays with value 1.0) ----------------
    _set_scalar(buffers, "nLHEPdfWeight", 1)
    _set_buf(buffers, "LHEPdfWeight", 1, 1.0)
    _set_scalar(buffers, "nLHEScaleWeight", 1)
    _set_buf(buffers, "LHEScaleWeight", 1, 1.0)
    _set_scalar(buffers, "nLHEReweightingWeight", 0)
    _set_scalar(buffers, "nPSWeight", 1)
    _set_buf(buffers, "PSWeight", 1, 1.0)

    # ---- GenVtx ----------------------------------------------------------
    _set_scalar(buffers, "GenVtx_x", 0.0)
    _set_scalar(buffers, "GenVtx_y", 0.0)
    _set_scalar(buffers, "GenVtx_z", 0.0)
    _set_scalar(buffers, "GenVtx_t0", 0.0)

    # ---- bunchCrossing ---------------------------------------------------
    _set_scalar(buffers, "bunchCrossing", 0)

    # ---- genTtbarId ------------------------------------------------------
    _set_scalar(buffers, "genTtbarId", 0)


# ========================= RUNS TREE =====================================

def write_runs_tree(f_out, n_events, sum_weights, f_ex):
    """Write a Runs tree for mcreader.py compatibility."""
    # Try cloning from example
    t_runs_ex = f_ex.Get("Runs")
    if t_runs_ex:
        f_out.cd()
        t_runs = t_runs_ex.CloneTree(0)
    else:
        f_out.cd()
        t_runs = ROOT.TTree("Runs", "Runs")

    # Create our own branches
    genEventCount = np.zeros(1, dtype=np.uint64)
    genEventSumw  = np.zeros(1, dtype=np.float64)

    # Check if branches already exist from clone
    if not t_runs.GetBranch("genEventCount"):
        t_runs.Branch("genEventCount", genEventCount, "genEventCount/l")
    else:
        t_runs.SetBranchAddress("genEventCount", genEventCount)

    if not t_runs.GetBranch("genEventSumw"):
        t_runs.Branch("genEventSumw", genEventSumw, "genEventSumw/D")
    else:
        t_runs.SetBranchAddress("genEventSumw", genEventSumw)

    genEventCount[0] = n_events
    genEventSumw[0]  = sum_weights

    t_runs.Fill()
    t_runs.Write()


# ========================= MAIN ==========================================

def main() -> int:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--example", required=True,
                   help="example NanoAOD to clone structure from")
    p.add_argument("--delphes", required=True,
                   help="Delphes ROOT input file")
    p.add_argument("--out", required=True,
                   help="output NanoAOD-style ROOT file")
    args = p.parse_args()

    Path(args.out).parent.mkdir(parents=True, exist_ok=True)

    # 1. Read Delphes data into memory
    print(f"[1/4] Reading Delphes: {args.delphes}")
    data = read_delphes(args.delphes)
    n_evt = data["n_events"]
    print(f"       {n_evt} events")

    # 2. Clone tree structure from example
    print(f"[2/4] Cloning structure from: {args.example}")
    f_ex, t_out, buffers, branch_meta = setup_tree(args.example)
    print(f"       {len(buffers)} branches set up")

    # 3. Open output file
    f_out = ROOT.TFile.Open(args.out, "RECREATE")
    f_out.cd()
    t_out.SetDirectory(f_out)

    # 4. Event loop
    print(f"[3/4] Filling {n_evt} events ...")
    sum_w = 0.0
    for i in range(n_evt):
        # Zero all array buffers (scalar buffers keep their value from
        # previous iteration unless explicitly overwritten, which is fine
        # for branches that don't change; but array tails must be clean).
        for name, meta in branch_meta.items():
            if meta[0] == "array":
                buffers[name][:] = 0

        fill_event(i, data, buffers, branch_meta)

        if "genWeight" in data:
            sum_w += float(data["genWeight"][i])
        else:
            sum_w += 1.0

        t_out.Fill()

        if (i + 1) % PRINT_EVERY == 0:
            print(f"       {i+1}/{n_evt}")

    # 5. Write
    print(f"[4/4] Writing {args.out}")
    t_out.Write()

    write_runs_tree(f_out, n_evt, sum_w, f_ex)

    f_out.Close()
    f_ex.Close()

    print(f"Done. {n_evt} events, {len(buffers)} branches.")
    print(f"  sum(genWeight) = {sum_w:.6f}")
    print(f"  output: {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
