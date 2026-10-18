# Fresh anti-slop review of the 58 implemented spells

15 October 2026. Human-requested second critical review of the previous 36-spell batch (`c72980091a5`) and the following uncommitted 22-spell batch. All work remains in `/home/tommaso/.codex/worktrees/spells-rank-one-two/dnd_engine`, branch `codex/spells-rank-one-two`. No NDClient work or new commit was made for this review.

The fresh review found real defects that earlier green tests/reviews missed. Confirmed defects were repaired and retained as native behavioral regressions. Earlier PASS records remain historical evidence; this report records the later findings. No unresolved confirmed blocker remains from this finite review. “No finding” below means source/interaction review found no additional concrete problem; it does not mean every possible combination was executed.

Scope remains the approved [36-spell plan](plans/BG3_STYLE_RANK_1_2_SPELL_IMPLEMENTATION_PLAN_2026-10-15.md) and [22-spell plan](plans/SRD_LEVEL_4_9_22_SPELL_IMPLEMENTATION_PLAN_2026-10-15.md), including all 12 approved high-level summon bodies. Source preference, human exclusions and adaptations are unchanged. The low-level anti-slop reviewer, high-level behavioral/anti-OOP reviewer and independent plan-adherence tracker reviewed separate concerns and compared actual code/native results, without treating earlier passes as proof.

## Confirmed findings and repairs

| Severity | Affected content | Reproduced defect | Repair |
| --- | --- | --- | --- |
| P2 | Animal Friendship | A second caster replaced the first caster's charm. | Exact source-owned condition names with a stable display name; Charm Monster's inherited naming remains correct. |
| P1 | Searing Smite, Branding Smite, Ensnaring Strike | A canceled root EFFECT still executed the weapon attempt and reached hit-only payment. | Return a canceled effect before creating/resolving its attack. Upfront attempted-action costs still follow native interruption rules. |
| P2 | Hex, Hunter's Mark reapplication | A canceled EFFECT still committed the new quarry. | Admit/check the effect before committing prepared old/new condition changes; cancel unused prepared state through the existing finally path. |
| P2 | Hex, Hunter's Mark reapplication | Ending concentration during an accepted EFFECT left an orphan new quarry condition. | Recheck the exact live sustain's identity, applied/contributing state and caster ownership after admission and before commit. |
| P1/P2 | Moonbeam, Dancing Lights movement | Canceled follow-ups still changed their field/light anchors. | Admit/check the effect before relocation; retain accepted event causality. |
| P2 | Spare the Dying | A canceled EFFECT still stabilized the dying target. | Admit/check before calling native stabilization. |
| P2 | Plant Growth, ground Chromatic Orb, ground Acid Arrow | Canceled casts still created ground fields. | Check accepted EFFECT before attack-roll/surface work. |
| P2 | Phantasmal Force | A fully absorbed physical component could determine the next damage type instead of surviving elemental damage. | Allocate native flat reduction once in stable component order, then select the largest positive remaining component, keeping stable ties and own-tick exclusion. This matches the already approved Vampiric Touch accounting convention. |
| P1 | Resilient Sphere | Outside Shove moved its occupant; Help/Shake removed enclosed conditions through the boundary. | One passive external-contact capability at the existing physical-access check, plus the Sphere owner's native forced-movement veto. Self mundane items/movement, suppression and ordinary condition expiry/cleanup remain allowed. |
| P2 | Antilife Shell | Caster teleportation swept imaginary intervening cells and ended concentration. | Recognize the existing causal PortalTransferEvent and relocate through the native area operation without a physical sweep. |
| P2 | Antilife Shell | Translating a map-clipped footprint shrank the shell and could falsely eject initially enclosed edge occupants. | Recompute native geometry for actual movement sweep centers and use native move_zone for the final footprint. No pathfinder or field framework added. |
| P2 | Conjure Elemental: Air Myrmidon Tenacity | Natural-1 critical misses dealt no miss damage. | Include both native miss outcomes. |
| P2 | Conjure Elemental: Air Myrmidon Tenacity | Damage stayed four after Strength changed. | Use the approved max(current Strength modifier, 1) formula. |
| P1 | Dispel Evil and Good: Break Enchantment | A canceled EFFECT still cured Charm Monster and ended the sustaining ward. | Admit/check the effect before preparing/committing its exact removals. |
| P2 | Conjure Elemental, Planar Ally, Summon Dragon recipe module | A cold leaf import depended on installer-owned action/condition declarations already being installed. | Use the existing neutral behavior_content_ref and finite authored condition identities. No bootstrap/installer import added to the leaf. Fresh-process import followed by bootstrap verifies all 12 recipes resolve. |

A proposed additional Tenacity late-cancellation leak **did not reproduce**: an actual miss canceled at native EFFECT deals zero damage. That test remains; no speculative completion hook, new event bus or deferred attack framework was added. Native completion dispatch is unsuitable for a normal gameplay handler, so it was not used as an untested fix.

## Coverage: previous 36 roots

| Spell | Fresh disposition |
| --- | --- |
| Dancing Lights | Repaired canceled relocation; native regression. |
| Sorcerous Burst | No additional finding: bounded extra dice, criticals, element variants and documented forecast limit reviewed. |
| Spare the Dying | Repaired canceled stabilization; native regression. |
| Starry Wisp | No additional finding: object ownership, reveal/light and source-turn deadline reviewed. |
| Vicious Mockery | No additional finding: actual-roll consumption and suppressed deadline reviewed. |
| Animal Friendship | Repaired independent caster ownership; native regression. |
| Chromatic Orb | Repaired canceled ground creation; native regression. |
| Create or Destroy Water | No additional finding: rain leases, persistent water and removal branches reviewed. |
| Dissonant Whispers | Fresh suppressed-expiry and Heroism-prevention cases pass. |
| Divine Favor | No additional finding: weapon eligibility, component protection and critical delivery reviewed. |
| Divine Smite | No additional finding: automatic entitlement/toggle selection and hit payment reviewed. |
| Ensnaring Strike | Repaired canceled attack; save/tick/Help/opportunity-attack behavior reviewed. |
| Faerie Fire | No additional finding: cast-time recipients and separate reveal owners reviewed. |
| Goodberry | No additional finding: consumption, capacity, transfer/rest and suppression lifecycle reviewed. |
| Heroism | Fresh case clears Phantasmal Killer and prevents Dissonant fear. |
| Hex | Repaired canceled reapplication and owner loss; native regressions. |
| Hideous Laughter | No additional finding: immunity, agency, local attack advantage and recovery reviewed. |
| Hunter's Mark | Repaired canceled reapplication and owner loss; native regressions. |
| Protection from Evil and Good | Fresh case removes Fiend Charm Monster and retains Humanoid Charm Monster. |
| Ray of Sickness | No additional finding: attack/save separation, immunity and deadline reviewed. |
| Searing Smite | Repaired canceled attack; native regression. |
| Acid Arrow | Repaired canceled ground creation; miss-half, delayed tick and critical handling reviewed. |
| Branding Smite | Repaired canceled attack; native regression. |
| Calm Emotions | No additional finding: target filtering, purge and rage prevention reviewed. |
| Dragon's Breath | No additional finding: recipient actor versus retained caster/DC, costs and cleanup reviewed. |
| Flame Blade | No additional finding: exact item, spell attack, retirement and protection reviewed. |
| Flaming Sphere | No additional finding: autonomous body, Ram, aura, objects, trail and cleanup reviewed. |
| Magic Weapon | No additional finding: exact item, strongest bonus, transfer and path suppression reviewed. |
| Moonbeam | Repaired canceled relocation; initial exposure remains deferred until owner commitment. |
| Pass without Trace | No additional finding: nonstacking membership, movement and exact source cleanup reviewed. |
| Phantasmal Force | Repaired post-defense component selection; native regression. |
| Spiritual Weapon | No additional finding: retained attack values, independent lifetime and autonomous actions reviewed. |
| Glyph of Warding | No additional finding: payload branches, disarming before resolution, collateral and recovery reviewed. |
| Plant Growth | Repaired canceled creation; terrain composition and partial burning reviewed. |
| Revivify | No additional finding: eligibility, downed/dead branches and prepared relocation reviewed. |
| Vampiric Touch | No additional finding: own-component healing, mitigation, repeated costs and ownership reviewed. |

## Coverage: following 22 roots

| Spell | Fresh disposition |
| --- | --- |
| Charm Monster | Independent recipients, combat saves, immunity and damage break reviewed. |
| Aura of Life | Moving membership, pre-death-save healing and future maximum-loss prevention reviewed. |
| Phantasmal Killer | Recovery-before-damage, strongest overlap, source ownership and expiry reviewed. |
| Resilient Sphere | Repaired contact/forced movement; self items, suppression, existing DOT deadlines and cleanup freshly pass. |
| Vitriolic Sphere | Initial upcast damage, fixed residue and one-use deadline reviewed. |
| Antilife Shell | Repaired teleport and map-edge behavior; initial edge occupant remains enclosed. |
| Conjure Elemental | Independent lifetime/replacement; cold import and Tenacity repaired. |
| Dispel Evil and Good | Break Enchantment admission repaired; exact eligible-source cleanup reviewed. |
| Summon Dragon | Scaling/DC, independent resistance and separate free Breath cadence reviewed; cold import repaired. |
| Blade Barrier | Formation/entry/START cadence, terrain and concentration ownership reviewed. |
| Flesh to Stone | Stages, persistent completion, immunity and restoration reviewed. |
| Freezing Sphere | Launch, portable custody, clocks, suppression and retirement reviewed. |
| Irresistible Dance | Action/movement denial with preserved bonus actions/reactions reviewed. |
| Planar Ally | Approved bodies, real SRD spell loadouts and independent lifetime reviewed; cold import repaired. |
| Arcane Sword | Remote geometry, accuracy, costs and admitted anchor changes reviewed. |
| Delayed Blast Fireball | Original-caster growth, custody, ending and single detonation reviewed. |
| Forcecage | Formation admission, paid escape, boundaries and section destruction reviewed. |
| Feeblemind | Fixed scores, spell/item blocks, cures and GM recovery adaptation reviewed. |
| Holy Aura | Fixed recipients, qualifying hits, blindness ownership and shared ending reviewed. |
| Foresight | Attacks/checks/saves, surprise, Counterspell and retarget cleanup reviewed. |
| Weird | Retreat-compatible fear, recovery-before-damage and overlap reviewed. |
| Power Word Heal | Heal/cures, recipient preference and retained stand-offer lifecycle reviewed. |

## Coverage: 12 high-level bodies

All 12 numerical stat recipes were independently compared with the approved plan table, rather than using production BODIES as their own expected values. All 12 also have fresh exact normal/critical attack assertions. Fixed damage die faces are 2 in the table; Cambion uses its actual three SRD Scorching Rays.

| Body | Normal / critical damage | Other inspected behavior |
| --- | ---: | --- |
| Air Elemental | 10 / 18 | Jets, Shocked, conditional Multiattack dice. |
| Earth Elemental | 9 / 13 | Slam, seismic push, Mud, Trembling Legs. |
| Fire Elemental | 8 / 16 | Burning, fire patches, conditional dice. |
| Water Elemental | 12 / 20 | Fixed Slam component, cooling/Brittle, ice. |
| Air Myrmidon | 11 / 15 | Tenacity repairs, Vortex replacement, innate Invisibility. |
| Earth Myrmidon | 15 / 21 | Fixed nine component, paid Burrow, Muck. |
| Fire Myrmidon | 11 / 15 | Strike, Immolation ownership, reaction resource. |
| Water Myrmidon | 11 / 15 | Icicle, Vapours, Poisoned immunity. |
| Deva | 14 / 24 | Concussive Smash, revival resource, bound mace. |
| Djinni | 12 / 18 | Actual innate spells, independent Gales. |
| Cambion | 12 / 24 | Three real rays, source-specific Kiss prerequisite. |
| Draconic Spirit, slot 5 | 11 / 13 | Scaling, cadence, resistance lease, provenance. |

## Final validation

The retained new gameplay cases are [18 low-level regressions](../tests/engine/test_low_level_spell_review_regressions.py) and [41 high-level/body cases](../tests/engine/test_high_level_spell_review_regressions.py). They include failure reproductions, negative controls and additional numeric/interaction qualification; not all 59 cases represent a separate defect. The [cold-import regression](../tests/architecture/test_spell_catalog_composition.py) is a separate new architecture case. No temporary review test files remain.

Final qualification on the completed repair set:

- **483 passed in 149.91s**: both spell batches, all maintained new review cases, affected movement/standard-condition/summon lifecycle suites, both player spell-transport files and all three spell-progression files. Log: `/tmp/spell-58-review-focused-final.log`.
- **36 active architecture checks passed, 5 known legacy cases deselected, 30.95s**. Includes the new isolated-process recipe-before-installer case. Log: `/tmp/spell-58-review-architecture.log`.
- **92 Python diagnostics in 323 production files**, exactly matching the committed baseline's 92 diagnostics in 320 files, with **zero new diagnostics and zero unmatched baseline diagnostics**. All three new production modules are included. No checker configuration or ignores changed. Comparison: `/tmp/spell-58-review-pyright-comparison.json`.
- Final normal `git diff --check`: **PASS**. Static undefined-name checks and formatting were applied to the new review tests/new edited production modules.
- Independent closing reviews: low-level anti-slop **PASS**, high-level behavioral/anti-OOP **PASS**, plan adherence/report accuracy **PASS**. These follow the repairs and do not reuse the earlier broad PASS as proof.

Reproduce the combined acceptance from the worktree:

```sh
UV_PROJECT_ENVIRONMENT=/home/tommaso/.cache/dnd-engine/venv uv run --no-sync python -m pytest \
  tests/engine/test_bg3*.py tests/engine/test_high_level_spell*.py \
  tests/engine/test_low_level_spell_review_regressions.py \
  tests/player/test_bg3_spell_transport.py tests/player/test_high_level_spell_transport.py \
  tests/progression/test_bg3*.py tests/progression/test_high_level_spell_learning.py \
  tests/engine/test_misty_step.py tests/engine/test_standard_conditions.py \
  tests/engine/test_summoning_lifecycle.py -q --assert=plain --tb=short
```

The active architecture lane comprises `test_spell_catalog_composition.py`, `test_dependency_boundaries.py`, `test_action_discovery_requirements.py` and `test_ai_import_direction.py`. Its unchanged five legacy deselections are `test_engine_and_server_action_execution_share_the_core_dispatcher`, `test_game_import_does_not_load_ai_or_server_packages`, `test_neutral_symbols_have_one_canonical_leaf_owner`, `test_world_contract_dtos_are_not_reexported_through_api_models`, and `test_safe_leaf_modules_only_compose_declared_neutral_values`.
 Broader engine integration during this review passed **3,175 tests**, with the same **120 baseline deselections** and archived `test_solid_walls.py` collection ignore. This run preceded the last guarded reapply/Strength formula refinements; the final combined affected run qualifies the completed repair set. No full-repository-green claim is made.

Existing broad exclusions remain the prior documented door/legacy combat-log/propagation/replay cases in the implementation plans. Python typing is compared against the unchanged 92-diagnostic committed baseline, not described as a clean project. Approved fixed Forcecage forms, omitted Frozen transition, Feeblemind GM time recovery, Foresight Action adaptation, recipient stand preference and autonomous summon control remain deliberate limitations. Exhaustive spell combinations and optimal AI utility choices are not established by this review.
