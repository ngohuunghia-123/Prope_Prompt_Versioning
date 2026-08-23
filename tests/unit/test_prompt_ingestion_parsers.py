from __future__ import annotations

import io
import zipfile

import pytest
from openpyxl import Workbook

from prope.prompt_ingestion.domain import ImportMode, IngestionError
from prope.prompt_ingestion.parsers import parse_uploads


def test_files_mode_stages_one_candidate_per_file() -> None:
    candidates = parse_uploads(
        [("Refund policy.md", b"Help the customer with a refund."), ("triage.txt", b"Classify the ticket.")],
        mode=ImportMode.FILES,
        namespace="support",
    )

    assert [(item.namespace, item.name, item.source_format) for item in candidates] == [
        ("support", "refund-policy", "md"),
        ("support", "triage", "txt"),
    ]


def test_table_mode_applies_explicit_field_mapping() -> None:
    candidates = parse_uploads(
        [("prompts.csv", b"label,instruction\nSummarize,Summarize the article\n")],
        mode=ImportMode.TABLE,
        namespace="content",
        field_mapping={"title": "label", "source": "instruction"},
    )

    assert candidates[0].title == "Summarize"
    assert candidates[0].source_text == "Summarize the article"


def test_zip_path_traversal_is_refused() -> None:
    archive = io.BytesIO()
    with zipfile.ZipFile(archive, "w") as zipped:
        zipped.writestr("../prompt.txt", "unsafe")

    with pytest.raises(IngestionError, match="ingestion_unsafe_archive"):
        parse_uploads(
            [("prompts.zip", archive.getvalue())],
            mode=ImportMode.FILES,
            namespace="support",
        )


def test_yaml_aliases_are_refused() -> None:
    with pytest.raises(IngestionError, match="ingestion_yaml_alias_refused"):
        parse_uploads(
            [("prompts.yaml", b"- &base {source: hello}\n- *base\n")],
            mode=ImportMode.TABLE,
            namespace="support",
        )


def test_xlsx_formulas_are_never_evaluated_or_imported() -> None:
    workbook = Workbook()
    sheet = workbook.active
    sheet.append(["title", "source"])
    sheet.append(["Unsafe", "=HYPERLINK(\"https://example.invalid\")"])
    content = io.BytesIO()
    workbook.save(content)

    with pytest.raises(IngestionError, match="ingestion_formula_refused"):
        parse_uploads(
            [("prompts.xlsx", content.getvalue())],
            mode=ImportMode.TABLE,
            namespace="support",
        )


def test_invalid_namespace_is_refused_before_staging() -> None:
    with pytest.raises(IngestionError, match="ingestion_invalid_namespace"):
        parse_uploads(
            [("prompt.txt", b"hello")],
            mode=ImportMode.FILES,
            namespace="Not Valid",
        )
