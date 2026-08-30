# Typed selection-plan boundary

`pipeline.py` currently represents the result of candidate selection as a
mutable `dict[str, Any]`. Both public planning functions then inspect the
serialized `selected` value and repeat the same `dict`/`None` branching before
adding their query fields. This makes the internal selection state less
explicit and couples query construction to the JSON representation.

The private `_SelectionPlan` dataclass will own the typed selection state and
its conversion to the existing JSON-compatible dictionary. `build_plan` and
`build_variant_plan` will construct the serialized dictionary only at their
public boundary and will use the typed `PolygonCandidate | None` directly for
query construction. The returned keys, values, ordering, query variants,
search behavior, and public function signatures remain unchanged.

No new runtime behavior, configuration, schema, provider, or data path is
introduced. The change removes internal representation coupling only.
