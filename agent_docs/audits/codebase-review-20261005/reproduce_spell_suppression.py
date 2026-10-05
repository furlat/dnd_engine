"""Read-only production-source audit probe; run from the repository root.

PYTHONPATH=. .venv/bin/python .runtime/codebase-review-20261005/reproduce_spell_suppression.py

Guiding Bolt and Antimagic Field use real spell actions. Shield uses the same
ShieldBuff condition created by its reaction handler, installed through the
public condition owner; this probe does not exercise reaction selection.
All runtime registries are cleaned in finally. No source or test files change.
"""

from dnd.content_system.bootstrap import bootstrap_content_system
from dnd.content_system.runtime import SERVER_CONTENT_SYSTEM_RUNTIME
from dnd.core.dice import fixed_dice_faces
from dnd.entity import Entity
from dnd.spells.abjuration import AntimagicField, ShieldBuff
from dnd.spells.evocation import GuidingBolt
from tests.engine.support import reset_combat_state
from tests.manual.spell_regression_support import (
    create_spell_regression_actor,
    reset_spell_regression_arena,
)
from tests.manual.test_remaining_spell_legacy_contract import (
    _force_spell_attack_hit,
    _remove_spell_attack_modifier,
)


def main() -> None:
    SERVER_CONTENT_SYSTEM_RUNTIME.install(bootstrap_content_system())
    reset_spell_regression_arena(18, 8)
    try:
        caster = create_spell_regression_actor(
            "caster", (2, 3), "heroes", spell_slots={1: 1}
        )
        target = create_spell_regression_actor("target", (7, 3), "monsters")
        field_caster = create_spell_regression_actor(
            "amf", (7, 4), "monsters", spell_slots={8: 1}
        )
        Entity.update_all_entities_senses(max_distance=90)
        hit_modifier = _force_spell_attack_hit(caster, target)
        try:
            with fixed_dice_faces(10, 3, 3, 3, 3):
                guiding = GuidingBolt(
                    source_entity_uuid=caster.uuid,
                    target_entity_uuid=target.uuid,
                    cast_at_level=1,
                ).apply()
        finally:
            _remove_spell_attack_modifier(caster, hit_modifier)
        assert guiding is not None and not guiding.canceled
        mark = target.active_conditions["Guiding Bolt"]

        shield = ShieldBuff(
            source_entity_uuid=target.uuid, target_entity_uuid=target.uuid
        )
        applied = target.add_condition(shield)
        assert applied is not None and not applied.canceled and shield.applied
        field = AntimagicField(
            source_entity_uuid=field_caster.uuid, cast_at_level=8
        ).apply()
        assert field is not None and not field.canceled
        print("guiding_bolt_cast_success:", not guiding.canceled)
        print("antimagic_field_cast_success:", not field.canceled)
        print("guiding_bolt_magical_origin:", mark.magical_origin)
        print("guiding_bolt_active_inside_field:", mark.contributions_active())
        print("shield_suppressed_inside_field:", not shield.contributions_active())

        target.on_turn_start()
        print("shield_present_after_its_next_turn_start:", "Shield" in target.active_conditions)
        field_caster.remove_condition("Concentrating")
        print("shield_present_after_field_ends:", "Shield" in target.active_conditions)
        print("shield_active_after_field_ends:", shield.contributions_active())
    finally:
        reset_combat_state()
        print("runtime_cleanup_completed: True")


if __name__ == "__main__":
    main()
