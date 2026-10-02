# Item authoring prerequisites implemented

October 2, 2026. Human-approved scope:
[items prerequisites](ITEMS_MODULE_PREPLAN_2026-10-02.md). Independent anti-slop
and ECS/anti-OOP reviewers approve the corrected implementation. This prepares
existing mechanics and presentation for content authoring; it does not author
the 150-character roster.

## Native ownership and creation

`DIRECT_ITEM_BUILDERS` remains the sole canonical dispatch: 289 item IDs, including
47 cold weapon definitions and 64 wearables. Definitions have no live identity or
subscriptions. Pure functions in `dnd/content/items/item_composition.py` return
new definitions; `materialize_item_definition` creates physical copies using the
existing native lifecycle.

```python
from dnd.content.items.authored_item_definitions import AUTHORED_WEAPON_DEFINITIONS
from dnd.content.items.item_composition import named_item, with_extra_damage, with_weapon_bonus
from dnd.core.creature_types import DamageType
from dnd.core.item_properties import AdditionalDamage

definition = with_weapon_bonus(AUTHORED_WEAPON_DEFINITIONS["weapon.longsword"], bonus=1)
definition = with_extra_damage(definition, packet=AdditionalDamage(6, 1, DamageType.FIRE))
definition = named_item(definition, item_id="weapon.example_flame_longsword", name="Flame Longsword")
```

Register deliberately authored variants through the existing builder table.
Applying +2 after +1 replaces the bonus; distinct damage packets coexist and
exact duplicates fail. Wearer bonuses replace the same authored target. Shared
composers handle wearer bonuses, weapon-scoped unseen strikes and armor penalties
with exact modifier/handler removal handles. The canonical dagger/staff/crown/armor
builders no longer require special subclasses. Equipment definitions reject unsupported stack
authoring instead of silently discarding it. Numeric enhancements do not silently
change native magical identity or magical attack provenance.

Equipment and environment objects retain the existing BaseItem capabilities:
inventory, equipment, floor placement, optional health, use actions, physical
support, destruction and remnants. Existing environment profiles and spell-owned
construction systems keep their responsibilities; no new universal item model,
effect interpreter or second registry was introduced.

## Accepted transfer before mutation

Inventory pickup and floor equipment removal respect spatial admission vetoes.
Drop, unequip and displaced equipment storage admit destination placement/capacity
before clearing membership. Invalid or newly occupied floor destinations reject
without losing the source item. PickUp reports rejected transfer correctly. Drop
uses existing inventory action discovery, with exact selected item UUID and no
invented charge cost.

Stack compatibility checks recipe/appearance and live state. Condition/handler,
health, altered integrity, remnant, support or spent-charge state cannot disappear
through a merge. Accepted merges publish exact surviving counts/identities.
Foreign transfers of equipped gear require ordinary accepted source unequip;
source vetoes cannot be bypassed by a recipient's inventory or equipment.

Containers preserve rejected spill contents in their ordinary destroyed wreck.
Existing LootAll can recover retained contents after admission succeeds. No
separate debris inventory or resurrection of the intact container is needed.

`ItemLocationStateEvent` records accepted destination state. The narrow
`ItemHoldingsReleasedEvent` records accepted cross-owner source removal with only
former owner/container and item UUID. This lets an observer lose their known item
without receiving hidden recipient identity or holdings. Same-owner and rejected
transfers emit no release. Existing actor folding handles this fact for native
knowledge, interval replay and received player streams. Normal equipment/location
event ordering is preserved.

## Presentation and private media

`game/data/item_appearances.json` contains 42 explicit hand substitutions and 282
ground appearance bindings. Variant IDs remain qualified by category/hand.
Six legal off-hand families retain the existing Attack5 gesture and timing while
sharing ordinary attack effects. Their reused geometry remains an explicit visual
approximation; color does not alter rules.

Ground equipment samples isolated original frames with authored camera rows,
pivots, palette color, scale and contact shadow. The explicit 64-pixel source tile
registration shares the held rig's conversion to 128-pixel game tiles. Apparel can compose separated layers.
Existing paving, floor lighting and selection apply; multiple items in one cell
are independently selectable through the existing public Tab/Enter target chooser.
Floor snapshots retain disclosed quantity and pickability. No collision geometry
is inferred from the PNG.

Native item effects retain exact owning item/provider identity and phase facts.
Existing coating equipment modifiers follow item UUID through main/off-hand,
drop, transfer and expiry. Static damage riders remain on-hit facts rather than
invented passive glows. Replay reads received event values, never a live inventory.
Hand/ground/material bindings remain public data suitable for a future TS client.
Disclosed rig layers retain their owning item UUID. Item color and coating use
reviewed source palette zones, preserving unmatched material colors and alpha;
they do not multiply source pixels by the requested color.

The complete original archive is preserved in the private source repository.
The importer installs 645 unchanged selected sheets, 86,538,120 bytes, with exact
SHA-256 receipts in the private source directory and production manifest. Pixels
remain ignored by this code repository. [ASSETS.md](../ASSETS.md) records paths and
import command. These include the existing off-hand Attack5 Slash1/Slash2 media.

## Validation

Results and commands are saved under `.runtime/item-prerequisites-20261002/` and
`.runtime/items-module-20261002/`.

| Check | Result |
| --- | --- |
| Complete `tests/engine` | 1,955 passed |
| New composition/transfer plus equipment replication regressions | 28 passed |
| Feedback material/pickup/appearance regressions | 28 passed, including both modular bodies |
| Independent hidden/visible transfer recheck | 4 passed |
| Scoped native and renderer Pyright | 0 errors, 0 warnings |
| Complete `tests/architecture` | 76 passed; five known failures below |
| Final dependency/source hygiene/AI import checks | 48 passed |

The complete game suite finished with **2,648 passed, 23 failed, 177 errors**.
All 200 failed reports were independently classified: 179 baseline wall-media
errors/failures, two baseline lifecycle frame mismatches, three baseline legacy
attack-field decodes, 13 mixed-version gallery-schema reads while the files were
changing, one corrected passive import and two corrected coating-capability
expectations. A fresh focused equipment/replay/application run passed 88 checks;
its three legacy attack decodes reproduce on HEAD. New feedback regressions passed
28 checks, including palette replacement, real held/floor pixels, all pickup
frames, vendor registration at two zooms and both modular bodies. Independent
reviewers approve the corrections.
A desktop crash interrupted the first broad run. The restarted run wrote results to
`.runtime/items-module-20261002/resilient-validation/reports.jsonl`, full output to
`full-game.log` there, and its terminal result to `result.json`. Its process is
detached from the app. `failure-classification.json` retains the baseline proofs.
The broad run used code that changed during execution; its count is not a claim
that the final renderer suite is green.

Public native regressions cover placement vetoes/capacity, equipment displacement,
source unequip veto, state-bearing stacks, destroyed chest recovery, Drop discovery,
composed attacks and exact wearer cleanup/transfer. Public received-only game
regressions cover all six off-hand families, hidden/visible inventory recipients,
independent replay, ground lighting/selection and owned coating transfer/removal.
Review clips use actual native action events on the existing paving floor, in all
four cameras; production sprites are never manufactured for the review. The clip
removes a permanent coating and does not certify timed expiry; the native coating
clock continuity remains covered by the existing engine regressions.
Private [review clips](http://127.0.0.1:8768/items-module-20261002/accepted-review/runs/20261002T141505Z-e83b81/index.html)
are two complete 16-second, 32-FPS engine recordings in the standard gallery,
with saved native/player inputs, frame traces and checks. They replace the
unhelpful one-second checkpoint videos. The dagger alone drops onto an empty
adjacent tile, transfers and attacks before recorded coating removal. The prior
pile recording left a spare robe, not the dagger: every pickup frame in four
cameras now has an explicit floor UUID and actual drawing regression. Review
holds keep settled states readable without inventing native turns or slowing
authored animations.

The architecture suite has the same five previously documented failures:

| Check | Observed cause |
| --- | --- |
| `test_current_and_accepted_artifact_hashes_are_exact` | Frozen evidence hash differs from current artifact |
| `test_srd_source_inventory_and_proof_overlay_are_exact` | Coverage is 178 playable/742 missing; frozen expectation is 177/743 |
| `test_every_structural_definition_has_one_exact_authored_owner` | 11 structural definitions; frozen expectation is 10 |
| `test_cri_public_item_inventory_is_complete_and_direct` | Earlier window content is absent from the expected item set |
| `test_content_bootstrap_and_composed_spell_catalog_cold_start` | Paused server imports removed `dnd.core.senses` |

Those expectations and the paused server were not changed to make this lane green.

## Content authoring boundary

The code is ready to author deliberate gear variants using existing mechanic
families. The roster's deduplicated gear/material/palette and VFX ownership follow
the [updated item content plan](ITEM_CONTENT_IMPLEMENTATION_PLAN_2026-10-02.md).
The artist's all-150 reconciliation exists as a candidate inventory, with zero
exact selected appearances and 93 unresolved VFX observations; its original
thread is resuming the unfinished match analysis. Missing consumable
ground media, fixed-rig baked gear loss, firearms and unsupported geometry remain
explicit decisions; none is silently replaced with new rules or binding fiction.
Contacts inspected during the study do not certify every frame/direction/body.
Conditions/abilities and then characters follow the user's item-first order.
