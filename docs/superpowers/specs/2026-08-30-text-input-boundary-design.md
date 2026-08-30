# Text input boundary design

Both sentence adapters accept any string value, including the empty string,
and ignore all other values. They currently encode that policy in separate
loops while retaining different source types.

`_iter_text_inputs` is a private lazy boundary that preserves each source and
string value in order. `sentence_rows` uses page mappings as sources, while
`_source_text_inputs` uses Arrow row indices. The adapters continue to own
their output lists and Arrow selection, so no public API, sentence model call,
output schema, or data policy changes.
