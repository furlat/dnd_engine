"""Persistent character-sheet equipment uses the runtime equipment authority."""

from __future__ import annotations

from pathlib import Path
from uuid import UUID, uuid4

import pytest
from pydantic import ValidationError

import server.character_directory_service as service_module
from dnd.content_system.bootstrap import bootstrap_content_system
from dnd.content_system.builtin_character_builds import (
    BUILTIN_PREMADE_BUILDS,
    compose_builtin_character_revisions,
)
from dnd.core.content.durable_characters import CharacterItemV1
from dnd.core.equipment_types import WeaponSlot
from server.character_directory_contracts import (
    CharacterEquipmentMutationRequest,
    CharacterEquipOperation,
    CharacterUnequipOperation,
)
from server.character_directory_service import (
    CharacterDirectoryOwnershipError,
    CharacterDirectoryService,
)
from server.game_directory.contracts import (
    CharacterAdvancementAwardCreate,
    CharacterAdvancementSourceKind,
    CharacterBootstrapCreate,
    CharacterDeploymentLeaseCreate,
    GameCreate,
    MembershipCapabilities,
    MembershipCreate,
    MembershipRole,
    PrincipalCreate,
    PrincipalKind,
)
from server.game_directory.errors import ConflictError, StaleVersionError
from server.game_directory.repository import GameDirectoryRepository
from server.game_gateway import create_gateway_app


_PEPPER = b"persistent-character-equipment-mutation"
_PREMADE_ID = "hero.barbarian_l5_berserker_torch"


def _item(
    items: tuple[CharacterItemV1, ...],
    content_id: str,
) -> CharacterItemV1:
    return next(
        item for item in items if item.recipe.ref.content_id == content_id
    )


def _seed(
    tmp_path: Path,
) -> tuple[
    GameDirectoryRepository,
    CharacterDirectoryService,
    UUID,
    UUID,
]:
    repository = GameDirectoryRepository(
        tmp_path / "directory.sqlite3",
        capability_pepper=_PEPPER,
    )
    owner = repository.create_principal(
        PrincipalCreate(
            principal_kind=PrincipalKind.HUMAN,
            display_name="Owner",
        ),
    )
    content_system = bootstrap_content_system()
    service = CharacterDirectoryService(repository, content_system)
    settings = service.ensure_profile_settings(owner.principal_id)
    build = BUILTIN_PREMADE_BUILDS[_PREMADE_ID]
    character_id = uuid4()
    revisions = compose_builtin_character_revisions(
        character_id=character_id,
        build=build,
        content_system=content_system,
        ruleset_digest=settings.ruleset_digest,
    )
    repository.create_character_with_revisions(
        CharacterBootstrapCreate(
            character_id=character_id,
            owner_principal_id=owner.principal_id,
            display_name="Persistent Berserker",
            definition=revisions.definition,
            starter_holdings=revisions.holdings,
            starter_loadout=revisions.loadout,
            initial_advancement_award=CharacterAdvancementAwardCreate(
                character_id=character_id,
                level_delta=build.level,
                source_kind=CharacterAdvancementSourceKind.CREATION,
                source_id=f"character:{character_id}:creation",
            ),
        ),
    )
    return repository, service, owner.principal_id, character_id


def _request(
    service: CharacterDirectoryService,
    owner_id: UUID,
    character_id: UUID,
    *,
    operation: CharacterEquipOperation | CharacterUnequipOperation,
    idempotency_key: UUID | None = None,
) -> CharacterEquipmentMutationRequest:
    snapshot = service.get_character_snapshot(owner_id, character_id)
    return CharacterEquipmentMutationRequest(
        idempotency_key=idempotency_key or uuid4(),
        expected_row_version=snapshot.character.row_version,
        expected_heads=snapshot.heads,
        expected_content_set_digest=service.content_system.content_set_digest,
        expected_ruleset_digest=(
            service.ensure_profile_settings(owner_id).ruleset_digest
        ),
        operation=operation,
    )


def test_equipment_mutation_contract_is_one_strict_discriminated_operation() -> None:
    item_id = uuid4()
    equip = CharacterEquipOperation(
        character_item_id=item_id,
        target_slot=WeaponSlot.MELEE_OFF,
    )
    unequip = CharacterUnequipOperation(character_item_id=item_id)

    assert equip.operation == "equip"
    assert equip.target_slot is WeaponSlot.MELEE_OFF
    assert unequip.operation == "unequip"
    with pytest.raises(ValidationError):
        CharacterEquipOperation.model_validate({
            "operation": "equip",
            "character_item_id": str(item_id),
        })
    with pytest.raises(ValidationError):
        CharacterUnequipOperation.model_validate({
            "operation": "unequip",
            "character_item_id": str(item_id),
            "target_slot": WeaponSlot.MELEE_OFF.value,
        })

    path = "/directory/characters/{character_id}/equipment"
    openapi_path = create_gateway_app().openapi()["paths"][path]
    assert set(openapi_path) == {"put"}


def test_character_sheet_equip_reuses_two_handed_conflict_rules_and_is_idempotent(
    tmp_path: Path,
) -> None:
    repository, service, owner_id, character_id = _seed(tmp_path)
    before = service.get_character_snapshot(owner_id, character_id)
    greataxe = _item(before.holdings.holdings.items, "weapon.greataxe")
    shield = _item(before.holdings.holdings.items, "shield.shield")
    assert greataxe.equipped_slot is WeaponSlot.MELEE_MAIN
    assert shield.equipped_slot is None
    request = _request(
        service,
        owner_id,
        character_id,
        operation=CharacterEquipOperation(
            character_item_id=shield.character_item_id,
            target_slot=WeaponSlot.MELEE_OFF,
        ),
    )

    after = service.update_character_equipment(
        owner_id,
        character_id,
        request,
    )

    after_greataxe = _item(
        after.holdings.holdings.items,
        "weapon.greataxe",
    )
    after_shield = _item(after.holdings.holdings.items, "shield.shield")
    assert after_greataxe.equipped_slot is None
    assert after_shield.equipped_slot is WeaponSlot.MELEE_OFF
    assert after.character.row_version == before.character.row_version + 1
    assert after.heads.holdings_revision == before.heads.holdings_revision + 1
    assert after.heads.definition_digest == before.heads.definition_digest
    assert after.heads.loadout_digest == before.heads.loadout_digest
    assert {
        item.character_item_id for item in after.holdings.holdings.items
    } == {
        item.character_item_id for item in before.holdings.holdings.items
    }
    assert (
        service.update_character_equipment(owner_id, character_id, request)
        == after
    )
    restore_request = _request(
        service,
        owner_id,
        character_id,
        operation=CharacterEquipOperation(
            character_item_id=greataxe.character_item_id,
            target_slot=WeaponSlot.MELEE_MAIN,
        ),
    )
    restored = service.update_character_equipment(
        owner_id,
        character_id,
        restore_request,
    )
    assert _item(
        restored.holdings.holdings.items,
        "weapon.greataxe",
    ).equipped_slot is WeaponSlot.MELEE_MAIN
    assert _item(
        restored.holdings.holdings.items,
        "shield.shield",
    ).equipped_slot is None
    repository.close()


def test_character_sheet_unequip_and_identity_fences_fail_closed(
    tmp_path: Path,
) -> None:
    repository, service, owner_id, character_id = _seed(tmp_path)
    stranger = repository.create_principal(
        PrincipalCreate(
            principal_kind=PrincipalKind.HUMAN,
            display_name="Stranger",
        ),
    )
    before = service.get_character_snapshot(owner_id, character_id)
    greataxe = _item(before.holdings.holdings.items, "weapon.greataxe")
    request = _request(
        service,
        owner_id,
        character_id,
        operation=CharacterUnequipOperation(
            character_item_id=greataxe.character_item_id,
        ),
    )

    with pytest.raises(CharacterDirectoryOwnershipError):
        service.update_character_equipment(
            stranger.principal_id,
            character_id,
            request,
        )
    with pytest.raises(ConflictError, match="content"):
        service.update_character_equipment(
            owner_id,
            character_id,
            request.model_copy(
                update={"expected_content_set_digest": "0" * 64},
            ),
        )
    with pytest.raises(ConflictError, match="ruleset"):
        service.update_character_equipment(
            owner_id,
            character_id,
            request.model_copy(
                update={"expected_ruleset_digest": "0" * 64},
            ),
        )

    after = service.update_character_equipment(
        owner_id,
        character_id,
        request,
    )
    assert (
        _item(
            after.holdings.holdings.items,
            "weapon.greataxe",
        ).equipped_slot
        is None
    )
    stale = request.model_copy(update={"idempotency_key": uuid4()})
    with pytest.raises(StaleVersionError):
        service.update_character_equipment(owner_id, character_id, stale)
    repository.close()


def test_character_sheet_rejects_unknown_or_incompatible_item_without_revision(
    tmp_path: Path,
) -> None:
    repository, service, owner_id, character_id = _seed(tmp_path)
    before = service.get_character_snapshot(owner_id, character_id)
    potion = _item(
        before.holdings.holdings.items,
        "consumable.potion_haste",
    )
    incompatible = _request(
        service,
        owner_id,
        character_id,
        operation=CharacterEquipOperation(
            character_item_id=potion.character_item_id,
            target_slot=WeaponSlot.MELEE_MAIN,
        ),
    )

    with pytest.raises(ConflictError, match="equipment"):
        service.update_character_equipment(
            owner_id,
            character_id,
            incompatible,
        )
    assert (
        service.get_character_snapshot(owner_id, character_id).heads
        == before.heads
    )
    unknown = incompatible.model_copy(
        update={
            "idempotency_key": uuid4(),
            "operation": CharacterUnequipOperation(
                character_item_id=uuid4(),
            ),
        },
    )
    with pytest.raises(ConflictError, match="character_item_id"):
        service.update_character_equipment(owner_id, character_id, unknown)
    assert (
        service.get_character_snapshot(owner_id, character_id).heads
        == before.heads
    )
    repository.close()


def test_equipment_commit_atomically_rechecks_the_deployment_lease(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repository, service, owner_id, character_id = _seed(tmp_path)
    before = service.get_character_snapshot(owner_id, character_id)
    greataxe = _item(before.holdings.holdings.items, "weapon.greataxe")
    request = _request(
        service,
        owner_id,
        character_id,
        operation=CharacterUnequipOperation(
            character_item_id=greataxe.character_item_id,
        ),
    )
    game = repository.create_game(
        GameCreate(
            created_by_principal_id=owner_id,
            scenario_kind="test",
            scenario_id="equipment-lease-race",
            display_name="Equipment Lease Race",
            creation_manifest={},
            ruleset_version="test",
            engine_version="test",
            content_digest=service.content_system.content_set_digest,
        ),
    )
    membership = repository.create_membership(
        MembershipCreate(
            game_id=game.game_id,
            principal_id=owner_id,
            role=MembershipRole.PLAYER,
            capabilities=MembershipCapabilities(
                may_control_entities=True,
            ),
        ),
    )
    real_mutation = service_module.mutate_character_equipment

    def acquire_lease_after_preflight(**kwargs):
        holdings = real_mutation(**kwargs)
        repository.acquire_character_deployment_lease(
            CharacterDeploymentLeaseCreate(
                character_id=character_id,
                game_id=game.game_id,
                membership_id=membership.membership_id,
            ),
        )
        return holdings

    monkeypatch.setattr(
        service_module,
        "mutate_character_equipment",
        acquire_lease_after_preflight,
    )

    with pytest.raises(ConflictError, match="active deployment"):
        service.update_character_equipment(owner_id, character_id, request)
    assert (
        service.get_character_snapshot(owner_id, character_id).heads
        == before.heads
    )
    repository.close()
