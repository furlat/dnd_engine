# Shared binding and text boundary — ECS review

2026-10-05. Independent current-code review. Scope: corrected movement evidence, shared bind_presentation_group, headless replay inputs/ownership/imports. Narrative wording/timestamp policy is under separate review and is not certified here.

**Approve these bounded ECS boundaries.**

- MotionGroupSource contains exact native reduction inputs and existing commit records. Previously discarded zero-duration/departure groups no longer leave unresolvable evidence references. It does not retain duplicate graphical trees or execute a second reducer.
- bind_presentation_group centralizes the existing bind_motion-then-bind_choreography choice. Encounter and recorder now use that function; graphical resource loading stays in their existing adapters. Native group/reaction ancestry and reduce_presentation_group ordering remain unchanged.
- text_replay accepts the saved public PlayerSequence through the existing decoder and reducer. It does not open private recordings or live ECS entities. It uses the same binding choice, existing end-of-head body sampler for settled facing/position, and existing condition registration for activation history. No duplicate condition/death/movement rule implementation was found.
- NarrativeReplay is passive output, not a registry or controller. Persistent surface/construction/item samplers need not be rerun solely for text unless their presentation dates become semantic inputs; that later expansion must reuse their owners.
- Current description state derives from observed/remembered PlayerState; the code explicitly distinguishes last-known entities. Broader text coverage of tiles/world conditions and effects remains an outstanding feature, not claimed complete by this review.

Checks executed: explicit game/animation-review import graph has no cycles. A fresh interpreter rejecting every Pygame import loaded the current catalog and replayed the retained schema-2 persistent-shield public sequence through text_replay, yielding 31 entries and 6500 ms. This proves the tested headless path executes; it does not certify wording, all-family narrative coverage, exact timestamp parity or pixels. No production edits by this reviewer.
