# Surface transitions: bounded implementation plan

Status: independently approved by anti-slop and anti-OOP/ECS reviewers; awaiting
human acceptance of the proposed mechanics. This document does not authorize new mechanics by
borrowing BG3 or Divinity rules. Evidence is the
[native inventory](audits/SURFACE_ELEMENTAL_BG3_DOS2_COMPARISON_2026-10-01.md),
`dnd/spatial/environmental_conditions.py`, `dnd/spatial/transitions.py`,
`dnd/spatial/ignition.py`, `dnd/residues.py` and the artist's
`surface-ignition/SURFACE-INVENTORY.json` handoff.

## Intended result

Existing gameplay surfaces work through normal actions and material placement,
with visible formation, persistence and resolved transitions matching their
actual admitted cells. Accepted art is integrated before requesting replacements.
The first useful loop is oil/web ignition, water extinguishing ordinary ground
fire, and walking through the resulting material. Freeze, electricity and melt
follow as separate reviewed capabilities. Magical walls and clouds keep their
own rules; no automatic spreading, explosions or new status multipliers.

## What is already real

| Owner | Gameplay and creation | Existing transitions | Current visual coverage / missing connection |
| --- | --- | --- | --- |
| OilSurface | Barrel deposit; difficult terrain; persistent ground owner | IGNITE → FireSurface | Oil residue/spill installed. Accepted directional fire formation/hold exists; hold is not yet bound to this owner. Four named fire producers now connect ignition. |
| FireSurface | Real light and entry/turn-start damage; current 2d4/three-round game convention | DOUSE removes intersecting cells | Accepted fire growth/hold and quench wisps exist. Ordinary water placement does not yet produce a compatible resolved douse. |
| WetSurface | Barrel deposit, wet membership; persistent ground owner | FREEZE → Ice; ELECTRIFY → ElectrifiedWater; VAPORIZE → SteamCloud | Water spill/film exists. Cold/lightning/vaporization rows lack ordinary action producers. No need to replace working barrel art globally. |
| IceSurface | Difficult terrain, DC10 slip/prone checks, persistent ground owner | VAPORIZE → SteamCloud | No existing MELT→water row and no independently accepted freeze/thaw lifecycle in this handoff. Ice projectile art is not surface art. |
| ElectrifiedWater | Wet membership and first-per-turn lightning exposure | FREEZE → Ice; VAPORIZE → Steam | No normal electrification producer; no separately accepted electrified-water transition/hold. |
| SteamCloud | Two-round wet, heavily obscuring cloud owner | No authored disperse row found | Quench wisps are finite cosmetic puffs, not a complete two-round SteamCloud presentation. Maintained cloud art/behavior remains a separate gap. |
| Web / BurningWeb | Web restraint, difficult terrain, concentration; burning patches have their own short life | IGNITE → BurningWeb; burning patch DOUSE removes cells | Accepted Web and fire banks exist. Partial web burn-away/ash is missing. Preserve remaining Web ownership and concentration; burning replacements currently live independently. |
| Grease | Existing authored spell/slip zone and mundane barrel route | No ignition row | Installed accepted Grease and liquid art. Do not invent flammability from the artwork or change its current concentration convention in this lane. |
| Blood / poison / dread blood / other residues | Tile-owned deposits and their existing material/body-response rules; some harm or frighten on contact | No general surface transform rows | Existing spill/residue rendering. They are not WetSurface aliases. Corrosive/demonic/dread identities must stay distinct; the six-liquid art family does not prove every residue has a matching bank. |
| Fog/Cloudkill/Stinking Cloud/gas zones | Existing cloud owners, sensory obscuration and their own effects | Selected DISPERSE thresholds | Working cloud renderer remains unchanged. Steam dispersion is a separate proposed row; closing a door does not erase an existing cloud. |
| Wall of Fire | Field owner; flame contact and one-sided heat; concentration | Initial flame shell ignites Oil/Web; hot-side band does not | Installed native cardinal walls. New transient heat sweep is in real replay clips; safe-base masks installed with recorded physical hot-side selection. Late material placement into maintained flames is missing. |
| Spike Growth / scorch / other spell zones | Separate native spell or residue rules | No generic combustion claim | Installed authored art is retained. Thorns, scorch and burning terrain are different content. |

Other producers already present include Gust's authored wind dispersal and
Sleet Storm's strong dousing interaction at creation. Preserve their actual
spell behavior; do not relabel wind as water or apply dousing to every fire-themed
spell. The source audit distinguishes live rows from manually publishable events.

## Core contract: reuse the spatial system

1. A resolved action or committed placement supplies exact admitted contact cells,
   source attribution, occupancy layer and an explicitly authored environmental
   operation. Reuse `SpatialEffectInteractionEvent`; sorted nonempty positions,
   intensity and duration are already typed. Do not derive operations from
   sprite color or every `DamageAppliedEvent`.
2. The existing owner-indexed EFFECT handler intersects those cells with its
   footprint and selects its authored `SpatialEffectTransitionDefinition`.
   AIR contacts cannot transform ground surfaces. Preserve Globe filtering,
   native wall/door access, actual elevation, and Fireball breach-stage ordering.
3. Reuse current replacement admission: same-layer replacements activate with
   `replacing_condition_uuid`; incoming-application failure restores the incumbent.
   Outgoing full-retirement veto currently happens too late and can leave the new
   owner applied: repair that scoped cancellation gap by preparing the outgoing
   removal before mutation, then committing it after incoming admission succeeds.
   Secondary-cloud creation also currently ignores a later source-removal veto;
   C must preflight retirement or clean up the prepared secondary on failure.
   Never publish a consumed-cell outcome for a rejected retirement. Partial
   transformation preserves the untouched cells and their indexed handlers.
   Do not introduce a general transaction engine or rewrite these owners.
4. Add a small typed committed transition payload to the existing spatial
   lifecycle event/fact path: operation, predecessor/result identities and
   content refs, exact consumed/created cells, received source contact, support
   elevation and causal parent. Use the existing TRANSFORMED vocabulary if it
   can carry this outcome; do not manufacture it from an attempted interaction.
   Ordinary expiry, concentration removal and dousing must be distinguishable.
   Emit this optional frozen outcome once on the owning committed lifecycle event
   before completion; paired CREATED/TRANSFORMED events cannot duplicate accents.
   Add native optional fields to replay ADDITIVE_FIELDS for old recordings.
5. Project only observer-witnessed identities/cells from recorded native evidence.
   An interaction attempt currently projects no public fact, deliberately. Hidden
   surfaces must not become known because a global interaction names them.
   A transition may reveal a permitted visible steam response without revealing
   the hidden predecessor's identity/whole footprint. Predecessor and successor
   identities/refs and cell evidence must be independently redacted. Old recordings omit cues
   they cannot establish; they remain readable.
6. Render formation and finite transition accents from these public facts through
   the existing maintained/contact/deposit channels. Hold follows the resulting
   owner, not a guessed timer. A cosmetic quench puff creates no SteamCloud,
   obscuration, wet status, damage or gameplay cell. An actual SteamCloud needs
   its own retained state and maintained rendering.

Add source capability declarations where normal producer paths need them, using
typed authored operations rather than a growing spell-name switch. The first
adapter should consolidate the existing ignition publication pattern; retain the
spell executor's actual contact/outcome timing. Misses, failed/canceled actions,
protection exclusions and later breach stages cannot be flattened into one
precomputed AoE. This is composition of data and systems, not material subclasses
or a parallel physics simulator.

## Implementation sequence and exact scope

### A — Finish existing ignition/dousing presentation

Import only accepted fire onset/hold and the three quench banks, preserving full
sources privately. The current hot-side import already selects the eight 48-frame
formation banks. Add hold registration independently for actual burning owners;
do not use a repeating hot-side accent as terrain. Bind formation/hold to
FireSurface and BurningWeb; bind one quench accent to each resolved doused
intersection. Successful douse fades/removes the old fire at that causal contact,
using the recorded committed change. Canceled douse and expiry produce no quench.
Partial removal needs fragment retirement dates on the existing maintained-media
lifetime channel: today it has one owner-wide removed_ms and full REMOVED only.
The doused subset fades once while unaffected cells continue holding; do not
mark the whole owner removed or repaint a removed subset forever.

Cover newly placed oil/web inside existing Wall of Fire through an
explicit placement/APPEAR contact producer, after admitted placement. Emit one
interaction for the committed intersection per cause, not repeated per render
frame/turn. Wall contact uses actual flame cells only. Unburned rest and Web's
remaining concentration link survive; independent burning patches retain their
current native lifetime. No neighboring spread or hot-band ignition. Oil/Web
placement into an existing ordinary FireSurface is not admitted by the exclusive
ground layer, so an after-placement producer cannot handle that ordering. Keep it
as a named admission gap until the incoming-fuel outcome is accepted: whether
fuel is consumed by the incumbent, whether its lifetime renews, and which source/
deposit attribution survives. Implement through the same narrow admitted-contact
path used by B, not bypassed exclusivity. A does not claim that ordering complete.

Keep the current Oil damage/duration convention. Missing native Web burn-away
art is an explicit visual hold: do not leave removed Web drawn permanently,
replace a full 4×4 bank by a guessed partial texture, or invent per-pixel XYZ.
Until a correct partial Web bank exists, keep any accepted conservative visual
limitation explicit in review and separately request that asset.

### B — Water extinguishes ordinary ground fire

Recommended game convention for approval: committed water material contact
douses ordinary FireSurface/BurningWeb on the exact overlap; the cosmetic steam
accent does not make a heavy-obscurement cloud. Water does not cancel Wall of
Fire, Continual Flame, concentration or other magical fire fields automatically.

Water placement currently competes for the exclusive ground-surface slot. It
must not delete fire first and hope water activation succeeds, or simply fail to
place because fire occupies it. Add an explicit incoming-material discriminator
to the interaction/transition data only if the existing operation/intensity cannot
express the distinction: water-driven DOUSE selects an authorized wet replacement;
plain spell-driven DOUSE can keep the current remove-only row. Reuse same-layer
replacement activation and extend the direct environmental builder for WetSurface.
Carry incoming water MaterialDepositSource and grounded contact scope through
typed interaction data: the current builder copies the predecessor's deposit,
which would incorrectly attribute new water to the old oil. The caller must admit
each exact overlap once, exclude both replaced cells and rejected incompatible
overlaps from its remaining spill activation, and retain the incoming source for
all successful water pieces. Untouched fire retains its old source. Repair the
outgoing-retirement veto gap above before promising canceled/failed replacement
leaves the original fire unchanged.
Do not run a second renderer-owned liquid solver or rebuild the whole barrel.

First tests use a water barrel or another already-supported water placement,
burning oil, a partial overlap and a barrier. Water source volume/depth consumption
is not currently modeled; do not claim conservation or add a recursive water-vs-
fire strength solver. Repeated wet placement must be deterministic and bounded.

### C — Connect existing cold/lightning/vaporization rows

Audit each actual spell contact path before authoring capabilities. Cold contact
with water can publish FREEZE; lightning contact with water can publish ELECTRIFY.
Only selected spells whose resolved contact supports those operations participate;
ability names and damage enums alone are insufficient. Ground scope, admitted
AoE cells and successful projectile contact are explicit. Use a producer coverage
ledger so supported spells cannot silently diverge into target/object/AoE routes.

A proposed MELT operation and Ice→WetSurface row distinguish melting from the
existing VAPORIZE→SteamCloud row. The default fire contact should not turn every
water tile into a cloud or every ice tile instantly into steam. Which sources are
strong enough to vaporize, exact durations, and whether ambient fire douses from
cold remain authoring decisions to accept before implementation. Retain current
durations/status rules until those decisions are made; do not add BG3 Wet damage
multipliers or DOS2 armor/status rules.

Give SteamCloud a compatible DISPERSE row only if the requested wind rule is
accepted. Do not alter working cloud geometry or derive walls/doors from sprite
alpha. A newly spawned cloud uses the engine's accepted propagation model; later
door closure changes access/sight, not retroactive occupancy.

### D — Additional material proposals, separate from the first release

Residue freeze/electrify, poisonous combustion/explosion, acid neutralization,
flammable vegetation, soot remaining after generic fires, drying/evaporation,
and Grease combustion require explicit gameplay decisions and real material
ownership. Leave them unsupported rather than pretending art alone supplies
physics. Prefer a narrow residue-to-owner conversion only when its rules are
accepted; do not migrate all tile residues into surfaces as speculative cleanup.
No recursive adjacent spread, blessed/cursed variants, universal mixture solver,
or new multi-Z architecture in this plan.

## Artwork ledger and requests

| Required presentation | Available accepted source | Production work / genuine gap |
| --- | --- | --- |
| Ground fire formation/hold | `surface-ignition/HANDOFF.md`: eight directional banks, 48+64 frames, 32 FPS, four cameras/paired passes | Formation imported for heat accent; actual FireSurface/BurningWeb hold binding still required. No XYZ or fine arbitrary wall clipping is supplied. |
| Water extinguishing fire | Same handoff: three `quench_wisp` banks, 80 frames / 2.5s | Import/use after committed douse, fade existing fire locally. No native clear bank exists; a smooth local fade is the artist's accepted assembly proposal, not a new physical state. |
| Rounded liquid deposits | `delivery-liquid-depth-v1/HANDOFF.md`: six families × three seeds; floor/air and real droplet XZ ownership | Preserve selected installed bindings. `coverage-v2` completed only water seeds0/1; sixteen corrections remain pending, not an approved replacement batch. |
| Composable oil/water film | `surface-ignition/surface-assets.json`: fifteen corner patterns per material | Bind only if it improves actual admitted footprints; do not regress working deposit art or mix corrections from different seeds/captures. |
| Web partial burn/removal | Accepted Web v11 and generic fire | Need per-cell burn-away/removal/ash with compatible registration/coverage; no approved dedicated partial transition exists. |
| Freeze/melt/electrify water | Spell ice/lightning media exists elsewhere | Dedicated surface formation/hold/removal and transitions are absent from the recovered accepted set. Request only after C's rules/footprints/durations are fixed. |
| Maintained SteamCloud | Cosmetic quench wisps exist | A full cloud lifecycle/occupancy/visibility bank is a separate missing presentation. Do not stretch a puff across a two-round footprint. |
| Safe-side Wall base | Original wall art retained unchanged | Registered native side/height masks installed (4,119,132 bytes). Recorded geometry carries the selected hot side; absent historical metadata means no guessed tint. Original flame alpha and RGBA sources remain unchanged. |
| Curved wall / continuous heat stream | No approved ring or continuous constrained stream | Not a substitute for the cardinal wall/brief sweep. Separate requests after these are reviewed. |
| Other chemical/residue transitions | Existing blood/poison/dread deposits | No accepted generic reaction set. Optional D proposals require their own rule and art request, not blanket generation. |

Keep raw source/export backups private, selected packed atlases/geometry in the
private production repo, installation ignored in `game/assets`, and typed JSON
public in `game/data`. Use 32 FPS for new dense VFX, short maintained loops, exact
frame times and pivots, and shared pages. No 144 FPS production sheets, duplicated
sprite frames, fixed camera-only substitutes, or generated texture fallback.

Before commissioning an asset, send actual native affected-cell/elevation fixtures,
four camera registrations, intended onset/hold/removal phases, source/target
contacts and masks/XYZ requirements. Original art must remain intact. Accept
coverage and layering before scaling up exports; alpha/screen Y is not world height.

## Validation and review gates

Each admitted connection needs native command → committed change → projected
saved facts → cold replay → visible result, with no live engine query. The case
grid includes exact/partial/no overlap; barriers/doors/map edge; raised/airborne
contact; protected cells; all relevant cancellation phases; rejected replacement;
hidden predecessor and observer entering/leaving sight; repeated contact and
simultaneous owners; concentration and expiry; action/object damage provenance;
and four camera views at formation/hold/removal. These are targeted equivalence
classes, not every possible Cartesian combination.

For water dousing include fire-first/water-first placement, partial spill admission,
unchanged cells, failed wet replacement and deterministic repeated spills. For
Web include partial burn, concentration ending, independent burn retirement and
no stale restraint. For freeze/electrify include occupancy membership refresh,
slip/damage once-per-turn behavior and transition cancellation. Quench visual
tests must distinguish cosmetic steam from actual SteamCloud mechanics.

Record stable actor positions on real Fantasy H1 tiles, visible occupied-cell
overlays as an optional diagnostic, and native saved-event four-view videos.
Provide one short clip per connection: attempt, successful transition, traversal,
cleanup. Existing wall heat gallery is the first checkpoint; artist previews are
labelled source demonstrations, not engine integration evidence.

Include incoming-application cancellation and full outgoing-retirement veto as
separate native cases. Secondary vaporization must never leave both committed
steam and an unconsumed source merely because retirement was vetoed.

Run focused engine and replay checks per step. After mechanics changes, run the
complete engine suite, event/wire/dependency checks and scoped typing; document
any genuine app-integrity failure for human discussion rather than weakening tests.
Recheck cloud/wall/Globe occlusion only when the affected paths changed. Independent
anti-slop and anti-OOP/ECS reviews must approve the actual plan and final additions.

Implementation approval can cover A+B first while C/D stay explicitly pending.
That delivers a useful, readable surface loop using existing art and typed owners
without turning this lane into an unbounded elemental sandbox.
