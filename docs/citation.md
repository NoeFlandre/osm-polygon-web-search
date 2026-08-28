# Citation and license

## Citation

The repository includes machine-readable citation metadata in
[CITATION.cff](https://github.com/NoeFlandre/osm-polygon-web-search/blob/main/CITATION.cff).

If you use the project, cite it as:

    Flandre, Noe. OSM Polygon Web Search. Version 0.1.0. 2026.

The sentence-level table uses the SAT-3L-SM model from the
[Segment Any Text paper](https://aclanthology.org/2024.emnlp-main.665/) and
the [`wtpsplit`](https://github.com/segment-any-text/wtpsplit) implementation.
The upstream model and implementation are MIT-licensed; their terms remain
separate from this project's Apache-2.0 license.

The relevance step uses the local
[`LiquidAI/LFM2.5-2.6B`](https://huggingface.co/LiquidAI/LFM2.5-2.6B) model.
Its model license and usage terms remain separate from this project's
Apache-2.0 license.

## License

The project code, documentation, and original metadata are available under
the [Apache License 2.0](https://www.apache.org/licenses/LICENSE-2.0). The
Viewer table includes OSM-derived fields and web-derived text, which retain
their source-specific terms. See the repository
[LICENSE](https://github.com/NoeFlandre/osm-polygon-web-search/blob/main/LICENSE)
for the complete Apache terms.
