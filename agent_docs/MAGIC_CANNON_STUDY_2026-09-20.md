# Magic cannons: recovered artwork and native firing study

Status: the shared body/grant implementation remains. **The user rejected the
Magic Missile cannon demonstration below.** Its replacement is one larger Sleep
projectile and Sleep area, with paired mage/device cases. Web follows, including
[device-owned sustaining](DEVICE_SUSTAINING_PLAN_2026-09-20.md). The prior results
below are historical validation, not visual approval or the final spell selection.

## Initial implementation result (before the Sleep correction)

`build_spell_device` composes an existing fixed `SpellGrantingItem` from a body
identity and ordinary spell templates. Either body can grant different spells,
or several spells with different levels/ranges/aim restrictions. The existing
Fireball/arcane builders remain convenient default content constructors. There
is no cannon-specific Fireball/Magic Missile implementation and no renderer
branch selecting a spell from the device's name.

For example, one body can carry these independent grants:

```python
device = build_spell_device(
    item_id="environment.fireball_cannon",
    name="Spell Cannon",
    charges=3,
    spell_templates=[
        Fireball(source_entity_uuid=operator.uuid, template=True,
                 cast_at_level=3, cast_origin="source_item",
                 alt_range=225, target_sector_degrees=45),
        MagicMissile(source_entity_uuid=operator.uuid, template=True,
                     cast_at_level=1, cast_origin="source_item"),
    ],
)
```

These are existing native spell records. `cast_origin` defaults to `actor` for
ordinary casts; `source_item` selects the placed emitter. Existing `alt_range`
overrides distance and optional `target_sector_degrees` is the total angular
width around operator-to-device direction. Omitting it adds no angular rule.
Shared discovery/execution geometry and displayed target distances use that
origin. Source-item casting requires a perceived device in a distinct neighboring
cell. Rejected position/range/aim commands spend neither action nor charge.

The default cannon content currently authors level-3 Fireball, 225-foot range,
45-degree aim width and three charges. The arcane body defaults to level-1 Magic
Missile, its ordinary 120-foot range, no extra sector and unlimited charges.
These are editable content choices, not universal device rules or final balance
approval. Custom grants keep their own levels. The spell owns target modes,
recipient allocations, effects, saves, homing and blast propagation. Fireball's
aim restriction never clips the explosion's victims.

Native `SpellEvent` records `cast_origin` and the effective range. Its existing
`source_position` still means operator position, and its existing source-item
UUID identifies the device. The player projection retains this UUID only when
the object is disclosed. Binding reads its historical placement from retained
player state, including height. It never queries a live device or native map.
Older archives retain actor-origin defaults. Missing emitter disclosure remains
an explicit binding gap; it does not invent an origin or disclose private state.

### Body media and launch

`game/data/spell_devices.json` owns body-to-item bindings, operation recipe,
launch pitch and control distance. Its measured media data retains the artist's
eight direction rows, eight phase columns, four cameras and four pitch banks.
The 32 imported sheets total 2.92 MB. `devtools/import_spell_devices.py` copies
those sheets and measurement data while preserving authored settings. There are
no content hashes, startup asset scans or runtime imports from the art worktree.

The operation reuses the existing arm-extension recipe (`Attack5`), with contact
at the body's authored release column: 250 ms at 12 FPS. The body continues
through recoil/recovery. Actual spell projectile/target recipes keep their media,
palette, impact behavior and applications; no actor hand-casting overlay is
added to device operation. There is no measured crank/hand socket in the delivery,
so this is the existing arm gesture, not a claimed exact hand-on-crank contact.

The barrel points away from the operator. Measured muzzle position at release
supplies launch contact and stays fixed during recoil. One optional initial
control vector extends the shared projectile curve for device launches. It comes
from the authored bore direction and control-distance fraction; the actual spell
still determines the destination and its remaining trajectory. Current body
settings select the 15-degree pitch bank. Body facing persists after playback
using the existing historical visual-facing state. Lighting, subjective object
visibility and painter ordering remain in the existing world draw pass. Decoded
sheets and scaled/tinted frames use bounded caches.

The portable JSON and coordinate meanings are documented in
[the presentation contract](../game/data/PRESENTATION_CONTRACT.md#spell-device-bodies-and-emission).
Pygame consumes sampled body frames and trajectories; these records contain no
Pygame surfaces, Python class names or backend animation instructions.

### Verification and review

Independent anti-slop and ECS reviewers approved the implemented selected path.
Their final review found two presentation issues, both corrected: repeated body
resampling/tinting, and a device trajectory branch overriding a spell's
`fineRotation: "none"`. The former now uses bounded caches; the latter respects
the authored opt-out and has a four-camera regression check.

- Backend: **63 passed** across `test_spell_device_targeting.py`,
  `test_126_action_override_runtime.py` and
  `test_131_inventory_use_actions_legacy_contract.py` (20.85 seconds).
- Game regression: **314 passed** across animation, volley, attachment geometry,
  combat/history, world/boundary drawing, areas, projection, assets and devices
  (53.25 seconds).
- Final focused device replay/animation check: **9 passed** after the rotation
  correction (6.64 seconds). Eight overlap the game batch; do not add the counts
  together. Changed game modules, importer and new game tests typecheck cleanly.
- New scenarios serialize native events, reset the native runtime, project and
  serialize player events, then bind/reduce them without live entities. Costs,
  damage, child applications and operator-only charge disclosure are asserted.

The [superseded six-clip gallery](http://127.0.0.1:8767/runs/20260920T145340Z-e77f9c/index.html)
passed across 748 four-camera frames with no media gaps. Each of three real action sequences is recorded from
operator and target viewpoints, with four camera angles per clip:

1. The same cannon casts Fireball, then split Magic Missile on its next real turn.
   Shared charges reach zero; after a fresh turn, discovery offers no shot.
2. The arcane body emits three Magic Missiles toward two separate recipients.
3. A cannon shot is rejected, the operator pays movement to walk around it, and
   the newly legal Fireball reaches its selected center plus a victim outside
   the aiming sector. Its range is measured from the cannon, not the operator.

The final gallery rerenders the same saved inputs after the rotation correction;
it does not regenerate gameplay. Numeric defaults and new footage still await
the user's visual judgment. Existing actor-cast recipes remain unchanged.

### Bounded support

This integration exercises the two existing device defaults and Fire Bolt as an
additional native grant. Other authored sprite-projectile spells can use the same
binding when their native targeting supports the origin hook. It does not claim
that every spell's self/touch/cone behavior has become device-relative: those
families still need their appropriate native origin semantics if actually granted.
The retired procedural geometry-projectile fallback also retains its old curve;
the imported Magic Missile uses the supported authored sprite path. No new flight
collision rules, autonomous turret controller or persistent native aiming state
were added.

## Original study before implementation

The following sections describe findings and choices before the implementation
above. Statements about then-missing origin/aim/media support are historical.

## What exists in the current branch

| Device | Current native behavior |
| --- | --- |
| `environment.fireball_cannon` | Fixed, non-pickable `SpellGrantingItem`; ordinary level-3 Fireball; defaults to three charges; costs one operator action and one charge; depleted device remains placed but offers no shot. |
| `environment.arcane_machine_gun` | Fixed, non-pickable `SpellGrantingItem`; ordinary level-1 Magic Missile; unlimited charges; one operator action; does not enter inventory. |

Both come from `dnd/content/items/environment_item_builders.py` and are registered
by `authored_item_builders.py`. The battlefield catalog already places the
Fireball cannon in two environments. Existing discovery considers sensed usable
floor objects within five feet.

The operator is still the spell caster: range, spell perception and declared
`source_position` refer to that actor. There is no cannon firing-sector rule.
The item supplies the spell and charges; it is not yet an independent emitter.

Three existing checks passed in 2.42 seconds: repeated Magic Missile use,
Fireball depletion/removal from discovery, and environment discovery requirements
(`tests/manual/test_131_inventory_use_actions_legacy_contract.py`). An independent
reviewer repeated those checks successfully. These tests do not claim to cover
cannon-origin firing or sector restrictions that do not exist yet.

A native firing probe additionally confirmed: operator at `(1,5)`, cannon at
`(2,5)`, recorded spell source at `(1,5)`; the item UUID survives native event
serialization; a successful shot damages its target, spends one action, leaves
spell slots unchanged and changes charges from three to two. Charge consumption
is a causal child of the cast. The diagnostic first omitted the normal content
bootstrap; after installing the same catalog used by the tests, it ran normally.

## Recovered material and its actual status

Coordinated directly with task **Matching environment spritesheets —…**,
`01a0b501-8a27-7413-ba24-4a36e5b140d2`, the producer of the blood artwork.
Its current asset root is:

`/home/tommaso/.codex/worktrees/23a9/dnd_engine/output/environment-sprites/`

- [Weapon workshop handoff](/home/tommaso/.codex/worktrees/23a9/dnd_engine/output/environment-sprites/weapon-workshop/README.md).
- [Latest firing/scorch handoff](/home/tommaso/.codex/worktrees/23a9/dnd_engine/output/environment-sprites/PRODUCTION-FIREBALL-SCORCH-HANDOFF.md), superseding the older firing-sequence README.
- Latest reviewed body sets: `weapon-workshop/cannon-pitch{0,15,30,45}/` and
  `weapon-workshop/arcane-pitch{0,15,30,45}/`. All four pitch directories together
  form each device's bank. Pitch 45 is barrel elevation, not a new camera angle.
- Secondary `weapon-workshop/fork/` is an exploratory base model; no corresponding
  pitch bank or final firing-sequence approval was established.
- Each set includes editable Blender source, individual frames, four camera
  sheets and metadata. The existing `weapon-candidates.zip` excludes the later
  pitch banks and must not be mistaken for the complete latest delivery.

Export contract: 256×256 transparent cells in 2048×2048 sheets; eight world-aim
rows and eight phase columns; four cameras independent of aim. Ground anchor is
`(128,208)`. Phases are idle, charge 1/2, release, recoil, recovery 1/2, settled.
Candidate playback is 12 FPS, with release at column 3 / 250 ms. Metadata provides
measured per-frame muzzle pixels, forward vectors and barrel pivots. All banks
retain the 30-degree orthographic camera. Authoring coordinates are not tile
coordinates; use the documented conversion rather than treating them as native
world positions.

The producer confirms the user approved the final launch/impact-shaped-wall
preview behavior and asked for its production documentation. This is not proof
that every angle, lifecycle state or secondary fork candidate was approved.
There are no authored empty/broken skins or exported operator-hand/control
sockets. A modeled crank is not an interaction anchor.

The preview's `shared-vfx` is a live link into the Godot task's worktree, not a
portable delivery. Existing production Fireball/Magic Missile recipes and imported
media remain the starting point. Do not roll back approved speed, scale, palette,
wall behavior or timings by copying older prototype code. The arcane prototype
uses a purple javelin; it does not demonstrate Magic Missile's multi-target or
homing semantics. Fixed-wall preview sorting, wall UVs and reset behavior are
examples, not generic game rules.

## Design direction: an existing spell with explicit device parameters

The user's combined requirements are: reuse the actual spell, emit from the
cannon, allow the device to modify targeting/range, and let operator position
matter. A launch arc and a rule restricting selectable targets remain distinct.
A fixed 45-degree target sector is not an agreed requirement.

1. Keep the spell's target mode, applications, effects and item-use costs. Author
   any device range override or additional target restriction explicitly on that
   device's spell grant; do not change the globally shared spell definition.
2. Use the cannon as the physical emission point. The operator remains responsible
   for the action and caster-dependent rules.
3. Operator position can determine the cannon's initial firing direction: standing
   west gives an eastward launch. Moving around the device changes that direction.
4. The existing spell delivery determines how the projectile proceeds after
   launch. Changing the launch arc must not silently replace that spell's rules.

For Magic Missile, preserve homing and repeated applications. The initial launch
direction alone does not prove a final target is illegal; an explicitly authored
device sector can restrict which recipients may be selected, without changing
how the selected missiles fly. Omitting the sector leaves no added angular rule.
For Fireball, a sector restricts the chosen impact center, not individual victims
of the resulting explosion. Normal blast propagation stays with the spell.

This gives meaningful operator movement to a device whose grant has a sector,
without imposing that sector on every spell-emitting item. No numerical aperture,
separate rotation action or persistent turret orientation has been chosen.

### Existing data to reuse, and the small missing part

`SpellAction` already has `spell_range`, `alt_range`, `effective_range` and
`get_range()` (`dnd/actions.py:4350,4373,4460`). `SpellGrantingItem.get_use_actions`
creates the ordinary spell variant and preserves those fields. Device builders
can author a range override on that existing template. No second range field,
multiplier stack, override merger or device-spell subclass is needed.

The proposed additions are only passive casting-geometry data on that grant:

| Parameter | Meaning |
| --- | --- |
| Existing `alt_range` | Optional replacement for the spell's normal distance; absent uses the spell's range. |
| Casting origin choice | Actor by default; source item for a mounted device. Uses existing actor/item identity. |
| Optional target sector | When authored, limits selected target points around operator-to-device direction. Absent adds no angular restriction. |

Names for the new fields are not fixed here. Keep this data with the executable
spell template, rather than duplicating a targeting policy on the item, spell and
renderer. Derive direction from the current operator/device positions for use;
do not store another persistent aiming state.

One shared geometric calculation should resolve the chosen origin, distance and
optional sector for discovery and authoritative execution. Existing spell-specific
visibility, target filters and application rules still apply. When range is
device-relative, replace the actor-relative distance test: an additional check
followed by the old actor check would accidentally impose two different ranges.

The concrete first integration surface is the two existing device spells:
Fireball and Magic Missile validation plus their position/entity discovery paths.
This does not claim automatic support for every self/touch/line/cone spell. Add
other delivery forms only when a device actually grants one.

`SpellEvent.range_ft` currently records `spell_range.normal`, even when validation
uses `effective_range` (`dnd/actions.py:4904`). The implementation must record the
effective value so an authored device range is represented honestly in events.

The active manual range-override test passed in 1.49 seconds, exercising discovery,
execution and clearing (`tests/manual/test_126_action_override_runtime.py::
test_range_override_controls_discovery_execution_scaling_and_clear`). A reviewer
also probed both device builders with a diagnostic `alt_range=225`: their use
variants retained that effective range, actor/item identities and one-action cost.
This establishes reuse of the existing override, not the unimplemented geometry.
The older engine test module could not collect because its server imports reach
retired `dnd.core.senses`; that unrelated import was not changed in this study.

## Existing integration points and necessary distinctions

Keep the shared `SpellGrantingItem` path. It already binds operator and source
item separately and owns item-backed costs. There is no reason for a new cannon
entity, aiming manager or separate Fireball/Magic Missile implementation.

- Reuse the existing spell recipe with the device origin and launch direction.
  Backend targeting parameters belong on the granted action; visual muzzle,
  pitch and trajectory settings belong in presentation data. Neither requires
  a parallel cannon-spell implementation.
- Entity-target discovery calls actual action validation. Fireball position/AoE
  discovery instead uses `get_valid_positions` and area previews. Adding a sector
  check only to execution would advertise illegal shots; filtering only the UI
  would not make it a rule. Both must use the same authored device restriction.
- `execute_use_action` regenerates current item actions but does not independently
  repeat discovery's general proximity gate. Any agreed operating-position rule
  must agree between authoritative action validation and target discovery.
- Discovery's displayed target distances are currently actor-relative too. Use
  the resolved origin consistently there; if an existing AoE preview cache stores
  those distances, include that origin in its key. Reuse the cache, not a new one.
- Preserve the existing observer's senses and subjective event admission. The
  cannon gains no independent vision. Existing map propagation provides physical
  obstruction queries; its use must follow the actual spell's rules. A curved
  drawing is not authority to bypass a wall or add a new collision simulation.
- `AoEShape.origin_override` is effect geometry, **not** launch geometry. Setting
  it to the cannon could relocate the Fireball blast to the cannon itself.
- `SpellEvent.source_position` currently means operator position. Projection
  checks actor disclosure for it, and `game/combat.py:107` requires agreement with
  the retained actor contact. Preserve that meaning and bind the emitter through
  the existing source-item identity and retained historical object placement.
  Add native coordinates only if the existing recorded state cannot recover it.
- `SpellFact` does not currently carry that item instance/emitter binding, and
  `bind_cast` assumes an actor source. The public projection and shared binding
  need to carry the permitted historical object origin before the muzzle art can
  be connected honestly. Content attribution alone is not an object placement.

The recorded sequence must supply the historical shot origin alongside the actor,
item and complete child lineage. Reuse retained placement rather than duplicate
it in a new event field without need. Playback must not consult a live cannon or
a subsequently moved operator. Muzzle pixels, barrel pitch-bank selection and
body frames remain presentation data, not backend rules.

## Presentation choice still requiring judgment

The recovered eight yaw rows depict the eight operator-to-cannon axes. They do
not provide continuous horizontal yaw. Under the user's clarification, the bore
should align with the initial launch direction, not necessarily a straight line
to the final target. Use the existing spell trajectory with that launch input;
do not move targets or restrict native targeting to match sprite rows. Only
request more yaw artwork if the chosen launch behavior actually needs it.

The existing pitch banks address vertical barrel inclination independently.
Adapting the initial flight arc to the cannon is now expressly requested. Current
Bezier authoring supplies scalar curvature, not an independent initial tangent;
a small shared trajectory input may be needed. That is presentation geometry,
not a ballistic rule system. Match the depicted barrel and launch tangent while
preserving the actual spell's selected destination and delivery behavior. Capture
the muzzle at release so recoil cannot drag an already launched projectile. A
literal hand on a crank needs an authored control socket/pose; none was recovered.

## Evidence required before calling an implementation complete

Real action discovery/execution should demonstrate ordinary behavior when optional
device parameters are absent, an extended range measured from the device, sector
boundaries and repositioning when a sector is authored, and unchanged costs/charges
and wall rules. Include a target inside device range but outside operator range
to expose double validation. Fireball's blast stays at its selected destination
and may affect victims outside the aiming sector. Multi-target Magic Missile must
retain its real child applications and homing delivery; check selected recipients
against an optional sector independently of their flight curves.
Saved sequences from operator and target perspectives should replay the same
origin/aim after native reset and later movement, with four-camera footage of
release, recoil and impact. Use existing scenario/replay/gallery tools.

Independent anti-slop and ECS reviews identified the discovery/execution split,
launch versus blast origins and the meaning of `source_position`. Latest anti-slop
and ECS reviews support reusing `alt_range` plus explicit origin/optional sector
data. They require replacing actor-relative distance rather than adding a
competing check, and keeping displayed/cached target distances consistent.
Earlier warnings against deriving game rules from visual trajectories still apply;
they do not prohibit the device modifiers the user has now explicitly requested.
The producer independently confirmed yaw/pitch and missing control-socket limits.
No implementation or import was made in this study.
