# Typed osmium ingestion boundary design

## Problem

The PBF scanner accepts pyosmium ways, areas, nodes, and geometry factories
through `Any`. These values enter the core candidate-selection path, so the
current annotations cannot detect an incorrect attribute name or collaborator
shape in the helpers that build polygon candidates.

The other remaining `Any` annotations are either heterogeneous JSON records
or third-party ML adapters. Removing those safely would require a broader
schema or tensor-interface refactor. The PBF boundary is therefore the highest
impact narrow improvement: its required object shapes are small and already
stable.

## Decision

Define four private structural protocols in `pbf.py`:

- `_CoordinateNode` exposes longitude and latitude;
- `_WayObject` exposes an id, tags, and iterable nodes;
- `_AreaObject` exposes tags plus the existing `from_way` and `orig_id`
  methods;
- `_GeometryFactory` exposes multipolygon serialization.

Use those protocols on `_way_candidate`, `_relation_geometry`, and
`_relation_candidate`. Accept `object` at `_object_candidate`, retain its
existing concrete pyosmium runtime checks, and bridge each checked object to
the structural type with `cast`. Cast the pyosmium factory once when it is
created because pyosmium's factory protocol is intentionally tied to its
concrete `Area` class while this module also supports structural test doubles.

## Compatibility

This is an annotation-only refactor. `Protocol` and `cast` add no runtime
validation or conversion. The scanner's public signature, object filtering,
tag access, geometry generation, exception handling, candidate ordering, and
outputs remain unchanged. No data, model, network, dependency, or feature
surface is added.

## Verification

Add a contract test that first fails against the existing `Any` annotations,
then proves all four helpers expose the intended boundary types. Run the
focused PBF tests followed by formatting, linting, `ty`, complete line and
branch coverage, strict MkDocs, pre-commit, the McCabe/CRAP gate, fresh
mutation testing, and a wheel build. Attempt the Docker gate and report any
local-daemon limitation separately.
