# Packet 6 Antimagic native implementation handoff — 2026-10-04

Status: implemented and locally verified within the approved Antimagic scope;
**independent native review is required before visual binding**. This is an
implementation handoff, not self-approval or whole-plan completion. The shared
checkout contains other agents' changes; this document does not claim to freeze
their files or approve their packets.

## Retained ownership contract

`BaseCondition.suppression_provider_uuids` holds additive field UUIDs on the
existing condition. `set_suppression(provider_uuid, suppressed)` changes one
provider without resetting duration, rebuilding children, or replacing owned
modifiers and handlers. The obsolete `AntimagicSuppression` remove/re-add path is
removed. `bind_owned_contributions()` stamps existing ownership-array entries.
Value aggregation, contextual modifiers and event/spatial handlers consult that
exact owner. Missing owners fail closed. Existing `enabled` flags remain intact.
Lifecycle handlers explicitly use `runs_while_suppressed=True`; condition clocks
and final teardown remain active.

The leaf `ContributionOwner` protocol in `dnd/core/base_object.py` adds only
`uuid`, `contributions_active()` and `allows_contribution_at(position)` to the
existing registry contract. `BaseObject.get_contribution_owner(uuid)` reads the
existing registry. Items also register there because their ordinary identity
registry is `BaseBlock` rather than `BaseObject`; item teardown removes both
entries. `BaseObject.get()` retains its original subtype check. There is no new
owner registry or condition manager. This protocol/registration boundary needs
particular independent DAG and identity review.

Shared public children use their existing primary/additional parent UUIDs.
Suppression of one magical parent cannot remove a surviving mundane jaw-trap
contribution. The existing spatial-restraint lease reconciliation now also runs
when an independent public Restrained replaces the previously borrowed child.
Harm and Feast refresh their existing effective contribution from active source
owners; they do not repeat application or healing. Max-HP transitions preserve
normal HP through the previously supplied Health helper.

## Direct consumers and published data

- `ConditionState.suppression_provider_uuids` publishes the effective exact
  provider tuple, including shared-child ownership. Condition and resulting stat
  changes use existing events. New effects born inside a field acquire tokens in
  existing `prepare_condition_application`, before application contributions.
- `ItemPresentationState.suppression_provider_uuids` publishes intrinsic item
  suppression; existing `ItemEffectPresentationState` rows carry the same tuple
  for intrinsic weapon damage coatings. Ordinary physical item appearance remains.
- `BaseItem.refresh_antimagic_contributions()` recomputes current ownership from
  the existing protection registry during world-placement/location publication.
  Field movement and removal update retained item state, including carried,
  dropped and temporarily absent created items. Magical usable-item admission
  rechecks before charges or effects are consumed.
- Invisibility and Freedom of Movement use passive condition contribution fields.
  Immunity entries, granted actions, Shillelagh overrides, Fly/Haste grants, owned
  sense modes and wearer/property modifiers consult their exact existing source.
  Ordinary nonmagical Hidden remains effective. Sense ownership is excluded from
  wire payloads; existing sense-mode replacement events remain compatible.
- The shared light API is the weather agent's
  `GridMap.refresh_contribution_lights(parent_event: UUID | None)` and
  `add_light_source(..., contribution_owner_uuid: UUID | None)`.
  Antimagic calls that refresh after a suppression transition. Existing light
  object identity, UUID and authored `is_active` stay intact. Produce Flame now
  stamps its actual condition UUID on its light.

## Spatial effects, transport and physical items

`AntimagicException` declares FIELD, ARTIFACT or DEITY in existing effect-origin
data. Field providers remain in the existing SpellProtectionRegistry and cannot
cancel one another. Spell admission handles source, destination and crossing;
position-target declarations now preserve their actual `end_position`, without
changing area-position semantics. This rejects ordinary teleport into a field.
BASE_ACTION magical repetitions use the same spell-effect admission route.

Areas retain their native footprint and owned terrain modifier identities.
Existing typed `SpellSuppression` rows identify exact affected cells. Initial
installation, field movement/removal and later area relocation recompute those
cells; terrain, light/optics, triggers, Force/Ice/Wind wall contact and crossing
consumers use the same gate. Force wall sections keep identity with only the
covered cells open. Created stone remains an ordinary physical obstruction.
Wall sections deliberately do not use whole-object disappearance, which would
erase uncovered parts of a partially suppressed wall.

Physical ranged attacks use their existing path and record
`ActionEvent.item_magic_suppression_provider_uuids`. A crossing attack omits its
weapon's +N, magical extra damage and magical attack overrides in the attack's
combined values. The arrow and ordinary damage continue; the source weapon's
live values and ownership remain unchanged. Explicit artifact weapons bypass
this gate. The existing item property handler consumes that same recorded tuple.

## Created presence and expiry

Summons retain the same Entity and existing Summoned owner. Spatial presence and
runtime agency suspend through existing entity operations; encounter membership
and condition duration keep ticking. Guardian/Feast created props use their same
BaseItem and exact creation-condition UUID. Whole props use existing map
remove/place operations and keep their clock while absent.

After the final token clears, these Antimagic-created absences restore at the
original anchor only when native footprint admission is valid and unoccupied.
Otherwise the same owner has one ordinary owned return handler waiting on
committed spatial departure; nobody is displaced. Expiry removes that handler and
the retained owner once, with no resurrection. Overlapping fields also inspect
absent items through the existing item registry. The original-coordinate return
policy is specific to Antimagic; Banishment's separate nearest-valid return work
is not changed or claimed complete here.

The implementation uses EFFECT handlers on committed spatial boundaries. The
existing EventQueue intentionally does not execute COMPLETION EventHandlers;
new-condition suppression therefore lives in the existing preparation path,
rather than relying on an inert completion callback. Field-owner removal defers
restoration to the existing runtime-owner removal publication boundary.

## Verification

Commands use HOW_TO_TEST's cached uv environment and pytest `--assert=plain` to
avoid recursively rendering large engine objects on failure.

- `/tmp/dnd-antimagic-combined.log`: **455 passed** across Antimagic, prepared
  condition lifecycle, jaws, direct items, roster support, summon terminal
  consequences, holy/necromancy, Telekinesis, remaining walls, wall retirement,
  Wall of Fire, silent removal, senses/light/stealth and dependency boundaries.
- `/tmp/dnd-antimagic-item-final.log`: **35 passed** after the final usable-item
  admission case, covering Antimagic and direct item runtime.
- `/tmp/dnd-antimagic-final-focus.log`: **101 passed** after the last area
  relocation correction, covering all **21** new retained-contribution cases,
  roster support and remaining walls.
- `/tmp/dnd-antimagic-type-final.log`: **0 errors, 0 warnings** across the 25
  touched production modules checked before the final small item/area changes.
- `/tmp/dnd-antimagic-type-final2.log`: **0 errors, 0 warnings** for the final
  BaseItem, area, abjuration, wall and item-property changes.
- The reported sense-mode wire regression was checked directly with
  `test_eb_12_009_sense_mode_changes_emit_replacement_payloads` and passed.

The final focused runs supplement the earlier 455-case run; they are not a claim
that all 455 were repeated after the final edits. The new cases exercise identity,
overlap, expiry, source handoff, existing-area relocation, item transfer, stale
consumable admission, partial Force/physical Stone, blocked summon restoration,
created prop absence and ordinary physical arrows. Existing old tests were
migrated from removed/re-added condition expectations to retained membership and
exact token expectations. No artwork, render acceptance or whole-suite completion
is claimed by this native handoff.

## Independent review requested

Review the registry/protocol boundary and cleanup; contribution coverage outside
owned modifier arrays; preparation/removal publication ordering; shared-child
source handoff; exact pending-presence ownership; partial area identity; and
typed item/condition facts consumed by replay. Client binding remains root-owned.
Chain Lightning target selection and causal links are concurrently root-owned and
are outside this handoff's implementation and verification claim.
