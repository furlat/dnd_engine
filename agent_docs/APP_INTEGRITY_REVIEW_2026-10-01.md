# Game app integrity: failures and decisions before further fixes

October 1, 2026. **Additional app repairs require discussion; the approved attack
implementation continues.** The user clarified that the whole application's
integrity is our responsibility and asked to discuss additional fixes, especially
backend changes. They subsequently clarified that this does not stop completion
of the approved attack plan. Attack-plan regressions remain implementation work;
the broader server/content migrations below are findings for discussion. This
document does not authorize those additional migrations.

**Scope correction after the user's review:** the old HTTP/session/replication
server and its durable-character service were already retired. This is explicit
in `RECOVERY_PLAN.md` and
[the September 21 test disposition](retired_server_tests/2026-09-21/README.md).
The current application is the in-process `game` client. The earlier recommendation
to prioritize restoring server transport/persistence was incorrect. Failures in
those retained modules do not establish defects in the current game and do not
authorize rebuilding the retired server. Keep their evidence separate from active
native/gameplay failures. Historical scenarios also need a current-content
disposition rather than automatic restoration.

**User disposition after reviewing the findings:** historical scenario content
should be redesigned around worthwhile gameplay and current environments; restoring
the old scenarios is not itself a requirement. Icon coverage belongs to frontend
authoring and the future Pygame UI discussion, not engine acceptance or the list
of missing gameplay features. Preserve useful native assertions independently of
these old content and presentation expectations.

## What actually ran

The full `tests` run completed in 39 minutes 39 seconds:

- **6,161 passed, 338 failed, 146 errors, 1 warning.**
- The errors comprise **72 collection errors** and **74 runtime setup errors**.
- A separate current `tests/engine` rerun passed **1,775 tests**.
- The full process loaded code before several corrections. Current focused
  reruns resolve some of its failures; subtracting them from the total would
  not constitute a new full-suite pass.

The full historical repository collection is **not green**. A passing engine
subset does not certify the entire active game/replay suite. Retired server
startup is not an acceptance requirement for the current in-process application.
“Preexisting” and “outside the attack refactor” identify provenance, not reasons
to disregard a failure.

Raw evidence is preserved under `.runtime/attack-review/validation/`:
`attack-full-suite-final.txt`, `attack-final-nodes.json` (all 338 failed and 146
error node IDs), `attack-failure-blocks.json`, and
`attack-collection-classified.json`. The original collection attempt found
6,551 tests; the completed run's own result above is authoritative for that run.

## Confirmed production defects and contract breaks

| Finding | Evidence and consequence | Proposed repair to discuss |
| --- | --- | --- |
| Fireball ignored an effective target-mode override | `test_position_aoe_to_multi_entity_affects_only_selected_targets` selected two recipients; the new Fireball area loop also processed an unselected bystander. Dice exhaustion exposed the extra application. | **Fixed within the approved plan:** staged breach only runs for `POSITION_AOE`; other modes use shared selected-target application. Override, spell-family and staged-breach suite: 49 passed. |
| Generated event contract rejected real events | The stale manifest rejected current attack/source/contact fields and lacked AreaReachEvent entirely. It also contained older accumulated model drift. | **Completed through the approved serialization work:** regenerate with the unchanged canonical generator and retain strict validation. Three real discovered object-attack/Fire Bolt/breach cases pass JSON decoding after runtime reset; complete wire/timeline verification is recorded in the implementation report. Older server DTO/persistence migration remains separate. |
| Server/app adapters still import removed APIs | Collection fails on removed senses, item binding, character build and ruleset-digest APIs. Examples: `server/world_contracts.py`, `server/world_projection.py`, `server/game_directory/contracts.py`, `server/game_creation_composition.py`. These are production imports, not merely test imports. | First establish supported runtime entrypoints and durable character/scenario contracts. Separate moved imports from transport/persistence migrations; preserve supported semantics and verify startup and real encounter/action/replication. Do not restore empty compatibility modules. **Not fixed.** |
| Scenario/content composition is inconsistent | Retained scenarios reference missing `creature.player.fighter` / `creature.player.sorcerer` definitions. Other paths call `bind_runtime_behavior` without its required `current_binding`. Worker startup also fails. | Trace supported scenario and character construction through the current content pipeline. Establish which IDs remain supported and which were intentionally retired before changing scenarios or public contracts. **Not fixed.** |

The server rows above describe retained legacy code, not required current-game
repairs. Current scenario consumers must be assessed separately: scene content
can be replaced while native composition and gameplay coverage remain required.

**Frontend icon authoring/validation drift; excluded from engine requirements.** The
ledger lacks 11 current definitions. Closure validation runs in tests; runtime
lookup falls back to authored icons. Seven missing definitions name icons absent
from the pinned index; four explicitly have no icon. The user assigns this to
frontend/UI work: it is not a missing engine feature and icon completeness must
not gate engine correctness. A blind regeneration would restore hundreds of retired
rows because the ledger and active generated selection differ. Retiring the
obsolete `action.attack_object` row is the bounded attack-plan cleanup, separate
from this missing-content review.

**Touch targeting research (October 1).** The Grease entry assertion and both
Darkvision/True Seeing ally-in-darkness assertions reproduce in isolation
(three tests failed). The latter two return `Target not visible`: both spells
explicitly require a visual contact before checking their five-foot reach.
The user requested BG3-like close-range targeting. BG3's documented
[Blinded condition](https://bg3.wiki/wiki/Blinded_(Condition)) caps attacks and
spells at ten feet; [Darkvision](https://bg3.wiki/wiki/Darkvision_(spell)) retains
its five-foot melee range. This supports investigating contact targeting rather
than treating the sense-grant effects as absent. Darkness and Blinded are not
interchangeable in BG3, and these sources alone do not establish every blind
touch/invisibility interaction. No targeting or spell implementation was changed
during this research.

**Native spell repair follow-up:** the Grease failure was a fixture entering
`(5,6)` outside its actual ten-foot square. The test now proves that movement
harmless, then verifies entry at `(4,5)`; Grease production behavior is unchanged.
Darkvision and True Seeing now opt into shared five-foot contact admission,
including deployment, layer, relationship, hidden/invisible and physical hand
passage checks. Their retained regressions use current sensory observations
rather than retired tile-light/contact APIs. See the
[bounded delivery](SPELL_FIRST_DELIVERY_2026-10-01.md) for validation and scope.

**Retired transport/persistence, if revisited, need more than import replacements.** Current item
snapshots carry `item_id`; current behavior bindings carry `behavior_id`,
`provided_by_id` and `origin_root_id`. Several production consumers still require
deleted recipe/runtime bindings and references. Do not fabricate hashes or restore
those bindings to satisfy them. `CharacterItemV2` already retains durable identity,
charges, damage and equipment, but settlement still expects V1 and the character
definition still has legacy recipe references. Define the intended migration,
preserving acquisitions/losses, revisions, compare-and-swap and disclosure, before
changing settlement, profiles or client schemas. None of that work is required
merely to remove retired-server failures from the current game's status report.

**Current character persistence is unfinished as a playable feature.**
`CharacterBuild` provides passive authored creation input and the direct
`prepare_character`/`create_character` path. `CharacterItemV2` has a tested JSON
round-trip for direct item identity, charges and damage, but its full persistence
consumers remain in retired server modules. `game.session.create_session` resets
the runtime and creates fresh premades or a selected authored encounter;
`close_session` releases controllers/entities. There is no current-game path
which saves a progressed runtime character and reloads it after restart.
Saved player-event replay supports viewing history; it does not reconstruct a
playable character with restored handlers, resources and mutable inventory.
Read-only verification after this clarification: direct character-build and
durable-item/proficiency tests passed **21 tests**. The item test verifies JSON
identity/charge/damage round-trip; it is not an end-to-end character save/resume
test. No persistence or server implementation was changed.

## Failures requiring contract inspection before choosing a fix

**Fireball combat-log hierarchy: diagnosed.** A real three-target cast has one
root callback, three correct target branches, and 49 additional Ashen residue
condition entries. Logless stages already flatten correctly. The target-only
count assertion conflated target logs with non-target residue logs. Preserve the
existing log behavior and verify the three isolated target branches explicitly.
Suppressing or aggregating residue log noise would be a separate UI decision.
The full event-lifecycle file now passes four tests with production logging
unchanged; target isolation, saves, HP and residue counts are all asserted.

**Subjective spatial-effect log policy.** The neighboring log projection suite
reports two failures: the policy set lacks `CombatLogEntryType.SPATIAL_EFFECT`,
and a spatial-effect entry is dropped when the test expects a scrubbed entry.
This requires defining its disclosure policy before implementation; it is not
repaired by merely adding the enum to a set. This particular policy is in the
retired `server/combat_log_projection.py`; it is not a demonstrated active-game
log failure. No policy change was made here.

**Connected propagation versus an old occlusion fixture.** The remaining spell
test puts a single blocking tile between Fireball and a target, leaving a route
around it. It expects the older straight-line occlusion outcome; connected
propagation now reaches the target around that tile. The previously agreed
propagation rule favors a fixture with an actually sealed barrier, but this
behavioral discrepancy is recorded for discussion rather than silently rewriting
the expectation.

**Reset/isolation failures.** Content-pack loader/CLI checks encounter live
registries where a cold runtime is required. Several legacy tests still reset a
removed `_entity_by_position` registry or never deploy their actors. Establish
whether each failure is fixture cleanup, production lifecycle leakage or test
order dependence. Preserve the cold-runtime requirement and isolation checks.

**Content inventories and archived evidence.** Tests freeze old counts, exact
source hashes, old roster inventories and previously exported AI traces. One
inventory omits 19 already integrated window IDs; historical recovery evidence
also has changed source counts/hashes. Missing AI trace files are a separate
artifact problem. Determine which assertions describe live supported content
and which protect archived evidence. Do not rewrite expected hashes or remove
assertions merely because current output differs.

## Clearly identified fixture and expectation migrations

These are candidates for test repair, provided the same observable behavior is
still exercised:

- Required item IDs omitted by raw Weapon/BaseItem fixture construction.
- Removed GridMap registration/set-tile APIs and direct registry resets.
- Entities composed but never deployed before movement/attacks.
- Fire Bolt assertions still expecting `ENTITY` after its approved
  creature-or-object target mode.
- Fixed dice streams that assumed Fireball never rolls damage for objects.
- Destruction tests expecting the removed object-only body gesture instead of
  the shared attack contact, while retaining pixel/seek/visibility checks.

An exception message alone does not prove that every test in its family is stale.
After setup is repaired, execute the original behavioral assertions to discover
any underlying defect.

## What changed before the stop instruction

The attack implementation and earlier fixes remain in the working tree; they
have not been reverted. Their record is in
[the attack implementation report](ATTACKS_AND_DESTRUCTIBLE_OBJECTS_IMPLEMENTATION_2026-10-01.md).

The latest production correction before the stop supplied the retained actor
alongside a canceled spell's attempted contact; interruption playback otherwise
raised a KeyError. The already running control/interruption/breach/object rerun
finished **36 passed**. No Fireball override, wire-contract, server-adapter or
scenario repair was applied before the next user clarification. After that
clarification, only the approved-plan override and generated event contract were
completed. Server-adapter/scenario repairs remain unimplemented.

Immediately before the stop, fixture edits had also been made in these files:

| File | Existing change and validation boundary |
| --- | --- |
| `tests/manual/test_126_two_weapon_fighting_legacy_contract.py` | Required item IDs and real composition/deployment; paired with inventory checks, 26 passed. |
| `tests/manual/test_131_inventory_use_actions_legacy_contract.py` | Fire Bolt target-mode expectation; cannon targets the existing distant recipient instead of its own nearby area. The old selection correctly destroyed the cannon under the approved new Fireball rule. Included in the 26 passes. |
| `tests/manual/test_126_action_override_runtime.py` | At the stop: 33 passes and 2 failures before the last expectation edit. After clarification, the target-override fix and this full file pass within the 49-test run above. |
| `tests/manual/test_14_spell_families.py` | At the stop: 13 passed, 1 stale printed target-mode expectation. After clarification, that expectation was migrated; the full file passes within the 49-test run. |

The proposed broad adapter work performed **no commands or edits** before its
interruption. Icon cleanup also made **no writes**: a pre-write consistency guard
failed, exposing the generator/ledger drift. The subsequent clarification resumed
approved attack-plan completion, including bounded removal of its obsolete icon
row; broader adapter/persistence and icon-content work remain read-only.

The final wire/timeline run passed **29 tests**, including three new real native
object-attack/Fire Bolt/breach records decoded after runtime reset. The existing
movement fixture now explicitly composes and deploys its Goblins before moving;
its original movement/save assertions are unchanged. The generated manifest
comes from the unchanged canonical generator, with no permissive serializer or
new runtime reconstruction. Test-module typing is clean. This is current-contract
validation, not certification of older versioned archives or the deferred server
DTO/persistence consumers.

## Corrected discussion boundary

The approved attack corrections are complete. Retired server restoration is not
the next task. Distinguish active engine/gameplay regressions, historical scenario
content to replace, stale fixtures, and explicitly retired protocol tests. Keep
native assertions from mixed historical tests even when retiring their HTTP parts.

The user's current question is whether character persistence is a missing active
feature: the answer is yes at the end-to-end save/resume boundary, despite usable
creation and item-record foundations. Discuss that requirement separately from
reviving the old repository/profile/settlement service. No implementation is
authorized by this finding alone.

Use the same anti-slop and ECS reviewers for the proposed fixes. Keep native
rules authoritative, event records passive, authoring data explicit, and imports
acyclic. The user decides the additional app-repair steps after this discussion.

Independent documentation reviews: anti-slop and ECS approved these boundaries
with the icon classification, log diagnosis and persistence-scope clarifications
recorded above.
