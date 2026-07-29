"""Exact historical-character projection onto one installed content set.

The canonical registry identity (pack, kind, content ID, version) is the only
allowed replacement coordinate.  Contract hashes authenticate the historical
and installed definitions; display labels, Python paths, and fuzzy aliases are
never consulted.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TypeVar

from pydantic import BaseModel, ValidationError

from dnd.content_system.character_appearance import (
    migrate_player_character_appearance,
    resolve_player_character_appearance,
)
from dnd.content_system.character_content_migrations import (
    CHARACTER_CONTENT_REF_MIGRATIONS_BY_SOURCE,
    exact_content_ref_key,
)
from dnd.core.content.durable_characters import (
    BuildChoiceSelection,
    CharacterAppearanceSelection,
    CharacterHoldingsRevision,
    CharacterItemV1,
    ItemAugmentationRecord,
)
from dnd.core.content.identities import ContentRef
from dnd.core.content.premade_characters import (
    CharacterBuildDraft,
    CharacterLoadoutDraft,
)
from dnd.core.content.recipes import ContentRecipe
from dnd.core.content.registry import FrozenContentRegistry
from server.character_directory_contracts import (
    CharacterAppearanceOptionRebaseChange,
    CharacterContentRefRebaseChange,
    CharacterContentRebaseIssue,
    CharacterContentRebaseIssueReason,
    CharacterOriginChoiceRebaseChange,
    CharacterRebaseChange,
)


_ModelT = TypeVar("_ModelT", bound=BaseModel)


@dataclass(frozen=True, slots=True)
class CharacterContentRebaseResult:
    """One deterministic current-content projection and its evidence."""

    build: CharacterBuildDraft
    loadout: CharacterLoadoutDraft
    holdings: CharacterHoldingsRevision
    holdings_changed: bool
    changes: tuple[CharacterRebaseChange, ...]
    issues: tuple[CharacterContentRebaseIssue, ...]

    @property
    def ready(self) -> bool:
        return not self.issues


class _ContentRebaser:
    def __init__(self, registry: FrozenContentRegistry) -> None:
        self._registry = registry
        self._changes: list[CharacterRebaseChange] = []
        self._issues: list[CharacterContentRebaseIssue] = []

    def result(
        self,
        *,
        build: CharacterBuildDraft,
        loadout: CharacterLoadoutDraft,
        holdings: CharacterHoldingsRevision,
        holdings_changed: bool,
    ) -> CharacterContentRebaseResult:
        return CharacterContentRebaseResult(
            build=build,
            loadout=loadout,
            holdings=holdings,
            holdings_changed=holdings_changed,
            changes=tuple(sorted(self._changes, key=lambda row: row.path)),
            issues=tuple(sorted(self._issues, key=lambda row: row.path)),
        )

    def model(self, value: _ModelT, path: tuple[str, ...]) -> _ModelT:
        updates = {}
        for field_name in type(value).model_fields:
            original = getattr(value, field_name)
            replacement = self.value(
                original,
                (*path, field_name),
            )
            if replacement != original:
                updates[field_name] = replacement
        if not updates:
            return value
        return value.model_copy(update=updates)

    def value(self, value: object, path: tuple[str, ...]) -> object:
        if isinstance(value, ContentRef):
            return self.ref(value, path)
        if isinstance(value, ContentRecipe):
            return self.recipe(value, path)
        if isinstance(value, CharacterAppearanceSelection):
            return self.appearance(value, path)
        if isinstance(value, tuple):
            return tuple(
                self.value(row, (*path, str(index)))
                for index, row in enumerate(value)
            )
        if isinstance(value, BaseModel):
            return self.model(value, path)
        return value

    def ref(self, ref: ContentRef, path: tuple[str, ...]) -> ContentRef:
        declaration = self._registry.declarations.get(ref.identity_key)
        if declaration is None:
            migration = CHARACTER_CONTENT_REF_MIGRATIONS_BY_SOURCE.get(
                exact_content_ref_key(ref),
            )
            if migration is not None:
                declaration = self._registry.declarations.get(
                    migration.target_ref.identity_key,
                )
                if (
                    declaration is not None
                    and declaration.ref == migration.target_ref
                ):
                    self._changes.append(CharacterContentRefRebaseChange(
                        path=path,
                        source_ref=ref,
                        replacement_ref=declaration.ref,
                    ))
                    return declaration.ref
            self._issues.append(CharacterContentRebaseIssue(
                path=path,
                reason=(
                    CharacterContentRebaseIssueReason.IDENTITY_NOT_INSTALLED
                ),
                source_ref=ref,
                detail=(
                    "No installed definition owns this exact canonical "
                    "content identity."
                ),
            ))
            return ref
        replacement = declaration.ref
        if replacement == ref:
            return ref
        self._changes.append(CharacterContentRefRebaseChange(
            path=path,
            source_ref=ref,
            replacement_ref=replacement,
        ))
        return replacement

    def appearance(
        self,
        selection: CharacterAppearanceSelection,
        path: tuple[str, ...],
    ) -> CharacterAppearanceSelection:
        migration = migrate_player_character_appearance(selection)
        for added in migration.added_options:
            self._changes.append(CharacterAppearanceOptionRebaseChange(
                path=(*path, "options", added.option_id),
                selection=added,
            ))
        return migration.selection

    def add_origin_choices(
        self,
        *,
        source_species_ref: ContentRef,
        build: CharacterBuildDraft,
    ) -> CharacterBuildDraft:
        migration = CHARACTER_CONTENT_REF_MIGRATIONS_BY_SOURCE.get(
            exact_content_ref_key(source_species_ref),
        )
        if migration is None or not migration.added_origin_choices:
            return build
        existing_by_id = {
            choice.choice_id: choice
            for choice in build.immutable_origin_choices
        }
        choices: list[BuildChoiceSelection] = list(
            build.immutable_origin_choices,
        )
        for choice in migration.added_origin_choices:
            existing = existing_by_id.get(choice.choice_id)
            if existing == choice:
                continue
            path = (
                "build",
                "immutable_origin_choices",
                choice.choice_id,
            )
            if existing is not None:
                self._issues.append(CharacterContentRebaseIssue(
                    path=path,
                    reason=(
                        CharacterContentRebaseIssueReason
                        .ORIGIN_CHOICE_CONFLICT
                    ),
                    source_ref=source_species_ref,
                    detail=(
                        "The historical character already owns a different "
                        "selection for an exact migration-required choice."
                    ),
                ))
                continue
            choices.append(choice)
            existing_by_id[choice.choice_id] = choice
            self._changes.append(CharacterOriginChoiceRebaseChange(
                path=path,
                selection=choice,
            ))
        return build.model_copy(update={
            "immutable_origin_choices": tuple(sorted(
                choices,
                key=lambda row: row.choice_id,
            )),
        })

    def validate_appearance(
        self,
        build: CharacterBuildDraft,
    ) -> None:
        try:
            resolve_player_character_appearance(
                body_ref=build.body_recipe.ref,
                species_ref=build.species_ref,
                selection=build.appearance,
            )
        except ValueError as error:
            self._issues.append(CharacterContentRebaseIssue(
                path=("build", "appearance"),
                reason=(
                    CharacterContentRebaseIssueReason
                    .APPEARANCE_SELECTION_UNSUPPORTED
                ),
                source_ref=build.body_recipe.ref,
                detail=str(error),
            ))

    def recipe(
        self,
        recipe: ContentRecipe,
        path: tuple[str, ...],
    ) -> ContentRecipe:
        replacement_ref = self.ref(recipe.ref, (*path, "ref"))
        if replacement_ref == recipe.ref:
            return recipe
        try:
            declaration = self._registry.resolve_factory(replacement_ref)
            construction = declaration.construction
            if construction is None:
                raise TypeError("installed factory has no construction")
            construction.parameter_model.model_validate(recipe.parameters)
        except (KeyError, TypeError, ValueError, ValidationError) as error:
            self._issues.append(CharacterContentRebaseIssue(
                path=(*path, "parameters"),
                reason=(
                    CharacterContentRebaseIssueReason
                    .RECIPE_PARAMETERS_INCOMPATIBLE
                ),
                source_ref=recipe.ref,
                detail=str(error),
            ))
            return recipe
        return ContentRecipe.create(
            ref=replacement_ref,
            parameters=recipe.parameters,
        )


def rebase_character_content(
    *,
    registry: FrozenContentRegistry,
    build: CharacterBuildDraft,
    loadout: CharacterLoadoutDraft,
    holdings: CharacterHoldingsRevision,
) -> CharacterContentRebaseResult:
    """Project all durable content refs onto exact installed contracts."""

    rebaser = _ContentRebaser(registry)
    rebased_build = rebaser.model(build, ("build",))
    rebased_build = rebaser.add_origin_choices(
        source_species_ref=build.species_ref,
        build=rebased_build,
    )
    rebaser.validate_appearance(rebased_build)
    rebased_loadout = rebaser.model(loadout, ("loadout",))
    items: list[CharacterItemV1] = []
    holdings_changed = False
    for index, item in enumerate(holdings.items):
        item_path = ("holdings", "items", str(index))
        recipe = rebaser.recipe(item.recipe, (*item_path, "recipe"))
        augmentations = tuple(
            ItemAugmentationRecord.create(
                content_ref=rebaser.ref(
                    augmentation.content_ref,
                    (
                        *item_path,
                        "durable_augmentations",
                        str(augmentation_index),
                        "content_ref",
                    ),
                ),
                parameters=augmentation.parameters,
                durable_state=augmentation.durable_state,
            )
            for augmentation_index, augmentation in enumerate(
                item.durable_augmentations,
            )
        )
        if (
            recipe == item.recipe
            and augmentations == item.durable_augmentations
        ):
            items.append(item)
            continue
        holdings_changed = True
        items.append(CharacterItemV1.create(
            character_item_id=item.character_item_id,
            recipe=recipe,
            quantity=item.quantity,
            remaining_charges=item.remaining_charges,
            durability_damage=item.durability_damage,
            durable_augmentations=augmentations,
            equipped_slot=item.equipped_slot,
        ))
    rebased_holdings = holdings
    if holdings_changed:
        rebased_holdings = CharacterHoldingsRevision.create(
            character_id=holdings.character_id,
            holdings_revision=holdings.holdings_revision + 1,
            items=tuple(items),
        )
    return rebaser.result(
        build=rebased_build,
        loadout=rebased_loadout,
        holdings=rebased_holdings,
        holdings_changed=holdings_changed,
    )


__all__ = [
    "CharacterContentRebaseResult",
    "rebase_character_content",
]
