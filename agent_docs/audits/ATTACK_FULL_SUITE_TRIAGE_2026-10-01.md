# Attack refactor full-suite triage — October 1, 2026

This records observed failures, not a claim that the full suite passes. The full
run uses `tests --continue-on-collection-errors --assert=plain -q --tb=short`.
Plain assertions avoid enormous recursive entity representations on failures.
The run finished at `/tmp/attack-full-suite-final.txt`; the original
collection transcript is `/tmp/attack-full-collection.txt`.

**Final full-run result: 6,161 passed, 338 failed, 146 errors, 1 warning in
39 minutes 39 seconds.** Errors comprise 72 collection failures and 74 setup
failures (64 area-scene, 8 control-projection, 2 interruption-replay). Subsequent
focused passes below are separate evidence, not an arithmetical replacement for
a full rerun. The [integrity review](../APP_INTEGRITY_REVIEW_2026-10-01.md)
classifies wider backend/app issues for discussion; the approved attack plan
continues per the user's clarification.

## Refactor failures found and corrected

| Failure | Cause and correction | Verification |
|---|---|---|
| Class-feature metadata/docstring checks | The Extra Attack marker moved from fighter to conditions, and thin attack variants lost field descriptions. Restore descriptions, follow the marker's real owner, and distinguish `ClassVar` execution policy from Pydantic model fields in the existing architectural check. | All 15 source-model hygiene tests pass. |
| Weapon-template lifecycle expectation | The new ordinary unarmed fallback deliberately retains `Attack_MELEE_MAIN` without a weapon. The existing fixture now checks unarmed source metadata before equip and after removal, retaining its equipped-weapon checks. | Focused lifecycle test passes. |
| Sanctuary permits Fire Bolt without its Wisdom gate | The guard selected only `ENTITY`/`MULTI_ENTITY`; Fire Bolt now has the shared creature-or-object target mode. Extend that selected-target guard while retaining the recipient's harmful-effect check. | All 28 Sanctuary contract tests pass, including blocked and allowed Fire Bolt attempts. |
| Twinned Spell silently stops modifying Fire Bolt | The existing single-recipient eligibility check excluded the new target mode. Admit it to the existing creature-pair transformation; no other spell gains object admission. | New direct level-3 Sorcerer cast damages both selected creatures, spends one action and one sorcery point, and removes the override. All 27 direct Sorcerer progression tests pass. |
| Remote lever cannot actuate linked light/door | New universal source-item reach admission rejects the distant linked item's nested action. Explicit controller/link admission now preserves remote actuation without granting authority merely from event parentage. | ECS owner's 73 controls, plates and spell-device checks pass, including invalid link/controller and movement-after-commit rejection. |
| Legacy spellcasting tutorial stops before exercising spells | Its reset helper references the removed entity-position registry, and its factories never deploy actors. Migrated only those fixtures to existing runtime reset and composed/deployed entity helpers. | All 17 current spellcasting tutorial checks pass. |

The root full run started before several corrections; an old-process failure
must be paired with the explicit focused rerun above. Scoped typing for the
economy documentation, source-model check and migrated lifecycle fixture is
clean.

The added Twinned regression has no typing diagnostics. Checking its entire
pre-existing progression test module additionally reports 38 unrelated missing
subtype refinements in older tests; the production Sorcerer/abjuration modules
are checked separately. No blanket ignores were introduced.

The native target-mode scan covered shared action admission, discovery,
execution, spell recipient facts, Sanctuary, metamagic and AI allocation.
Remaining multi-only branches implement repeated target allocation/convolution;
they must not be widened into a second object attack path.

## Final approved-plan corrections after scope clarification

- Fireball's custom breach loop now runs only in effective `POSITION_AOE` mode;
  explicit selected-recipient overrides use shared application. Full override,
  spell-family and native breach files: **49 passed**.
- Fireball's parent log already contained correct isolated target branches plus
  Ashen residue entries. The test now validates each category, exact HP/save/damage
  and no cross-target descendants without changing logging: **4 passed**.
- The unchanged canonical generator refreshes the strict event wire manifest,
  including new attack contacts, source types and AreaReach dependencies. Real
  attacks and spells survive JSON decoding after runtime reset: full wire and
  cold timeline lane **29 passed**; test-module typing clean.
- Obsolete active AttackObject icon rows and documentation were removed without
  regenerating unrelated icon content. Eleven separate missing icon dispositions
  remain open in the wider integrity report.

Evidence: `attack-final-fireball-override.txt`, `attack-final-event-lifecycle.txt`,
`attack-wire-complete.txt`, `attack-wire-typing.txt` under the retained validation
directory. None of these runs replaces the completed full-suite failure totals.

## Collection blockers outside the attack change

The completed collection attempt found **6,551 tests and 72 collection errors**.
Every collection error is an import of previously removed content/server APIs;
none references removed `AttackObject` or a missing new attack module.

| Missing API | Affected modules |
|---|---:|
| `dnd.core.senses` | 32 |
| `dnd.content_system.item_bindings` | 16 |
| `dnd.core.progression.character_ruleset_digest` | 9 |
| `dnd.core.content.item_definitions` | 3 |
| `dnd.content_system.builtin_character_builds` | 3 |
| `dnd.content_system.character_build_validation` | 2 |
| `ItemContentRefSnapshot`, `dnd.player_character_body`, old `armors`, `weapons`, `apparel_presets`, `classes.content_factories`, `AuthoredBehaviorAttribution` | 1 each |

These include production adapters that still import removed modules, not only
stale test imports. Examples are `server/world_contracts.py:17` (senses),
`server/world_projection.py:14` (item bindings),
`server/game_directory/contracts.py:24` (ruleset digest), and
`server/game_creation_composition.py:10` (character builds). The cold-start spell
catalog architecture test reaches the same `server/world_contracts.py` senses
failure. The retained in-process engine tests collect past these adapters.
No compatibility shims were added. The exact grouped module inventory is saved
in `/tmp/attack-collection-classified.json` for this run.

## Other reproduced test debt

- `test_content_recovery_cr0_evidence.py` freezes obsolete source bytes/counts:
  only the current icon-bindings and SRD-coverage artifact hashes differ; the
  current ledger has 178 playable, 5 partial, 742 missing versus its frozen
  177/5/743; structural typed definitions are 11 rather than 10. These historical
  evidence assertions were not rewritten to mask differences.
- `test_content_recovery_cri_direct_items.py` expects no window family. Its exact
  inventory is missing the 19 previously integrated window wall/insert IDs;
  there are no expected IDs absent from actual public builders. This is unrelated
  environment-content expectation drift, not loss of registered items.

## Completion boundary

The complete current `tests/engine` rerun after the corrections passes:
**1,775 passed in 198.18 seconds**, recorded in
`/tmp/attack-engine-postfix.txt`. This rerun uses the installed native content,
real action/effect paths and the corrected lever/Sanctuary code. It does not
replace the separate whole-project run below.

The full-suite result is recorded above. It failed and remains a required repair
discussion; focused passes are not a replacement for it. The earlier owned
economy matrix/progression lane passed 269 tests, including the complete
Slow/Haste/Extra Attack/Action Surge Cartesian cases across creature, object and
mixed targets, plus resource ordering and cancellation checks.
