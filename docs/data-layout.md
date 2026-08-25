# Data layout

All local and derived data stays under this exact Seagate path:

    /Volumes/Seagate M3/projects/osm-polygon-web-search

The current package does not create, read, scan, transform, or upload files
from this path. The path is exposed as a pure value so later processing work
can have one explicit boundary.

No local or derived data is published to GitHub or Hugging Face. The initial
Hugging Face dataset card is metadata-only, and data files are never uploaded
as part of this foundation.

Future processing work must preserve this boundary and receive a separate
approved design, tests, documentation, and mutation-testing review.
