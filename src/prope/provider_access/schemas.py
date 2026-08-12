"""INT-027's wire types. The credential is write-only across the whole seam."""

from typing import Annotated

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field

from prope.provider_access.domain import (
    Adapter,
    CatalogueSource,
    ConfigStatus,
    VerificationStatus,
)

__all__ = [
    "MAX_CREDENTIAL_LENGTH",
    "MAX_DISPLAY_NAME_LENGTH",
    "MIN_CREDENTIAL_LENGTH",
    "CatalogueRefreshRead",
    "CredentialRotate",
    "ModelCreate",
    "ModelRead",
    "ProviderCreate",
    "ProviderRead",
    "ProviderUpdate",
    "VerificationRead",
]

MAX_DISPLAY_NAME_LENGTH = 200

MIN_CREDENTIAL_LENGTH = 8

MAX_CREDENTIAL_LENGTH = 512

MAX_MODEL_ID_LENGTH = 200

BaseUrl = Annotated[str, Field(min_length=8, max_length=2000, pattern=r"^https://\S+$")]

Credential = Annotated[
    str, Field(min_length=MIN_CREDENTIAL_LENGTH, max_length=MAX_CREDENTIAL_LENGTH)
]


class ProviderCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    display_name: str = Field(min_length=1, max_length=MAX_DISPLAY_NAME_LENGTH)
    base_url: BaseUrl
    credential: Credential
    interactive_concurrency: int = Field(default=24, ge=1, le=1024)
    batch_concurrency: int = Field(default=8, ge=1, le=1024)


class ProviderUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    display_name: str | None = Field(default=None, min_length=1, max_length=MAX_DISPLAY_NAME_LENGTH)
    base_url: BaseUrl | None = None
    status: ConfigStatus | None = None
    interactive_concurrency: int | None = Field(default=None, ge=1, le=1024)
    batch_concurrency: int | None = Field(default=None, ge=1, le=1024)


class CredentialRotate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    credential: Credential


class ProviderRead(BaseModel):
    """Everything a dashboard shows. There is no field that carries the secret."""

    model_config = ConfigDict(extra="forbid")

    provider_config_id: str
    display_name: str
    adapter: Adapter
    base_url: str
    status: ConfigStatus
    verification_status: VerificationStatus
    last_verified_at: AwareDatetime | None = None
    verification_error: str | None = None
    credential_last_four: str | None = None
    interactive_concurrency: int
    batch_concurrency: int
    created_by: str
    created_at: AwareDatetime
    updated_at: AwareDatetime


class VerificationRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    provider_config_id: str
    verification_status: VerificationStatus
    last_verified_at: AwareDatetime | None = None
    verification_error: str | None = None
    models_discovered: int


class ModelRead(BaseModel):
    model_config = ConfigDict(extra="forbid", protected_namespaces=())

    model_id: str
    display_name: str | None = None
    supports_streaming: bool
    available: bool
    source: CatalogueSource


class ModelCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", protected_namespaces=())

    model_id: str = Field(min_length=1, max_length=MAX_MODEL_ID_LENGTH)
    display_name: str | None = Field(default=None, max_length=MAX_DISPLAY_NAME_LENGTH)
    supports_streaming: bool = True


class CatalogueRefreshRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    provider_config_id: str
    discovered: int
