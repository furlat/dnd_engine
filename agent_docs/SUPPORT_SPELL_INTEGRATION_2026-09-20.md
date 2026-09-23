# Support spell integration

**Later user correction:** Fire Bolt’s normalization described below was rejected. Its original authored projectile record is restored, with both standing reference videos byte-identical to the earlier approved output. See [Sleep and Fire Bolt correction](SLEEP_POSE_CONTACT_2026-09-20.md). Other spell placement changes are unchanged.

## Scope and acceptance

Integrate the frozen `support-healing-v1` handoff after the Poison delivery
correction. Source: `/home/tommaso/.codex/worktrees/1aac/dnd_engine/output/weapon-vfx/support-spells-review/delivery`.
The eight support spells are Cure Wounds, Healing Word, Prayer of Healing,
Guidance, Resistance, Shield of Faith, Light and Thaumaturgy. True Strike uses
only the supplied exact-pose shortsword/bow overlays on its actual child attack.
The donor sword and donor Attack5 preview are excluded.

The observable boundary is saved subjective event histories replayed through
the ordinary compositor. Real discovered actions must produce actual healing,
condition membership, illumination or weapon attacks; presentation samples those
facts at authored contact. Both participants and all four cameras are captured.
Nearby unselected Prayer recipients must remain unaffected. Cast effects never
invent damage, conditions, targets or durations. Artist review is not human
approval.

## Shared implementation

1. Copy finite back/front media and quiet condition images, retaining literal
   palette, alpha, all 144 Hz frames, declared ground pivot and fixed scale.
   Author recipes separately. Reimport changes media/registration only.
2. Permit an anchored source-only cast when the actual spell has no recipient.
   Use its retained facing, authored source track and release/contact clock.
   Thaumaturgy must not acquire a fabricated self-target application.
3. Commit actual HealFact after-values at its inherited contact in the existing
   compiled state sequence. A non-damaging cast must not keep overwriting HP
   with its starting contact. Preserve standalone healing and actual revival;
   no damage reaction or new feedback framework.
4. Use existing static condition layers and real membership/removal. Existing
   composition selects recipes; remove the second physical-layer truncation
   which can cut a selected back/front pair. Guidance/Resistance/Shield share
   the body group (maximum three); Light has an illumination group (one).
   Do not change native concentration rules as part of an art integration.
5. True Strike keeps the real Attack action and its selected melee/ranged
   recipe, timing, equipment and hit/miss results. Bind its runtime action
   identity through the existing admission gateway. An explicitly authored
   child-attack presentation binding selects exact category/clip overlays;
   literal source sheets use the existing actor-layer loader, without ordinary
   rig category substitution. No extra caster gesture or attack recipe copy.

## Verification and review

Independent anti-slop and anti-OOP/ECS reviews inspect ownership, the observed
gaps and the bounded extension before implementation. Add native scenarios for
healing, two actual Prayer recipients plus an injured unselected actor,
condition application/removal/stacking, Light in darkness with movement, and
True Strike melee/ranged hit and miss. Tests inspect event ancestry, real HP and
condition state, contact timing, seek determinism and rendered layer ownership.
Reimport tests protect recipe ownership, not source hashes.

Run focused native/presentation regressions and typechecks. Record once, replay
the saved inputs into a labelled gallery, inspect representative rendered frames
and seek independent final review. Document exact results and limitations.
No runtime audits, visual regression framework, speculative spell mechanics or
asset reauthoring are part of this work.

## Progress

Independent anti-slop and ECS reviews approved the bounded plan. Both traced
the actual source-only and nested-healing gaps; the HP review confirmed why
adding a state commit alone would be overwritten by non-damaging cast samples.
The ECS review confirmed the supplied charge alpha is already baked into exact
weapon-pose sheets, so no opacity-envelope executor is needed. Implementation
is complete. Support visual priorities precede the existing invisible
Concentrating recipe, so it cannot consume one of their three visible slots.

## Implementation result

- Eight finite support recipes use the frozen media, and Guidance, Resistance,
  Shield of Faith and Light retain their delivered quiet back/front condition
  poses. The stacked case exercises all eight physical layers, movement and
  independent removals. No actor-wide tint or new condition lifetime is invented.
- Thaumaturgy uses a real source-only cast and retained facing. No self-target
  application is fabricated to satisfy the renderer.
- Healing enters the existing state sequence at contact and survives the media
  tail and backward seeking. Standalone `CastSample` still supplies passive HP
  snapshots: only the lineage compositor filters their ownership, preventing a
  non-damaging sample from overwriting an actual received heal. The first full
  regression run caught that distinction; it was repaired at the compositor.
- Light's native illumination changes now retain their actual application and
  removal parent events. Brightening, movement and removal therefore replay in
  the same complete lineage at the owning effect contact.
- True Strike owns its native child weapon attack through `childAttack` data.
  Exact shortsword/Attack6 and shortbow/Attack3 charge overlays use the existing
  actor layer loader and baked alpha. Other weapons keep their real attack with
  an explicit missing-overlay report; no approximate substitute is silently used.

The native scenarios record both participants once; render replay consumes only
their saved public event packets. The first combined review contained 67 views
and 7,955 four-camera frames. Root inspected support contacts, Prayer's selected
recipients, True Strike, Shocking Grasp and the shared incoming-projectile
points. The user's expanded request now includes every selected spell recipe;
its final catalog evidence and validation are recorded in
[the complete spell review](AUTHORED_SPELL_REVIEW_2026-09-20.md).

Final validation:

- Complete game selection outside the recorder test file: **1,445 passed,
  6 existing expected terrain-occlusion failures** (567.68 s on WSL with source
  under `/mnt/c`). No ordinary failures remain in that run.
- The separate recorder test file: **8 passed** (162.76 s), including actual
  videos, framing, failure reporting, saved input replay and paired views.
- Final Magic Missile / shared contacts / cast / device regression selection:
  **113 passed** (33.18 s), including the four extra target configurations added
  after the full selection was collected. This overlaps the full selection.
- Current spatial/rig selection before that last addition: **79 passed**;
  exact drawn targets now cover eight spells × two rigs × two scale/height
  settings, each with four cameras. Historical G5 numeric tests explicitly load
  their original imported recipe; current rig tests compare feedback relative
  to each rig's actual arrival instead of requiring identical torso geometry.
- Native True Strike/support selection: **5 passed**. Support gallery producers
  and paired public replay tests also execute real native actions in the main
  game selection.
- Selected presentation, importer and scenario typechecks: **zero errors**.
  Independent anti-slop/ECS reviews approved the shared ownership changes,
  native visibility examples and authored attachment normalization.

The six expected failures remain the already documented terrain painter defects
for airborne/forced movement. They are not spell binding failures or silently
skipped checks. This work adds no new expected failures.
