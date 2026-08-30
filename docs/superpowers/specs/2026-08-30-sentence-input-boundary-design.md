# Sentence input boundary design

Sentence validation is a shared policy: only non-blank strings are sent to
the local classifier, and accepted strings retain their original whitespace.
The mapping and Arrow adapters currently repeat the same validation loop while
tracking different source types.

`_iter_sentence_inputs` is a private lazy boundary that accepts source/value
pairs, applies `_non_empty_sentence`, and yields source/sentence pairs. The
mapping adapter supplies row objects as sources; the Arrow adapter supplies
integer row indices. This keeps each adapter's existing representation and
memory behavior while centralizing the policy and preserving source order.

No public API, classifier batching, error text, output column, schema, or
Seagate data policy changes.
