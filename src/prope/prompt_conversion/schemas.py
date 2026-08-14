"""HTTP wire schemas for prompt conversion."""

from pydantic import BaseModel, ConfigDict, Field

from prope.prompt_conversion.domain import MAX_SOURCE_CHARACTERS, SourceFormat


class PromptConversionCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_text: str = Field(min_length=1, max_length=MAX_SOURCE_CHARACTERS)
    source_format: SourceFormat
    prompt_id: str | None = None


class PromptConversionRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    xml_body: str
    model: str
    schema_version: str
