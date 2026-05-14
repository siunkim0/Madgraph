# BDT_MC / Condor submission

Submit the full MG5 → Pythia8 → Delphes → NanoAOD-mimic chain as one
HTCondor job per sample. The job runs on a worker node (tamsa
node-g3..g10), writing directly to `/data6` (shared filesystem).

## Files

| File | Purpose |
|---|---|
| `run_signal.sub` | HTCondor submit description |
| `run_signal.sh`  | Worker-node wrapper (the actual `executable`) |
| `logs/`          | stdout/stderr/log for each job |

## Submitting

Always submit from the **MG5 root dir** (the paths in the `.sub` file
are relative to that):

```bash
cd /data6/Users/snuintern2/folder/Madgraph/MG5_aMC_v3_5_6
condor_submit BDT_MC/condor/run_signal.sub
```

You'll see something like:
```
1 job(s) submitted to cluster 12345.
```

## Monitoring

```bash
condor_q                                      # your queue
condor_q -nobatch                             # one row per job
condor_q -hold                                # see why jobs are held
condor_tail <jobid>                           # stream stdout
tail -f BDT_MC/condor/logs/signal.<ClusterId>.<ProcId>.out
```

When the job finishes, check the output:
```bash
ls -lh BDT_MC/output/ggH_ZZ_4mu/nano/
ls -lh BDT_MC/output/ggH_ZZ_4mu/Events/run_*/tag_1_delphes_events.root
```

## What the wrapper does

`run_signal.sh` (worker-side):
1. Sources LCG_105 from CVMFS → puts ROOT 6.30 on PATH.
2. **`unset PYTHIA8DATA`** — undoes the LCG env that points at Pythia
   8.310 xmldoc, which conflicts with MG5's bundled Pythia 8.316.
   Skipping this is what caused the "Histogram with run_id '0' was not
   found" crash in the interactive run.
3. Builds `output/ggH_ZZ_4mu/` if it doesn't exist.
4. Runs `mg5_aMC` with a per-job launch script (multicore, 8 cores,
   100k events, 13.6 TeV, mH=125, CMS Delphes card).
5. Picks the newest `run_NN/` and converts the Delphes ROOT to
   NanoAOD-mimic ROOT at
   `BDT_MC/output/ggH_ZZ_4mu/nano/ggH_ZZ_4mu_run_NN.root`.

The conversion-output filename includes the run tag so multiple submits
don't overwrite each other.

## Resources

The `.sub` requests:
- 8 CPUs, 8 GiB RAM, 4 GiB scratch
- Max runtime 12 h (`+RequestRuntime = 43200`)
- AlmaLinux 9 / CentOS 9 / RHEL 9 (LCG view is el9-built)

Cluster snapshot at the time this was written: node-g7..g10 had
50–60 free CPUs each, so an 8-CPU job should start instantly.

## Adding background samples

Plan, when you're ready:

1. Copy `cards/ggH_ZZ_4mu_proc.dat` → `cards/qqZZ_4mu_proc.dat`
   (change to `generate p p > z z, z > mu+ mu-`, new `output` dir).
2. Copy `condor/run_signal.sh` → `condor/run_qqZZ.sh`
   (change `PROC_DIR`, `NANO_OUT`, and the in-script launch block).
3. Copy `condor/run_signal.sub` → `condor/run_qqZZ.sub`
   (change `executable` and log file names).
4. `condor_submit BDT_MC/condor/run_qqZZ.sub`.

A more elegant refactor (one parameterized wrapper, sample name passed
as argument) is straightforward but I left it explicit here for
clarity.

## Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| Job goes **HOLD** | usually missing executable permission | `chmod +x BDT_MC/condor/run_signal.sh` |
| `ROOT not on PATH` in `.err` | LCG view not available on worker | check `/cvmfs/sft.cern.ch` mount on the chosen node; `condor_status -compact` shows nodes |
| `Histogram with run_id '0' was not found` | `PYTHIA8DATA` not unset | already handled by the wrapper; if you change the wrapper, keep the `unset PYTHIA8DATA` line |
| Job runs forever, no output | `stream_output` off | tail the `.log` for events; ensure `stream_output = True` in the `.sub` |
| `Permission denied` on `/data6/...` | path not readable by Condor user | check ACLs, `ls -la BDT_MC/condor/run_signal.sh` |
| Conversion step fails at end | `delphes_to_nano.py` needs `uproot`/`awkward` | LCG view provides these; if not, add `pip install --user uproot awkward` to the wrapper |
