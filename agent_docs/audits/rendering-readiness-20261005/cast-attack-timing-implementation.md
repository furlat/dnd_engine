# Cast/attack producer timing evidence — implementation handoff

2026-10-05. This is an implementation receipt, not independent approval.

## Implemented scope

- Both existing cast compilers retain measured release frames/FPS/playback speed.
  Anchored contacts retain launch/contact delays, distance and facing-cell delays,
  disclosed propagation joins and line-distance contacts. Projectile contacts
  retain preparation joins, per-application stagger, travel duration inputs and
  ground-delivery sharing. Application identity remains distinct for A/B/A.
- Attack binding records melee contact or ranged release, projectile travel and
  disclosed interception fraction. It uses the selected original profile/clip.
- `compile_damage` optionally records its existing impact-delay and HP callback
  calculations into the owning compiler's passive evidence list. Terminal/lethal
  immediate callbacks stay immediate. Callers not providing evidence preserve the
  original return and behavior. No callback scheduling was introduced.
- Existing repeated-target HP callback flushing records its minimum against actual
  later same-target damage starts. This does not alter that existing policy.
- Existing AreaReach destruction prerequisites now record their known clearance
  floors. A later staged-area recipient delay appends final contact and damage/HP
  shift evidence. The offset references the two existing contact producer stages
  whose difference produced the shift; validation checks that difference. Original
  max/shift equations remain the playback authority.
- Shared dependency projection includes cast/attack scopes separately from the
  surrounding choreography scope: these may share a root UUID but have independent
  stage indices. Interrupted actions are omitted from this new dependency view,
  avoiding emission of canceled future delivery as an admitted relation.
- Cast references use a discriminated passive string-ID record because CastInput
  permits detached compiler labels as well as native UUID strings. Native event,
  object and field references remain UUID typed. This avoids UUID/string union
  coercion changing identities during JSON roundtrip.
- `MotionTimeline.root_uuid` retains the actual source root on both ordinary and
  jump producers; the shared walker uses it only when no explicit containing cue
  owner was supplied. No actor-ID inference.

## Corrections from initial-lane independent review

Clearance targets now use object kind for known object/section identities.
Construction formation/clearance inputs retain contributor_object_uuid and the
specific catalog property selected for its offset. Existing before/states fields
on MotionGroupSource are preserved. Initial-lane focused suite passed 11 tests
in 49.11s after these corrections.

## Verification and limits

185 existing cast/volley/area/attack tests passed before final annotation
refinements. Added boundary checks verify exact A/B/A HP admissions and callback
flush, real ranged/melee contact and HP, and fireball breach clearance/final shifted
HP provenance. The final focused run and scoped typing are recorded below.

The compiler changes preserve sampled dates and geometry; this receipt does not
claim new pixel acceptance. Production edits are limited to passive evidence and
retained root identity. No gameplay, art, recipe, narrative, UI or trace-consumer
changes are part of this lane.

## Still remaining in plan D

- Body/recovery/completion joins, including staged-area decorative impact stretching.
- Child action ordering, movement-parent completion, displacement/portal settlement,
  condition consumption release, and reaction alignment/interruption provenance.
- Standalone damage/heal, equipment and lifecycle producer annotations.
- Movement leg/dwell/connector/reaction/recovery timing dependencies; current state
  provenance and root identity are evidence, not those equations.
- Retained condition/item/spatial/construction/deposit lifetime causal relations.
- Cast/attack evidence inside drawable groups omitted from the retained motion
  reaction tree: MotionGroupSource currently retains its choreography evidence,
  but not every contained cast/attack compiler table. This is explicit incomplete
  coverage, not a claim that those groups had no cast delivery.

No generic scheduler or repeated family policy was extracted. Validation certifies
only the recorded local stages and explicit references; externally measured
anchors remain externally measured anchors.


Superseding checkpoint: final cast/attack/AreaReach focused validation passed 72 tests. Discarded group evidence is now retained by MotionGroupSource.action_timing and shared bound_action_dependencies. See timing-producer-completion-ecs.md for subsequent body, movement, reaction and standalone producer completion.
