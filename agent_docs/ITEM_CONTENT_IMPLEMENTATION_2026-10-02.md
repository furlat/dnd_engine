# Roster items: implemented first step

October 2, 2026. Implements the settled appearance/media portion of the
[full 165-record plan](ITEM_CONTENT_IMPLEMENTATION_PLAN_2026-10-02.md).

111 new appearance recipes reuse ordinary native bases: 102 existing-category
recipes, seven partial garments and two cloaks. Cloak uses the existing native
Cloak entity/slot; partial garments explicitly register at their legs layer within
the accepted body outfit. No weapon rules, armor grades or magical properties
were inferred from colors. Existing 205 ledger rows and original source metadata
remain unchanged. Production now has 78 categories / 316 variants, 98 hand
substitutions and 394 ground bindings.

235 shared original action sheets add 32,487,518 bytes. Every selected layer has
all 14 rig actions, original alpha and shadows. Colors remain palette swaps;
no recolored image copies or Idle substitutions. Local/private copies match.
The authoring converter validates through existing typed contracts; runtime does
not read the private bible. The original admission receipt is never overwritten.

The normal engine gallery records a real three-item transfer once and replays
both participants' received events in four cameras. Sword, waist and cloak leave
the first holder, appear on the floor once, and equip on body 2 after pickup.
The sword's existing fire coating follows its UUID; this demonstrates the existing
coating contract, not acceptance of a new roster enchantment. Real floor art is used.

Validation:

- Complete engine suite: 1,955 passed.
- Focused item, palette, transfer and definition checks: 31 passed.
- Scoped Pyright: 0 errors / warnings.
- Independent anti-slop and ECS/anti-OOP reviews: no blocking findings.
- Full renderer suite remains pending the concurrent spells lane's stable checkpoint.

Receipts: `.runtime/items-roster-20261002/engine-suite.txt`, `focused-checks.txt`,
`admission.json` and `review-recording.txt`. The two 19.8-second, 32 FPS recordings
are in `.runtime/items-roster-20261002/review/runs/20261002T161802Z-58c029/`.

The completed ownership supplement is reflected in the full plan. Missing bases,
remaining media, exact effect rules, ammunition/tool/focus/accessory representation
and fixed-holder loss remain explicit pending work; all 165 records are retained.
No NPC roster or condition/ability port is claimed complete. No Git commits made.

## Follow-up: reviewed next native slice

The human confirmed psychic weapons, delegated strong enhancement/damage balance,
rejected a separate firearm proficiency gate, confirmed existing melee/ranged
switching and deferred baked fixed-holder removal pixels. The full plan now
records these decisions and an exact actor-owned non-light offhand talent contract.
Fresh anti-slop and ECS reviews approve the revised plan; implementation review
also approves the isolated psychic/Maul definitions.

`roster_item_definitions.py` now defines five selected magical psychic weapons
(+2/2d6 for elite families, +3/3d6 for the ritual sword) using existing transforms,
plus an ordinary 2d6 Heavy/Two-Handed Maul. Historical art-derived necrotic riders
must not be stacked on top. No actor-dependent item scaling or new executor.
Twelve native composition/combat checks pass, including applied HP damage,
physical transfer and isolation from an unrelated weapon. Scoped typing is clean.
Exact Maul art and animated psychic effect transfer are not yet certified.
All six definitions are installed through the canonical builder. Actor-owned
UUID grants now admit one-handed non-light melee weapons through the same
eligibility query used by discovery and equip commands. Initial loadouts see the
grant before birth; multiple receipts remain independent. Revoking the last grant
uses existing inventory-only unequip events; a veto/full inventory retains both
grant and weapon. Attack validation, cost commitment and resolution recheck the
declared physical weapon and hand eligibility. No new damage/AC or action grants.
The selected left longsword now has one extra main/ground palette recipe and an
explicit Offhand1 substitution, using only already installed media. The final
review found that the talent also permits other authored one-handed melee items.
An explicit authoring-only hand table now binds all their categories/variants,
including psychic Longsword/Trident and aliases, to existing vendor offhand
sheets. These are disclosed length/head/tine silhouette approximations; native
rules are unchanged. Expanded eligibility is tested, not just baseline item slots.
Both reviewers approve the correction; no extra pixels were installed.

Final native slice validation:
- Complete engine suite: **1,969 passed** (226.61 seconds).
- Psychic/transfer/Maul/offhand native cases: **14 passed**.
- Offhand lifecycle plus exhaustive actor-expanded item renderer/palette/both-hand
  category and variant media cases: **15 passed**.
- Existing Haste/Slow/Extra Attack/Action Surge/progression suites: **242 passed**.
- Expanded Haste budget suite, including actor talent on/off across the same
  48 combinations and creature/object/mixed recipients: **352 passed**.
- Scoped native, renderer, converter and test typing: **0 errors / warnings**.
- Fresh anti-slop and ECS implementation review: no production blockers; their
  requested pre-birth disclosure, regrant and cancellation-cost checks are covered.

The broad renderer diagnostic finished **2,706 passed / 7 failed / 177 errors**.
Native item sources changed after it began; a separate spell bounds fix followed
its completion. It is not final combined acceptance. All 184 non-passing reports
match previously documented categories: 179 wall-module media registration,
two lifecycle Idle frame mismatches and three retained attack-field decodes.
Receipts: `combined-game-suite.txt`, `combined-game-classification.json`,
`native-slice-engine-suite.txt`, `native-slice-budgets.txt`,
`native-slice-talented-budgets.txt`, `talent-all-hand-checks.txt`,
`talent-all-hand-typing.txt`, `offhand-render-checks.txt` and both typing
receipts under `.runtime/items-roster-20261002/`. No unrelated fixes or Git
operations were performed. Remaining bases/accessories/ammunition/effect media
are still tracked in the complete queue; this is not the full character port.


## Complete remaining-record reconciliation

The roster author rechecked all nine historical gaps against this implementation;
`current-review.json` SHA `61d66023c9ba70b2f9142200c412c5d2d32956d2a16f5d91c7dd716257d38fbc`
remains the frozen study, not a runtime completion receipt. Offhand Longsword is
settled; Maul's mechanics are settled but exact art is absent. The seven ordinary gear records are now implemented under the human's simplified scope:

| Record | Implemented behavior |
| --- | --- |
| Musket | Existing ranged attack route, 1d12 piercing, 40/120 range, both ranged hands. No separate firearm proficiency. |
| Wand | Existing melee slot and ordinary 1d4 bludgeoning attack. |
| Banner | Existing melee route, 1d4 bludgeoning, both melee hands. |
| Back canister | Zero-AC backpack accessory; normal displacement, drop and transfer. |
| Saddle/tack | Transferable inventory possession, without mount benefits. |
| Crowbar | Existing melee slot and ordinary 1d4 bludgeoning attack. |
| Quiver | Zero-AC backpack accessory, separate from cloak, using original Bag2 banks. |

Ammunition/Loading, focus eligibility, tool-check bonuses, container contents and mount systems are explicitly deferred. Approximate donor geometry is disclosed in the passive appearance recipes; these are not claims of exact artwork. No extra execution route or special item class was added.

This accounts for all26 possession instances from the nine historical records.
Native backpack ownership and ordinary gear admission are complete; specialist
ammunition, focus and tool mechanics remain deferred. Fixed-holder removal pixels stay deferred.

## Ordinary gear completion checkpoint

The native backpack slot is published at birth and through normal equipment events.
Cloak uses a distinct render layer, so cloak and quiver retain separate possession UUIDs.
Two-handed ranged equipment reserves both ranged hands through the shared equipment footprint.
Mage Armor now uses the existing committed body-armor predicate, preserving cloth accessories.

- Full engine suite: **1,979 passed** (`ordinary-gear-complete-engine-final.txt`).
- Appearance admission: **112** records; the original intake and earlier receipts remain preserved.
- Original Bag2 banks: **14 pages / 2,025,461 bytes**, local/private SHA-256 verified.
- Native paired transfer review: `roster-backpack-transfer`, real wooden floor, 32 FPS, four cameras.

Receipts are under `.runtime/items-roster-20261002/`. This completes the ordinary gear amendment, not the later ability/condition/character port.

Final ordinary-gear renderer acceptance: **8 passed**, scoped typing **0 errors**.
Both paired native review clips pass all checks, with no presentation gaps:
http://127.0.0.1:8768/items-roster-20261002/backpack-review/runs/20261002T174959Z-7f890c/index.html
The clips last 23.4 seconds and preserve the standard four-camera engine format.
ECS reviewer approves after the Mage Armor regression fix; anti-slop reviewer
approves the bounded ordinary gear implementation with donor limitations disclosed.

## Complete appearance reconciliation and Maul binding

All113 proposed palette/layer recipes are now admitted, with zero new pages for
the final Maul. Its own native2d6 Heavy/Two-Handed definition uses the reviewed
original Melee11 hammer donor, explicitly approximate. Native and appearance
checks:14passed; scoped typing0errors. Both native Maul transfer clips pass:
http://127.0.0.1:8768/items-roster-20261002/maul-review/runs/20261002T175714Z-6ae5b3/index.html

The complete165-record reconciliation includes478 possession selections and48
canonical references, all constructed successfully. Per-possession psychic
powers preserve the original main/offhand appearances; cosmetic deduplication
does not merge the two sword power tiers. Independent anti-slop/ECS reviewers
approve. Ember/poison rule proposals and isolated emission media remain separate
from this appearance completion; no character port or all-effects claim.

Final exact authoring handoff:
`.runtime/items-roster-20261002/complete-item-roster-handoff.json` includes all150
characters,165 item records and478 possessions, including canonical references,
explicit native slots and category-qualified appearance selections. Five empty
possessions lists are retained explicitly. Final affected renderer tests:8passed.

## Final item rules and authoring handoff

Ember Longsword and Greatsword are magical native definitions composed from the
ordinary bases with 1d6 fire damage and no enhancement bonus. Two longsword
possessions retain distinct palette recipes while sharing mechanics. Basic Poison
uses the existing coat item/action/condition: one action, ten encounter rounds,
DC10 Constitution on an accepted creature hit, 1d4 poison on failure and zero on
success. It does not apply Poisoned and its die does not double on a weapon crit.
The handler follows the physical weapon UUID through drop/loot/equip; replacement
and expiry release both handler and owned damage contribution. Object attacks
retain ordinary weapon damage without an invented Constitution save. Existing
fire/lightning coats are unchanged.

Focused native checks: **50 passed**. Scoped typing: **0 errors / warnings**.
Complete engine suite: **1,990 passed** in212.92seconds. Both independent
anti-slop and ECS/anti-OOP implementation reviewers approve with no blockers.
Receipts: `final-items-engine-suite.txt`, `final-item-rule-checks.txt`,
`final-item-rules-typing.txt`, `final-item-handoff-typing.txt`,
`final-item-reviews.json` and `final-item-handoff-validation.json` under
`.runtime/items-roster-20261002/`.

`.runtime/items-roster-20261002/complete-item-rules-handoff.json` supersedes the
earlier authoring receipt for native rule selection, retaining all150 characters,
165 deduplicated records and478 possessions. All51 native references construct.
The poison consumer explicitly references a separate consumable; the handoff does
not silently pre-apply a condition. Original receipts remain preserved. No art,
animation or spell implementation changes were made in this final item slice.

This completes the item prerequisite lane. Character creation, abilities and
ability-derived conditions remain the later roster port; specialist ammunition,
focus, tool, container and mount mechanics remain deferred by the human.

## Existing-art material effects — human scope correction

No new weapon geometry, replacement sheets, isolated source FX or commissioned
artwork is authorized. The existing modular silhouettes and legal offhand donors
are retained. Their shape differences are accepted limitations, not artwork TODOs.
This supersedes the earlier exact-art/isolated-emission inventory.

`game/data/item-materials.json` provides frozen typed recipes selected by received
item behavior identity and damage type. Existing `item_material` handles both
held hands and ground; no actor-name lookup, live native registry, new executor
or condition-rendering edits. Additional Fire/Psychic/Lightning/Poison damage
facts and existing fire/lightning/Basic Poison coats select palette replacement
and bounded interior bloom. Coatings take priority80 over intrinsic priority40;
ties use semantic keys, independent of event order or UUID. Unknown effects keep
ordinary dye. Original dimensions, registration, source alpha, unmatched colors
and shadows remain unchanged. No halo extends across walls or changes occupancy.

The nine prior effect families are covered by shared material treatments: paired
psychic scimitars, psychic greataxe, trident, longsword and greater longsword;
Ember longswords A/B and greatsword; Basic Poison on the silver longsword. Exact
item UUID/effect state follows floor and recipient presentation. Poison cleanup
removes its material; intrinsic properties remain. These are static shaders/color
treatments, not new animated flames, light sources or damaging auras.

Remaining separate work: character/ability/condition authoring and human-deferred
fixed-sheet equipment/corpse removal. Body rituals, guard accents and blue body
sparks remain actor-owned. Specialist ammunition, focus, tool, container and mount
mechanics remain deferred. No outstanding replacement-weapon art request.

Material-only acceptance: **37 renderer/replay checks passed**, scoped typing
**0 errors**, and both anti-slop and ECS reviewers approve. Six normal paired
engine gallery clips pass in four cameras at32FPS using the real wooden floor:
`.runtime/items-roster-20261002/material-review/runs/20261002T190226Z-88cffd/`.
Actual held-frame inspection confirms violet material after transfer. No native
rule changes were needed; the complete engine1,990-pass receipt remains applicable
to native item rules. No new sprite pages or packed artwork bytes were added.

Current complete handoff: `.runtime/items-roster-20261002/complete-item-materials-handoff.json`.
Earlier receipts remain preserved. This receipt adds the existing-art policy and
material-document reference to the same150/165/478 native selections.
