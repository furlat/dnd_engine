# Continual Flame client ECS review — 2026-10-04

Initial verdict: **one concrete supported-object integration blocker**. Root
subsequently authorized this reviewer to implement the bounded correction;
independent root review of that correction will be required. The historical
finding below is retained rather than overwritten by a self-approval.

The supplied client binding uses real item/effect UUIDs, current disclosed
membership and retained passive application dates. First observation enters the
hold; cover, suppression, transfer and loss of sight do not replay application.
The item-specific projection fact avoids inventing creature condition membership.
Existing choreography admission and registered media sampling own timing. The
shared compositor uses current item-layer alpha, preserves body/support shadow
ownership and obeys exact suppression tokens. No new native event, rule engine,
registry or private scheduler was found. The documented fixed-sheet limitation
remains honest: no separable item pixels means no manufactured hand anchor.

Blocker: `playback_frame` routes floor attachments exclusively through
`item_ground_commands`, which returns no command without a GroundAppearance.
Ordinary authored furniture, devices and static props instead render through
the environment/device/static paths in `app.draw_frame`; those paths ignore the
item attachment commands. Continual Flame legally targets those real objects,
including the installed clay stove, so native light and effect membership exist
without the supplied flame. The correction must wrap their existing rendered
source frame, retain exact UUID/lifetime and current disclosure, and preserve
fixture depth and physical silhouette rather than replacing the object.

Independent baseline verification:42 cases passed in42.47s across Continual
Flame, player Chain selection, controls and dependency boundaries
(`/tmp/dnd-chain-continual-independent-review.log`). This verifies the supported
floor-equipment/modular path, not the missing environment route. No gallery was
rerendered during this review.

Pre-correction source pins: item_attachment_lifetime.py
`378aa2c9ea04785625db40545d7704bbbe6acda11c352d82fd0f90155697a3c4`;
item_draw.py `dba322a79b0119fb1ba730db64b7ed31b2d94aea1f9f151fff5955c24b2ff35a`;
animation_draw.py `4a04017bc72e35fbb47e1eb94ecf085419bf3ec882367f148c35ec82cf85364b`.

## Authorized correction implemented — root review required

The same `_item_attachment_blits` sampling now serves both composed modular/
ground-equipment frames and `item_attachment_commands` around ordinary object
frames. `app.draw_frame` binds current environment-bank frames, device frames
and single static-prop frames to the real item's UUID and existing application
date. The ordinary encounter and recorder pass their existing AnimationData and
item-start values into this map consumer. There is no separate lifetime,
registration table, item instance, native query, spell-name dispatcher or clock.

Environment attachment planes are separate rear/front DrawCommands, so the real
frame's surface, alpha, placement and registered fixture-depth crop are retained.
The existing owner field identifies those planes and their physical frame.
`split_actor_fixtures` excludes a peer only when both have the same explicit
nonempty owner; other actors, fixtures and world ordering still participate.
Current object disclosure, intact membership and both item/effect suppression
tokens gate drawing. Unrelated objects avoid attachment alpha scans altogether.

The new `test_continual_flame_objects.py` uses native discovery/casting on the
installed clay stove, Fireball cannon and standing torch, records real world
relocation and destruction, resets the engine, then consumes saved player bytes.
Those fixtures are nonportable: the test uses their existing world-placement
operation and does not fabricate player pickup permission. Both recorded
positions retain the one effect UUID and witnessed birth. Actual map-frame
pixels differ with the accepted flame in all four cameras, source object draw
evidence remains present, and suppression, loss of visual contact and destruction
remove only the attachment. Existing portable item transfer/loot/equipment
coverage remains in the original Continual Flame cases.

Final verification:

- `/tmp/dnd-continual-objects-final.log`: **105 passed, 10 fixture setup errors**.
  All new object, existing Continual, fixture-depth, world-depth and import-DAG
  checks passed. The ten projectile tests exposed missing selected texture
  dependencies in their explicitly restricted `original_data` fixture.
- That fixture now includes the real `fire_media`, `necrotic_media` and
  `support_conditions` dependencies for Continual Flame, shared stone and bark.
  No runtime fallback or validation omission was added.
  `/tmp/dnd-continual-projectile-fixture-final.log`: **all10 passed in3.69s**.
- `/tmp/dnd-continual-object-type-final.log`: **0 errors/warnings** across changed
  renderer/call-site modules and both affected test files. Whitespace check passed.
- Earlier transient failures from the concurrently incomplete electric draft's
  required LayerColors.source remain in the original logs; root repaired that
  authored draft before the successful combined run. A fixture initially used
  the wrong registry for StandingTorch and was corrected to its actual existing
  `build_standing_torch` constructor.

This accounts for all115 collected cases through the combined run and the exact
failed-file rerun. It does not claim a fresh 115-case combined run, new gallery
acceptance or independent approval of this reviewer's correction. Legacy merged
two-owner primitive wall corners were not assigned fabricated per-owner pixel
anchors; this correction covers the ordinary environment/device/single-prop
routes named in root's bounded assignment.

Correction source pins: item_draw.py
`df0afb5598165b4de6b7e27b709c565e4f9211ace96cc5cf2389a5fc0b7124b3`;
app.py `d3bfbb80ad31d338eaa42907047d842a54906e31d385c4ac6fc8743af9e22b4c`;
fixture_depth.py `83205df7849bc9c0947385f0f3caaed640f971e5b8d623c9ad8db1ae575a9468`;
new object tests `7a73c43e1246e2af425f99c221ee0d4668d26cfe57c971647ecf60f55b1bceb6`;
projectile fixture `37412e1ad93aa077b53bf33b3e06e562663d981210a31b4f3f06d7f0d0d8835d`.
