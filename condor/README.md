# Condor submission

Submit the full MG5 → Pythia8 → Delphes → NanoAOD-mimic chain as one
HTCondor job per sample. The job runs on a worker node, writing
directly to the shared filesystem.

## Files

| File | Purpose |
|---|---|
| `run_signal.sub` | HTCondor submit description |
| `run_signal.sh`  | Worker-node wrapper (the actual `executable`) |
| `logs/`          | stdout/stderr/log for each job |

## Submitting

Always submit from the **repo root** (the paths in the `.sub` file
are relative to that):

```bash
cd /path/to/this/repo
condor_submit condor/run_signal.sub
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
tail -f condor/logs/signal.<ClusterId>.<ProcId>.out
```

When the job finishes, check the output:
```bash
ls -lh output/ggH_ZZ_4mu/nano/
ls -lh output/ggH_ZZ_4mu/Events/run_*/tag_1_delphes_events.root
```

## What the wrapper does

`run_signal.sh` (worker-side):
1. Sources an LCG view from CVMFS → puts ROOT on PATH.
2. **`unset PYTHIA8DATA`** — undoes the LCG env that points at a
   different Pythia xmldoc version, which can conflict with MG5's
   bundled Pythia. Skipping this can cause "Histogram with run_id '0'
   was not found" errors.
3. Builds `output/ggH_ZZ_4mu/` if it doesn't exist.
4. Runs `mg5_aMC` with a per-job launch script (multicore, 8 cores,
   100k events, 13.6 TeV, mH=125, CMS Delphes card).
5. Picks the newest `run_NN/` and converts the Delphes ROOT to
   NanoAOD-mimic ROOT at
   `output/ggH_ZZ_4mu/nano/ggH_ZZ_4mu_run_NN.root`.

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
4. `condor_submit condor/run_qqZZ.sub`.

A more elegant refactor (one parameterized wrapper, sample name passed
as argument) is straightforward but I left it explicit here for
clarity.

## Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| Job goes **HOLD** | usually missing executable permission | `chmod +x condor/run_signal.sh` |
| `ROOT not on PATH` in `.err` | LCG view not available on worker | check CVMFS mount on the chosen node; `condor_status -compact` shows nodes |
| `Histogram with run_id '0' was not found` | `PYTHIA8DATA` not unset | already handled by the wrapper; if you change the wrapper, keep the `unset PYTHIA8DATA` line |
| Job runs forever, no output | `stream_output` off | tail the `.log` for events; ensure `stream_output = True` in the `.sub` |
| `Permission denied` | path not readable by Condor user | check ACLs, `ls -la condor/run_signal.sh` |
| Conversion step fails at end | `delphes_to_nano.py` needs `uproot`/`awkward` | LCG view provides these; if not, add `pip install --user uproot awkward` to the wrapper |
