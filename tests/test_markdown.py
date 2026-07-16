from __future__ import annotations

from audioatlas.markdown import markdown_code_span, markdown_text


def test_markdown_text_is_single_line_and_escapes_structural_punctuation() -> None:
    assert markdown_text("name | *draft*\n_two_") == r"name \| \*draft\* \_two\_"


def test_markdown_code_span_handles_embedded_backticks() -> None:
    assert markdown_code_span("mix.wav") == "`mix.wav`"
    assert markdown_code_span("mix`one`.wav") == "`` mix`one`.wav ``"
