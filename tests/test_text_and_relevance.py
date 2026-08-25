from osm_polygon_web_search.relevance import find_evidence
from osm_polygon_web_search.text import extract_text


def test_trafilatura_extracts_article_text() -> None:
    html = """
    <html><body><article>
      <h1>Alp X</h1>
      <p>Alp X has exposed limestone and alpine vegetation.</p>
    </article></body></html>
    """

    text = extract_text(html)

    assert text is not None
    assert "exposed limestone" in text


def test_relevance_requires_the_place_and_returns_physical_criteria() -> None:
    evidence = find_evidence(
        "Alp X has exposed LIMESTONE. Alp X has alpine vegetation.",
        place_name="Alp X",
    )

    assert len(evidence) == 2
    assert evidence[0].criteria == ("soil_surface",)
    assert evidence[1].criteria == ("vegetation_ecosystem",)


def test_relevance_continues_after_a_nonmatching_sentence() -> None:
    assert (
        find_evidence(
            "The region has alpine vegetation. Alp X has limestone.",
            place_name="Alp X",
        )[0].sentence
        == "Alp X has limestone."
    )


def test_relevance_ignores_generic_category_text_without_the_place() -> None:
    assert find_evidence("The region has alpine vegetation.", place_name="Alp X") == []


def test_relevance_ignores_a_place_sentence_without_a_target_criterion() -> None:
    assert find_evidence("Alp X is a place.", place_name="Alp X") == []


def test_relevance_ignores_empty_place_names() -> None:
    assert find_evidence("Alp X has limestone.", place_name="  ") == []


def test_empty_html_has_no_extracted_text() -> None:
    assert (
        extract_text("<html><head><title>Empty</title></head><body></body></html>")
        is None
    )
