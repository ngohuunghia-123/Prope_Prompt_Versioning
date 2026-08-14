"""App Agent for metadata extraction from prompt body and purpose.

Uses gpt-4o-mini (configurable via APP_AGENT_MODEL env var) to extract:
  - keywords: relevant terms for search
  - topics: broader categories
  - entities: named entities mentioned
  - variations: multilingual variations (en, vi)
  - language: detected language(s)

Separate from user's BYOK provider - app owns the API key.
"""

import json

from pydantic import BaseModel

from prope.prompt_search.agent.base import (
    APP_AGENT_MODEL,
    call_app_service,
    get_openai_client,
)
from prope.prompt_search.domain import ExtractedMetadata, ExtractedVariations

__all__ = [
    "APP_AGENT_MODEL",
    "extract_metadata",
    "preview_extraction",
]

#: Extraction prompt template
EXTRACTION_PROMPT = """You are a metadata extraction agent. Given a prompt's body and purpose, extract structured metadata for search indexing.

Extract the following:
1. **keywords**: 5-15 relevant search terms that would help find this prompt
2. **topics**: 2-5 broader categories this prompt belongs to
3. **entities**: Any named entities (products, systems, company names, etc.) mentioned
4. **variations**: Alternative phrasings in English (en) and Vietnamese (vi)
5. **language**: Primary and secondary languages detected (use 'en' or 'vi')

Output ONLY valid JSON in this exact format:
{
  "keywords": ["keyword1", "keyword2", ...],
  "topics": ["topic1", "topic2", ...],
  "entities": ["entity1", "entity2", ...],
  "variations": {
    "en": ["variation1", "variation2"],
    "vi": ["biến thể1", "biến thể2"]
  },
  "language": ["en", "vi"]
}

Rules:
- keywords should be lowercase, singular nouns or short phrases
- topics should be broader categories (e.g., "customer support", "data analysis", "code review")
- entities should be specific names, not generic terms
- variations should capture different ways to express the same intent
- language codes should be 'en' or 'vi'
- Do NOT include the prompt body in the output

PROMPT TITLE: {title}
PROMPT PURPOSE: {purpose}

PROMPT BODY:
{body}

Output JSON only:"""


class ExtractionResult(BaseModel):
    """Result from the extraction agent."""

    keywords: list[str]
    topics: list[str]
    entities: list[str]
    variations: dict[str, list[str]]
    language: list[str]


async def extract_metadata(
    body: str,
    purpose: str,
    title: str,
) -> ExtractedMetadata:
    """Extract structured metadata from a prompt.

    Args:
        body: The prompt body text
        purpose: The prompt's stated purpose
        title: The prompt's title

    Returns:
        ExtractedMetadata with keywords, topics, entities, variations, language
    """
    client = await get_openai_client()

    prompt = EXTRACTION_PROMPT.format(
        title=title,
        purpose=purpose,
        body=body[:4000],  # Truncate very long prompts
    )

    try:
        response = await call_app_service(
            lambda: client.chat.completions.create(
                model=APP_AGENT_MODEL,
                messages=[
                    {
                        "role": "system",
                        "content": "You are a metadata extraction agent. Extract structured metadata from prompts for search indexing. Output ONLY valid JSON.",
                    },
                    {"role": "user", "content": prompt},
                ],
                temperature=0.1,
                max_tokens=1000,
            )
        )

        content = response.choices[0].message.content

        # Parse JSON from response
        # Handle cases where model wraps JSON in markdown code blocks
        if content and content.startswith("```"):
            content = content.split("```")[1]
            if content.startswith("json"):
                content = content[4:]
            content = content.strip()

        data = ExtractionResult.model_validate(json.loads(content))

        return ExtractedMetadata(
            keywords=tuple(data.keywords),
            topics=tuple(data.topics),
            entities=tuple(data.entities),
            variations=ExtractedVariations.from_dict(data.variations),
            language=tuple(data.language),
        )

    except json.JSONDecodeError as e:
        raise ValueError(f"Failed to parse extraction result: {e}") from e
    except Exception as e:
        raise RuntimeError(f"Extraction failed: {e}") from e


async def preview_extraction(
    body: str,
    purpose: str,
    title: str,
) -> ExtractedMetadata:
    """Preview extraction without caching or storing.

    Same as extract_metadata but for preview purposes.
    """
    return await extract_metadata(body, purpose, title)
