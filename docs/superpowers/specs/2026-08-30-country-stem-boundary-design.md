# Country stem boundary design

The country resolver has two responsibilities: stripping the exact PBF
filename suffixes and converting the remaining basename into a display label.
The suffix operation is a pure private boundary so it can be tested directly
and expressed with the standard `str.removesuffix` operation.

The accepted suffix order remains unchanged: remove `.osm.pbf` first, then
`-latest`. Country normalization, title casing, and the existing empty-name
error remain in `country_from_pbf`. No input formats or output values change.
