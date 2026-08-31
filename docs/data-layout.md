# Data layout

All local and derived data stays under this exact Seagate path:

    /Volumes/Seagate M3/projects/osm-polygon-web-search

The PBF-first proof of concept reads the selected PBF from this path and writes
only run manifests below this path. The path remains the single explicit local
data boundary.

The initial layout is:

    liechtenstein-latest.osm.pbf       immutable source snapshot
    runs/poc/run.json                   candidate, query variants, and review manifest
    runs/poc/hf-viewer/train.parquet   source one-row-per-page table
    runs/poc-20260828-sat-3l-sm/       sentence-level Viewer output
    runs/poc-20260828-lfm2.5-2.6b-relevance/
                                      complete labels and relevant-only Viewer output

The PBF, raw HTML, and provider response remain on the Seagate. The explicitly
approved sentence-level output is classified locally with
`LiquidAI/LFM2.5-2.6B`. The complete yes/no table stays on the Seagate. Its
relevant-only subset is copied to Hugging Face as `train.parquet`; it contains
polygon geometry, the exact Brave query, URL fields, full page text parsed by
Trafilatura, sentence position and count, SAT provenance, and LFM provenance.
The published table omits extracted evidence and criteria. Raw HTML and
provider responses are not published to GitHub or Hugging Face.
The live search adapter is opt-in, and its credentials are read only from the
`BRAVE_SEARCH_API_KEY` environment variable.

Future processing work must preserve this boundary and receive a separate
approved design, tests, documentation, and mutation-testing review.

## Grid'5000 run artifacts

A remote classification run keeps its local control artifacts below the same
`runs/<run>/grid5000/` directory:

    input.json.gz             sentence-only transfer payload
    job.sh                    generated OAR job script
    job.id                    submitted OAR identifier
    checkpoint.json.gz        retrieved complete ordered labels
    output.json.gz            retrieved final labels
    oar.stdout, oar.stderr    retrieved job logs
    classified.parquet        local complete yes/no join
    relevant.parquet          local yes-only Viewer table
    manifest.json             hashes, job, model, and row counts

Only the sentence payload crosses to Grid'5000. The model and dependency caches
are node-local temporary files; no model cache is written to the MacBook SSD or
the remote `/home` run directory. The runner removes the exact remote run
directory only after local validation succeeds.
