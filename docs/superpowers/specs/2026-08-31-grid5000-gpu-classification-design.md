# Grid’5000 GPU relevance classification

## Goal

Run the existing LFM sentence classifier on one reserved Grid’5000 GPU node
without putting model memory or swap pressure on the MacBook, then combine the
returned labels with the Seagate-hosted sentence table and replace the
Hugging Face Viewer artifact.

## Design

The local runner reads only the `sentence` column from the Seagate segmented
Parquet file and writes a deterministic gzip-compressed JSON payload under the
same run directory. Each payload item contains its source row index and
sentence; page text, URLs, and polygon metadata are not transferred because
the model does not need them. The runner uploads that payload and a checked-out
worker to a uniquely named Grid’5000 run directory, runs the worker through one
OAR reservation on the Nantes `gpu=1` resource, polls the job, downloads the
validated labels, and materializes the complete and yes-only Parquet tables
locally.

The worker uses the repository’s existing prompt, left-padded LFM chat
template, final-token yes/no comparison, and `LiquidAI/LFM2.5-2.6B` model. It
uses `uv` and the CUDA toolkit on the reserved node, stores the model cache in
node-local `/tmp`, writes a checkpoint after every classification batch, and
removes that exact cache on successful completion. The remote `/home` run
directory is retained until the labels and logs have been copied and
validated, then removed as project-owned temporary state.

The frontend performs only policy checks, repository checkout, file transfer,
submission, status polling, and result retrieval. It never loads the model.
`usagepolicycheck -t` runs before submission and after the job reaches a
terminal state. A nonzero policy-check result, missing `No jobs flagged`
confirmation, unexpected OAR state, incomplete checkpoint, malformed label, or
row-count mismatch fails the run.

## Boundaries and safety

- The default site is `nantes`; the default request is exactly one host, one
  GPU, and a 30-minute walltime.
- Remote run identifiers are derived from the payload hash, so rerunning the
  same input and code refuses to submit a duplicate job while an existing run
  directory is present.
- No credential is embedded in code, scripts, payloads, logs, or commits.
- The local data-root guard rejects every input/output path outside
  `/Volumes/Seagate M3/projects/osm-polygon-web-search`.
- The HF publication remains the relevant-only table and does not include
  extracted evidence, raw HTML, or provider response data.

## Verification

Pure payload, command, OAR-state, checkpoint, and local-join behavior is tested
with deterministic unit tests. The worker is tested with a fake classifier.
The repository gates remain full tests with 100% branch coverage, Ruff, ty,
strict MkDocs, mutation testing with no survivors, and the configured
complexity/CRAP proxy. The live run records the source commit, payload hash,
site, OAR job ID, model ID, row counts, and output hashes on Seagate.
