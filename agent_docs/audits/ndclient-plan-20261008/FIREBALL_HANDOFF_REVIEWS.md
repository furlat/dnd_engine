# Fireball export / Pixi proof handoff review

Date: 8 October 2026. Scope:
[the dedicated handoff](../../FIREBALL_SINGLE_VIEW_PIXI_HANDOFF_2026-10-08.md),
with the linked mathematics chapter's depth-write correction.

The human requests one-view Fireball at 24 FPS, eight byte channels per depth
layer, followed by an interactive Pixi floor/wall/Globe/light scene. The later
Globe question was resolved from code: all required baseline art and sphere
registration already exist, so the handoff requests no new Globe delivery.
No artwork agent or other Codex chat was contacted. These were local independent
read-only review subtasks mandated by repository instructions.

## Anti-slop review

Reviewer: `fireball_handoff_antislop`. Initial findings and repairs:

1. Combined C/T cannot isolate emission from smoke. Bloom now explicitly uses
   brightness-threshold filtering of visible C and labels that approximation.
2. Current/next frames alone do not bound memory across many different cast ages.
   The proof now measures one and four distinct-age casts, uses separate 128 MiB
   effect-texture and decoded-frame budgets, counts intermediate targets separately,
   and fails its budget check explicitly if the active resource union exceeds it.
3. Peeling selection must write its own current depth attachment. The handoff and
   mathematics chapter distinguish that from final transparent accumulation,
   which does not write scene depth. Previous/current attachments remain distinct.

Final verdict: approved. Reviewer confirmed all three repairs and the reuse-only
Globe subsection against source. Two-band intersections, bloom appearance, analytic
shell registration and memory/performance budgets still need the Pixi proof.

## Anti-OOP / ECS / ownership review

Reviewer: `fireball_handoff_ecs`. Initial and final verdicts: approved.

Offline export, client composition and native applicability have separate existing
owners. No new rules, ECS, SDK schema, reducer, sphere definition or competing
rendering application is introduced. Private assets/originals are preserved.
The local delivery file layout is an importer concern, not another public protocol.
Shared time sampling/material functions remain usable in future Studio/play.

The final review independently confirmed existing Globe radius, projection join,
height scale, art scale, source canvas/pivot, front/back frames and clocks. No new
Globe artist task remains. Proof resource budgets do not become gameplay limits.

## Verification and limits

Checked local chapter links and the byte/timing arithmetic: 48 frames / 24 FPS =
2 seconds; dense two-layer 1536² RGBA8 pairs would total 1,811,939,328 decoded bytes
(1.6875 GiB). This is a deliberately disclosed upper bound, not a delivery size.

This turn writes documentation and reconciles the existing plan. No runtime code,
asset conversion, native gameplay change, shader benchmark or completed preview
is claimed. Those depend on the requested export and bounded client proof.
