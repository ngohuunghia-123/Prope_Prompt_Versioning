from __future__ import annotations

import csv
import hashlib
import io
import json
import re
import unicodedata
import zipfile
from collections.abc import Mapping, Sequence
from pathlib import PurePosixPath
from typing import Any

import yaml
from openpyxl import load_workbook
from yaml.tokens import AliasToken, AnchorToken

from prope.prompt_ingestion.domain import (
    MAX_BATCH_ITEMS,
    MAX_EXPANDED_BYTES,
    MAX_SOURCE_CHARACTERS,
    MAX_UPLOAD_BYTES,
    MAX_ZIP_MEMBERS,
    ImportMode,
    IngestionError,
    ParsedCandidate,
)
from prope.prompt_registry.domain import NAME_PATTERN

SUPPORTED_TEXT = {".txt": "txt", ".md": "md", ".markdown": "markdown", ".json": "json", ".yaml": "yaml", ".yml": "yaml"}
TABLE_EXTENSIONS = {".csv", ".xlsx", ".json", ".yaml", ".yml"}
NESTED_ARCHIVES = {".zip", ".tar", ".gz", ".tgz", ".7z", ".rar"}
_SLUG = re.compile(r"[^a-z0-9]+")


def slugify(value: str, fallback: str = "prompt") -> str:
    decomposed = unicodedata.normalize("NFD", value.lower())
    ascii_value = "".join(c for c in decomposed if not unicodedata.combining(c)).replace("đ", "d")
    result = _SLUG.sub("-", ascii_value).strip("-")[:63].rstrip("-")
    return result if result and result[0].isalnum() else fallback


def _decode(data: bytes) -> str:
    if b"\x00" in data:
        raise IngestionError("ingestion_binary_content")
    try:
        text = data.decode("utf-8-sig")
    except UnicodeDecodeError as error:
        raise IngestionError("ingestion_invalid_utf8") from error
    text = text.strip()
    if not text:
        raise IngestionError("ingestion_empty_source")
    if len(text) > MAX_SOURCE_CHARACTERS:
        raise IngestionError("ingestion_source_too_large")
    return text


def _safe_yaml(text: str) -> Any:
    try:
        if any(isinstance(token, (AliasToken, AnchorToken)) for token in yaml.scan(text)):
            raise IngestionError("ingestion_yaml_alias_refused")
        return yaml.safe_load(text)
    except IngestionError:
        raise
    except yaml.YAMLError as error:
        raise IngestionError("ingestion_invalid_yaml") from error


def _safe_member(info: zipfile.ZipInfo) -> bool:
    path = PurePosixPath(info.filename.replace("\\", "/"))
    mode = info.external_attr >> 16
    is_symlink = (mode & 0o170000) == 0o120000
    return not (
        info.is_dir()
        or info.flag_bits & 0x1
        or is_symlink
        or path.is_absolute()
        or ".." in path.parts
        or path.suffix.lower() in NESTED_ARCHIVES
    )


def _expand_files(files: Sequence[tuple[str, bytes]]) -> list[tuple[str, bytes]]:
    if sum(len(data) for _, data in files) > MAX_UPLOAD_BYTES:
        raise IngestionError("ingestion_upload_too_large")
    expanded: list[tuple[str, bytes]] = []
    expanded_bytes = 0
    for filename, data in files:
        if PurePosixPath(filename).suffix.lower() != ".zip":
            expanded.append((PurePosixPath(filename).name, data))
            expanded_bytes += len(data)
            continue
        try:
            with zipfile.ZipFile(io.BytesIO(data)) as archive:
                members = archive.infolist()
                if len(members) > MAX_ZIP_MEMBERS:
                    raise IngestionError("ingestion_too_many_items")
                for member in members:
                    if not _safe_member(member):
                        raise IngestionError("ingestion_unsafe_archive")
                    if member.file_size > MAX_UPLOAD_BYTES:
                        raise IngestionError("ingestion_archive_expansion")
                    expanded_bytes += member.file_size
                    if expanded_bytes > MAX_EXPANDED_BYTES:
                        raise IngestionError("ingestion_archive_expansion")
                    expanded.append((PurePosixPath(member.filename).name, archive.read(member)))
        except IngestionError:
            raise
        except (zipfile.BadZipFile, RuntimeError) as error:
            raise IngestionError("ingestion_invalid_archive") from error
    if len(expanded) > MAX_BATCH_ITEMS:
        raise IngestionError("ingestion_too_many_items")
    return expanded


def _tags(value: Any) -> tuple[str, ...]:
    if value is None:
        return ()
    values = value if isinstance(value, list) else str(value).split(",")
    return tuple(str(item).strip()[:60] for item in values if str(item).strip())[:20]


def _mapped(record: Mapping[str, Any], mapping: Mapping[str, str], field: str, *aliases: str) -> Any:
    key = mapping.get(field)
    if key:
        return record.get(key)
    for candidate in (field, *aliases):
        if candidate in record:
            return record[candidate]
    return None


def _candidate(
    *,
    filename: str,
    source_format: str,
    source: Any,
    namespace: str,
    record: Mapping[str, Any] | None = None,
    mapping: Mapping[str, str] | None = None,
) -> ParsedCandidate:
    fields = record or {}
    field_mapping = mapping or {}
    source_text = str(source).strip()
    if not source_text:
        raise IngestionError("ingestion_empty_source")
    if len(source_text) > MAX_SOURCE_CHARACTERS:
        raise IngestionError("ingestion_source_too_large")
    fallback_title = PurePosixPath(filename).stem or "Prompt"
    title = str(_mapped(fields, field_mapping, "title") or fallback_title).strip()[:200]
    name = str(_mapped(fields, field_mapping, "name") or slugify(title)).strip()[:63]
    item_namespace = str(_mapped(fields, field_mapping, "namespace") or namespace).strip()[:63]
    purpose = str(_mapped(fields, field_mapping, "purpose") or "").strip()[:2000]
    summary = str(_mapped(fields, field_mapping, "change_summary", "changeSummary") or "Imported in batch").strip()[:200]
    target = _mapped(fields, field_mapping, "target_prompt_id", "targetPromptId")
    if not NAME_PATTERN.match(item_namespace):
        raise IngestionError("ingestion_invalid_namespace")
    return ParsedCandidate(
        source_filename=filename[:255],
        source_format=source_format,
        source_text=source_text,
        title=title or "Prompt",
        purpose=purpose,
        namespace=item_namespace or namespace,
        name=slugify(name),
        tags=_tags(_mapped(fields, field_mapping, "tags")),
        change_summary=summary or "Imported in batch",
        target_prompt_id=str(target).strip() if target else None,
    )


def _csv_records(data: bytes) -> list[dict[str, Any]]:
    text = _decode(data)
    try:
        return [dict(row) for row in csv.DictReader(io.StringIO(text))]
    except csv.Error as error:
        raise IngestionError("ingestion_invalid_csv") from error


def _xlsx_records(data: bytes) -> list[dict[str, Any]]:
    try:
        workbook = load_workbook(io.BytesIO(data), read_only=True, data_only=False, keep_links=False)
        sheet = workbook.active
        rows = sheet.iter_rows()
        header_cells = next(rows, None)
        if header_cells is None:
            return []
        headers = [str(cell.value or "").strip() for cell in header_cells]
        records: list[dict[str, Any]] = []
        for cells in rows:
            if any(cell.data_type == "f" for cell in cells):
                raise IngestionError("ingestion_formula_refused")
            values = [cell.value for cell in cells]
            if any(value not in (None, "") for value in values):
                records.append(dict(zip(headers, values, strict=False)))
        workbook.close()
        return records
    except IngestionError:
        raise
    except Exception as error:
        raise IngestionError("ingestion_invalid_xlsx") from error


def _structured_records(filename: str, data: bytes) -> list[Mapping[str, Any]]:
    extension = PurePosixPath(filename).suffix.lower()
    if extension == ".csv":
        records: Any = _csv_records(data)
    elif extension == ".xlsx":
        records = _xlsx_records(data)
    elif extension == ".json":
        try:
            records = json.loads(_decode(data))
        except json.JSONDecodeError as error:
            raise IngestionError("ingestion_invalid_json") from error
    elif extension in {".yaml", ".yml"}:
        records = _safe_yaml(_decode(data))
    else:
        raise IngestionError("ingestion_unsupported_table_format")
    if not isinstance(records, list) or not all(isinstance(row, Mapping) for row in records):
        raise IngestionError("ingestion_table_must_be_records")
    if not records:
        raise IngestionError("ingestion_empty_source")
    if len(records) > MAX_BATCH_ITEMS:
        raise IngestionError("ingestion_too_many_items")
    return records


def parse_uploads(
    files: Sequence[tuple[str, bytes]],
    *,
    mode: ImportMode,
    namespace: str,
    field_mapping: Mapping[str, str] | None = None,
) -> list[ParsedCandidate]:
    if not NAME_PATTERN.match(namespace):
        raise IngestionError("ingestion_invalid_namespace")
    if not files:
        raise IngestionError("ingestion_no_files")
    if mode == ImportMode.FILES:
        candidates: list[ParsedCandidate] = []
        for filename, data in _expand_files(files):
            extension = PurePosixPath(filename).suffix.lower()
            source_format = SUPPORTED_TEXT.get(extension)
            if source_format is None:
                raise IngestionError("ingestion_unsupported_file_format")
            candidates.append(
                _candidate(
                    filename=filename,
                    source_format=source_format,
                    source=_decode(data),
                    namespace=namespace,
                )
            )
        return candidates

    if len(files) != 1 or PurePosixPath(files[0][0]).suffix.lower() not in TABLE_EXTENSIONS:
        raise IngestionError("ingestion_table_requires_one_file")
    filename, data = files[0]
    mapping = field_mapping or {}
    candidates = []
    for index, record in enumerate(_structured_records(filename, data), start=1):
        source = _mapped(record, mapping, "source", "body", "prompt")
        fmt = str(_mapped(record, mapping, "format", "source_format") or "txt").lower()
        if fmt == "yml":
            fmt = "yaml"
        if fmt not in {"txt", "md", "markdown", "json", "yaml"}:
            raise IngestionError("ingestion_unsupported_source_format")
        candidates.append(
            _candidate(
                filename=f"{PurePosixPath(filename).stem}#{index}",
                source_format=fmt,
                source=source or "",
                namespace=namespace,
                record=record,
                mapping=mapping,
            )
        )
    return candidates


def source_hash(candidate: ParsedCandidate) -> str:
    return hashlib.sha256(candidate.source_text.encode("utf-8")).hexdigest()
