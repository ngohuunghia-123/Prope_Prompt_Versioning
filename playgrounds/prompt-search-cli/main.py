"""Prompt Search CLI Test App.

A simple CLI app to test all 3 flows:
1. Index a prompt (provide prompt_id)
2. Manual/Quick search (keyword search)
3. Agent search (semantic search with LLM)
4. Preview index
5. Deindex

Usage:
    python -m prompt_search_cli.main
"""

import os
import sys
import time
from typing import Any

import click
import httpx

# Configuration
DEFAULT_BASE_URL = os.environ.get("PROMPT_SEARCH_API_URL", "http://localhost:8000")
DEFAULT_API_KEY = os.environ.get("PROMPT_SEARCH_API_KEY", "")


class APIClient:
    """Simple API client for prompt-search endpoints."""

    def __init__(self, base_url: str, api_key: str):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.client = httpx.Client(timeout=30.0)

    def _headers(self) -> dict[str, str]:
        headers: dict[str, str] = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers

    def search_quick(self, q: str, limit: int = 50) -> dict[str, Any]:
        """Quick keyword search."""
        response = self.client.get(
            f"{self.base_url}/api/v1/prompts/search",
            params={"q": q, "type": "quick", "limit": limit},
            headers=self._headers(),
        )
        response.raise_for_status()
        return response.json()

    def search_ai(self, q: str, limit: int = 50) -> dict[str, Any]:
        """AI semantic search."""
        response = self.client.get(
            f"{self.base_url}/api/v1/prompts/search",
            params={"q": q, "type": "ai", "limit": limit},
            headers=self._headers(),
        )
        response.raise_for_status()
        return response.json()

    def get_index_status(self, prompt_id: str) -> dict[str, Any]:
        """Get index status for a prompt."""
        response = self.client.get(
            f"{self.base_url}/api/v1/prompts/{prompt_id}/index",
            headers=self._headers(),
        )
        response.raise_for_status()
        return response.json()

    def trigger_indexing(self, prompt_id: str) -> dict[str, Any]:
        """Trigger indexing for a prompt."""
        response = self.client.post(
            f"{self.base_url}/api/v1/prompts/{prompt_id}/index",
            headers=self._headers(),
        )
        response.raise_for_status()
        return response.json()

    def preview_index(self, prompt_id: str) -> dict[str, Any]:
        """Preview what would be indexed."""
        response = self.client.get(
            f"{self.base_url}/api/v1/prompts/{prompt_id}/index/preview",
            headers=self._headers(),
        )
        response.raise_for_status()
        return response.json()

    def deindex(self, prompt_id: str) -> dict[str, Any]:
        """Remove index for a prompt."""
        response = self.client.delete(
            f"{self.base_url}/api/v1/prompts/{prompt_id}/index",
            headers=self._headers(),
        )
        response.raise_for_status()
        return response.json()

    def get_job_status(self, job_id: str) -> dict[str, Any]:
        """Get job status."""
        response = self.client.get(
            f"{self.base_url}/api/v1/prompt-search/jobs/{job_id}",
            headers=self._headers(),
        )
        response.raise_for_status()
        return response.json()

    def list_prompts(self, limit: int = 20) -> list[dict[str, Any]]:
        """List prompts."""
        response = self.client.get(
            f"{self.base_url}/api/v1/prompts",
            params={"limit": limit},
            headers=self._headers(),
        )
        response.raise_for_status()
        return response.json()


def print_search_results(results: dict[str, Any], search_type: str) -> None:
    """Pretty print search results."""
    prompts = results.get("prompts", [])
    search_type_label = "Quick (Keyword)" if search_type == "quick" else "AI (Semantic)"

    click.echo(f"\n{'=' * 60}")
    click.echo(f"  {search_type_label} Search Results")
    click.echo(f"{'=' * 60}")

    if not prompts:
        click.echo("  No results found.")
        return

    click.echo(f"  Total: {results.get('total', len(prompts))} result(s)")
    click.echo(f"  Next cursor: {results.get('next_cursor', 'None')}")
    click.echo()

    for i, prompt in enumerate(prompts, 1):
        click.echo(f"  [{i}] {prompt.get('title', 'Untitled')}")
        click.echo(f"      Prompt ID: {prompt.get('prompt_id', 'N/A')}")
        purpose = prompt.get('purpose', 'N/A')
        if len(purpose) > 100:
            purpose = purpose[:100] + "..."
        click.echo(f"      Purpose: {purpose}")

        if search_type == "ai" and prompt.get("similarity") is not None:
            similarity_pct = prompt["similarity"] * 100
            click.echo(f"      Similarity: {similarity_pct:.1f}%")

        if prompt.get("is_indexed"):
            click.echo("      Status: Indexed")
        else:
            click.echo("      Status: Not Indexed")

        if prompt.get("keywords"):
            click.echo(f"      Keywords: {', '.join(prompt['keywords'][:5])}")
        if prompt.get("topics"):
            click.echo(f"      Topics: {', '.join(prompt['topics'][:3])}")

        click.echo()


def print_index_status(status: dict[str, Any], prompt_id: str) -> None:
    """Pretty print index status."""
    click.echo(f"\n{'=' * 60}")
    click.echo(f"  Index Status for: {prompt_id}")
    click.echo(f"{'=' * 60}")

    if status.get("is_indexed"):
        click.echo("  Status: INDEXED")
        if status.get("indexed_at"):
            click.echo(f"  Indexed At: {status['indexed_at']}")
        if status.get("indexed_by"):
            click.echo(f"  Indexed By: {status['indexed_by']}")
        if status.get("version_id"):
            click.echo(f"  Version ID: {status['version_id']}")

        if status.get("nearest_neighbor"):
            nn = status["nearest_neighbor"]
            click.echo(f"\n  Nearest Neighbor: {nn.get('prompt_id', 'N/A')}")
            if nn.get('similarity'):
                click.echo(f"  Similarity: {nn.get('similarity', 0) * 100:.1f}%")
    else:
        click.echo("  Status: NOT INDEXED")

    click.echo()


def print_preview(preview: dict[str, Any], prompt_id: str) -> None:
    """Pretty print index preview."""
    click.echo(f"\n{'=' * 60}")
    click.echo(f"  Index Preview for: {prompt_id}")
    click.echo(f"{'=' * 60}")

    click.echo(f"\n  Keywords ({len(preview.get('keywords', []))}):")
    for kw in preview.get("keywords", [])[:10]:
        click.echo(f"    - {kw}")

    click.echo(f"\n  Topics ({len(preview.get('topics', []))}):")
    for topic in preview.get("topics", [])[:5]:
        click.echo(f"    - {topic}")

    click.echo(f"\n  Entities ({len(preview.get('entities', []))}):")
    for entity in preview.get("entities", [])[:5]:
        click.echo(f"    - {entity}")

    click.echo(f"\n  Languages: {', '.join(preview.get('language', []))}")

    if preview.get("variations"):
        click.echo("\n  Variations:")
        for lang, variants in preview.get("variations", {}).items():
            if variants:
                click.echo(f"    {lang}: {', '.join(variants[:3])}")

    if preview.get("duplicate_warning"):
        dup = preview["duplicate_warning"]
        similarity_pct = dup.get("similarity", 0) * 100
        click.echo("\n  WARNING: DUPLICATE DETECTED")
        click.echo(f"      Similar prompt: {dup.get('title', 'N/A')}")
        click.echo(f"      Similarity: {similarity_pct:.1f}%")

    click.echo()


@click.group()
@click.option("--base-url", default=DEFAULT_BASE_URL, help="API base URL")
@click.option("--api-key", default=DEFAULT_API_KEY, help="API key for authentication")
@click.pass_context
def cli(ctx: click.Context, base_url: str, api_key: str) -> None:
    """Prompt Search CLI Test App.

    A simple CLI app to test all search flows.
    """
    ctx.ensure_object(dict)
    ctx.obj["client"] = APIClient(base_url, api_key)
    ctx.obj["base_url"] = base_url


@cli.command()
@click.option("--query", "-q", prompt=True, help="Search query")
@click.option("--limit", "-l", default=50, help="Max results")
@click.pass_context
def quick(ctx: click.Context, query: str, limit: int) -> None:
    """Quick keyword search across all prompts."""
    client: APIClient = ctx.obj["client"]

    click.echo(f"\nSearching for: '{query}' (quick search)")

    try:
        results = client.search_quick(query, limit)
        print_search_results(results, "quick")
    except httpx.HTTPStatusError as e:
        click.echo(f"Error: {e.response.status_code} - {e.response.text}", err=True)
        sys.exit(1)
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


@cli.command()
@click.option("--query", "-q", prompt=True, help="Search query")
@click.option("--limit", "-l", default=50, help="Max results")
@click.pass_context
def ai(ctx: click.Context, query: str, limit: int) -> None:
    """AI semantic search over indexed prompts."""
    client: APIClient = ctx.obj["client"]

    click.echo(f"\nSearching for: '{query}' (AI semantic search)")
    click.echo("Note: Only indexed prompts will be searched")

    try:
        results = client.search_ai(query, limit)
        print_search_results(results, "ai")
    except httpx.HTTPStatusError as e:
        click.echo(f"Error: {e.response.status_code} - {e.response.text}", err=True)
        sys.exit(1)
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


@cli.command()
@click.option("--prompt-id", "-p", prompt=True, help="Prompt ID to index")
@click.pass_context
def index(ctx: click.Context, prompt_id: str) -> None:
    """Trigger indexing for a prompt."""
    client: APIClient = ctx.obj["client"]

    click.echo(f"\nTriggering index for prompt: {prompt_id}")

    try:
        # First check status
        status = client.get_index_status(prompt_id)
        if status.get("is_indexed"):
            click.echo("  Prompt is already indexed.")
            if not click.confirm("  Re-index anyway?"):
                return

        # Trigger indexing
        result = client.trigger_indexing(prompt_id)
        job_id = result.get("job_id")

        click.echo(f"  Indexing job created: {job_id}")
        click.echo("  Waiting for job to complete...")

        # Poll for job status
        while True:
            time.sleep(2)
            job_status = client.get_job_status(job_id)
            status_val = job_status.get("status")

            if status_val == "completed":
                click.echo("  Indexing completed successfully!")
                break
            elif status_val == "failed":
                click.echo(f"  Indexing failed: {job_status.get('error')}")
                sys.exit(1)
            else:
                click.echo(f"  Status: {status_val}...")

    except httpx.HTTPStatusError as e:
        click.echo(f"Error: {e.response.status_code} - {e.response.text}", err=True)
        sys.exit(1)
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


@cli.command()
@click.option("--prompt-id", "-p", prompt=True, help="Prompt ID to preview")
@click.pass_context
def preview(ctx: click.Context, prompt_id: str) -> None:
    """Preview what would be indexed for a prompt."""
    client: APIClient = ctx.obj["client"]

    click.echo(f"\nPreviewing index for prompt: {prompt_id}")

    try:
        preview_data = client.preview_index(prompt_id)
        print_preview(preview_data, prompt_id)
    except httpx.HTTPStatusError as e:
        click.echo(f"Error: {e.response.status_code} - {e.response.text}", err=True)
        sys.exit(1)
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


@cli.command()
@click.option("--prompt-id", "-p", prompt=True, help="Prompt ID to deindex")
@click.pass_context
def deindex(ctx: click.Context, prompt_id: str) -> None:
    """Remove index for a prompt."""
    client: APIClient = ctx.obj["client"]

    click.echo(f"\nRemoving index for prompt: {prompt_id}")

    try:
        result = client.deindex(prompt_id)
        if result.get("success"):
            click.echo("  Index removed successfully!")
        else:
            click.echo("  No index found to remove.")
    except httpx.HTTPStatusError as e:
        click.echo(f"Error: {e.response.status_code} - {e.response.text}", err=True)
        sys.exit(1)
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


@cli.command()
@click.option("--prompt-id", "-p", prompt=True, help="Prompt ID to check")
@click.pass_context
def status(ctx: click.Context, prompt_id: str) -> None:
    """Get index status for a prompt."""
    client: APIClient = ctx.obj["client"]

    click.echo(f"\nGetting index status for prompt: {prompt_id}")

    try:
        status_data = client.get_index_status(prompt_id)
        print_index_status(status_data, prompt_id)
    except httpx.HTTPStatusError as e:
        click.echo(f"Error: {e.response.status_code} - {e.response.text}", err=True)
        sys.exit(1)
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


@cli.command()
@click.option("--limit", "-l", default=20, help="Max prompts to list")
@click.pass_context
def list_prompts(ctx: click.Context, limit: int) -> None:
    """List available prompts."""
    client: APIClient = ctx.obj["client"]

    click.echo(f"\nListing prompts (limit: {limit})")

    try:
        prompts = client.list_prompts(limit)

        click.echo(f"\n{'=' * 60}")
        click.echo("  Available Prompts")
        click.echo(f"{'=' * 60}")

        if not prompts:
            click.echo("  No prompts found.")
            return

        for i, prompt in enumerate(prompts, 1):
            click.echo(f"\n  [{i}] {prompt.get('title', 'Untitled')}")
            click.echo(f"      ID: {prompt.get('prompt_id', 'N/A')}")
            click.echo(f"      Model: {prompt.get('model_name', 'N/A')}")
            click.echo(f"      Status: {prompt.get('status', 'N/A')}")

    except httpx.HTTPStatusError as e:
        click.echo(f"Error: {e.response.status_code} - {e.response.text}", err=True)
        sys.exit(1)
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


def main() -> None:
    """Main entry point."""
    cli(obj={})


if __name__ == "__main__":
    main()
