"""Canonical JSON recipes for reconstructing runtime content."""

from __future__ import annotations

from typing import Self

from pydantic import BaseModel, ConfigDict, Field, JsonValue, model_validator

from dnd.core.content.canonical import canonical_content_sha256
from dnd.core.content.identities import ContentRef


def compute_recipe_digest(
    ref: ContentRef,
    parameters: dict[str, JsonValue],
) -> str:
    """Hash one content reference and canonical JSON parameter object."""
    payload = {
        "ref": ref.model_dump(mode="json"),
        "parameters": parameters,
    }
    return canonical_content_sha256(payload)


class ContentRecipe(BaseModel):
    """Self-authenticating durable content construction request."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    ref: ContentRef
    parameters: dict[str, JsonValue] = Field(default_factory=dict)
    recipe_digest: str

    @classmethod
    def create(
        cls,
        *,
        ref: ContentRef,
        parameters: dict[str, JsonValue],
    ) -> Self:
        """Create a recipe with its canonical digest."""
        return cls(
            ref=ref,
            parameters=parameters,
            recipe_digest=compute_recipe_digest(ref, parameters),
        )

    @model_validator(mode="after")
    def _validate_recipe_digest(self) -> Self:
        self.verify_integrity()
        return self

    def verify_integrity(self) -> None:
        """Reject any mutation of the authenticated JSON parameter graph."""
        expected = compute_recipe_digest(self.ref, self.parameters)
        if self.recipe_digest != expected:
            raise ValueError(
                "recipe_digest does not authenticate the content reference "
                "and parameters",
            )
