# Liquid barrels — September 22

**Superseded footprint:** the user rejected one-cell spills and approved a
surrounding area for all six barrels. Follow
[the correction plan](LIQUID_BARREL_AREAS_2026-09-22.md). The original one-cell
statements below are historical, not an active constraint. Animated spilling is
also required and explicitly queued; static pools are not that finished result.

## Requested behavior and boundary

Breaking a placed barrel leaves its contents as native ground state: poison,
water, oil, grease, blood or dread blood. Walking into that state exercises the
same surface mechanics used elsewhere in the game. Observers receive the
result through existing subjective events, and saved packets alone reproduce
the remains and liquid. The destruction event owns the spill's causal lineage.

The user explicitly defers **Grease artwork** to the later spell handoff. Do
not import or bind its pending export. Implement and test its native barrel
mechanics; label that one visual gap honestly in the review gallery.

Input: actual attacks on placed barrels, then ordinary movement, jumping and
surface interaction. Output: same-UUID wreck, native surface/residue facts,
movement cost/conditions/damage where applicable, public replay and four-camera
paired review clips. No fluid simulation, new spreading rules, spell-rule
rewrite, multi-floor work or wider asset intake belongs to this unit.

## Native composition

Replace the oil-only composition with one liquid barrel composer and a finite
passive spill profile. Keep the existing oil ID and build helper compatible.
All six content IDs select data; do not introduce subclasses per liquid or a
second damage/condition engine. Capture the committed cell from the destruction
event's previous placement. All variants spill on **one tile**, preserving the
current oil footprint. Visual bounds must not determine gameplay bounds.

| Contents | Existing native owner and behavior |
| --- | --- |
| Oil | OilSurface: difficult terrain; its existing ignition transition remains, including destruction by fire. |
| Water | WetSurface: membership applies/removes existing Wet effects; preserve existing material interactions. |
| Grease | GreaseZone configured as permanent mundane ground grease, DC 10 Dexterity save and Prone on its existing triggers; difficult terrain. Generated Prone inherits zone tags instead of hardcoding magical. Spell Grease retains its existing defaults. |
| Blood | TileResidueCondition with BLOOD_RESIDUE; a full authored pool amount (5), mechanically inert for now. |
| Poison | New explicit poison ResidueProfile using the existing residue contact executor: 1d4 **poison**, not the acid damage of corrosive demonic residue. |
| Dread blood | Existing DREAD_RESIDUE: DC 10 Wisdom fear and the existing paid return step/stuck behavior. |

Use the barrel as the stable source for mundane grease, so the attacker is not
accidentally exempted by the spell's caster exemption. The destroyed barrel is
an item, not a creature occupant. Surface owners persist independently if the
wreck is later retired. Repeated damage/destruction must not deposit again;
terminal retirement must not spill. Existing native cancellation/interception
and lifetime rules stay intact.

Use actual ground contact: jumping over a liquid does not contact it, landing
on it does. Oil, Wet and Grease must explicitly select ground occupancy (their
ground visual layer does not itself restrict contact). Preserve that reach in
ground-to-ground replacements; Steam retains its cloud admission.
Preserve current per-material re-entry behavior and exact ownership
of Wet/Prone/fear; do not clear another source's condition or unrelated terrain.
Already-existing residue hazards act on entry, not retrospectively on an
occupant at deposition. The intact one-cell barrel blocks ordinary occupancy.

The study reproduced an existing adjacent dread-tile issue: a teleport into two
neighboring independent dread residues can reverse repeatedly between their
separate fear origins. This unit does not enlarge a barrel into a multi-cell
pool. Coherent multi-cell dread ownership is a separate unresolved limitation,
not a reason to introduce a pool framework here or claim it already works.

## Presentation ownership

Bind the six barrel IDs to the already installed accepted barrel intact/broken
banks. Content identity/name distinguishes the contents; no new barrel art is
required. Blood/dread use the installed persistent residue renderer. Poison
gets an explicit binding to the existing green liquid material without changing
its poison mechanics. Reuse an existing shared ground-material drawing path
for water/oil with authored palette/shape values; no per-barrel draw branches.
Do not pretend a missing liquid sprite is a spell failure or request Grease art.
There is also no installed persistent FireSurface artwork. Oil still ignites
mechanically and its former puddle must disappear; the burning-surface media
need is queued with the Godot task for a later handoff. Burning grass additionally
needs explicit combustible-terrain rules and is not implemented by coloring a
tile or by this barrel unit.

Ground images obey the observed tile cells, height, camera and painter order.
Both material transforms/removal and late initialization must be visible from
received state alone. No queries back into native objects from rendering.

## Acceptance and execution

1. Independent **anti-slop** and **anti-OOP/ECS** reviewers check this concrete
   composition and scope before implementation. Record their findings below.
2. Implement the finite native data/composer and six registered variants. Test
   real breakage, causal ownership, no duplicate/retirement spill, independent
   aftermath, and exact material identity. Exercise entry/exit, jump-over and
   landing plus oil ignition, water Wet, grease saves, poison damage, inert
   blood and dread paid retreat/budget exhaustion through native APIs.
3. Connect shared presentation data for the five currently visualized liquids.
   No Grease media integration. Test observed state and serialized replay,
   native surface changes and four camera corners at the appropriate boundary.
4. Record real paired histories: break each barrel, cross the resulting tile,
   and include save success/failure and a jump contrast where meaningful. Build
   a review gallery from saved packets, inspect frames, document the Grease
   visual gap. Do not fabricate state changes to animate a demo.
5. Run the affected engine, replay/media, destruction and registry checks plus
   typing. Review the final diff for duplicate mechanics or content-specific
   renderer code; update recovery status and the implementation record.

## Review

Anti-slop review (`backend_ecs_review`) and anti-OOP/ECS review
(`spell_orientation_antislop`) both approved the shared composition. Both
identified the ground-occupancy requirement above; it is part of implementation,
including replacements. Blood amount remains the existing residue accumulator,
with a bounded deposit quantity rather than multiple fake injury events.
Presentation review (`presentation_antislop_review`) found the existing
`particles.region.poison` material and the need for a shared pool representation
when a native residue has no injury ellipses. Existing injury contributions must
remain unchanged. Implementation is complete; see the
[result, validation and deferred media](LIQUID_BARRELS_RESULT_2026-09-22.md).
