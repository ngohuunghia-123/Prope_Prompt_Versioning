"""Terminal playground for the prompt-to-XML conversion endpoint.

Examples:
    python main.py convert --file prompt.md
    python main.py convert --format json --text '{"task": "Summarize {{topic}}"}'
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import click
import httpx

DEFAULT_BASE_URL = os.environ.get("PROMPT_CONVERSION_API_URL", "http://localhost:8080")
FORMAT_BY_SUFFIX = {
    ".txt": "txt",
    ".md": "markdown",
    ".markdown": "markdown",
    ".json": "json",
    ".yaml": "yaml",
    ".yml": "yaml",
}


def _read_dotenv_value(name: str) -> str:
    """Read one local playground setting without exporting all of `.env` to the shell."""
    dotenv_path = Path(__file__).resolve().parents[2] / ".env"
    try:
        for line in dotenv_path.read_text(encoding="utf-8").splitlines():
            key, separator, value = line.partition("=")
            if separator and key.strip() == name:
                return value.strip()
    except FileNotFoundError:
        pass
    return ""


DEFAULT_SESSION = os.environ.get("PROPE_SESSION") or os.environ.get(
    "ADMIN_SESSION_TOKEN"
) or _read_dotenv_value("ADMIN_SESSION_TOKEN")


class ConversionClient:
    """Small HTTP client that uses the same session cookie as the web app."""

    def __init__(self, base_url: str, session_id: str) -> None:
        self._client = httpx.Client(
            base_url=base_url.rstrip("/"),
            cookies={"prope_session": session_id} if session_id else None,
            timeout=45.0,
        )

    def convert(
        self, source_text: str, source_format: str, prompt_id: str | None
    ) -> dict[str, Any]:
        response = self._client.post(
            "/api/v1/prompt-conversions",
            json={
                "source_text": source_text,
                "source_format": source_format,
                "prompt_id": prompt_id,
            },
        )
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, dict):
            raise ValueError("conversion response is not a JSON object")
        return payload


def _read_source(path: Path) -> tuple[str, str]:
    source_format = FORMAT_BY_SUFFIX.get(path.suffix.lower())
    if source_format is None:
        supported = ", ".join(sorted(FORMAT_BY_SUFFIX))
        raise click.ClickException(f"unsupported file extension; expected one of: {supported}")
    try:
        return path.read_bytes().decode("utf-8", errors="strict"), source_format
    except UnicodeDecodeError as error:
        raise click.ClickException("source file is not valid UTF-8") from error


@click.group()
@click.option("--base-url", default=DEFAULT_BASE_URL, show_default=True)
@click.option(
    "--session",
    "session_id",
    default=DEFAULT_SESSION,
    help="Value of the prope_session cookie (or set PROPE_SESSION or ADMIN_SESSION_TOKEN).",
)
@click.pass_context
def cli(ctx: click.Context, base_url: str, session_id: str) -> None:
    """Exercise prompt conversion from a terminal against a running Prope API."""
    ctx.ensure_object(dict)
    ctx.obj["client"] = ConversionClient(base_url, session_id)


@cli.command()
@click.option(
    "--file",
    "source_file",
    type=click.Path(path_type=Path, exists=True, dir_okay=False),
    help="UTF-8 TXT, Markdown, JSON, or YAML file; format is inferred.",
)
@click.option("--text", help="Pasted source text.")
@click.option(
    "--format",
    "source_format",
    type=click.Choice(["txt", "markdown", "json", "yaml"]),
    help="Required with --text; optional override with --file.",
)
@click.option("--prompt-id", help="Existing prompt id; changes authorization to revision.create.")
@click.option(
    "--output",
    type=click.Path(path_type=Path, dir_okay=False),
    help="Write the XML preview to this file in addition to stdout.",
)
@click.pass_context
def convert(
    ctx: click.Context,
    source_file: Path | None,
    text: str | None,
    source_format: str | None,
    prompt_id: str | None,
    output: Path | None,
) -> None:
    """Convert one source into editable canonical XML without saving a revision."""
    if (source_file is None) == (text is None):
        raise click.UsageError("provide exactly one of --file or --text")

    if source_file is not None:
        source_text, inferred_format = _read_source(source_file)
        selected_format = source_format or inferred_format
    else:
        if source_format is None:
            raise click.UsageError("--format is required with --text")
        source_text = text or ""
        selected_format = source_format

    client: ConversionClient = ctx.obj["client"]
    try:
        result = client.convert(source_text, selected_format, prompt_id)
    except httpx.HTTPStatusError as error:
        click.echo(
            f"Conversion failed ({error.response.status_code}): {error.response.text}",
            err=True,
        )
        raise click.exceptions.Exit(1) from error
    except httpx.HTTPError as error:
        raise click.ClickException(str(error)) from error

    xml_body = result.get("xml_body")
    if not isinstance(xml_body, str):
        raise click.ClickException("conversion response has no string xml_body")

    click.echo(f"Model: {result.get('model', 'unknown')}", err=True)
    click.echo(f"Schema: {result.get('schema_version', 'unknown')}", err=True)
    click.echo(xml_body)
    if output is not None:
        output.write_text(xml_body, encoding="utf-8")
        click.echo(f"Wrote XML preview to {output}", err=True)


def main() -> None:
    cli(obj={})


if __name__ == "__main__":
    main()
