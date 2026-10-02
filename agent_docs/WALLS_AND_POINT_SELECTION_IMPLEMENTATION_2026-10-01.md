# Walls and ordered point selection

Authorized scope: finish native SRD walls, the existing game/controller point
selection bridge, and Wall of Fire presentation. Other wall artwork receives a
requirements handoff after native acceptance. Creature content and general multi-Z
are deferred. Preserve approved clouds, windows, attacks and action economy.

## Shared contracts and implementation order

1. Extend the existing immutable position-selection contract, exact discovered
   action bindings and dispatcher into Pygame and AI. The engine alone admits
   subsequent vertices. Clicks collect ordered points; Enter confirms, Backspace
   removes the last point, changing actions clears selection. One point uses the
   native first-cell shorthand; explicit endpoints can include the caster. Never
   enumerate every possible path or reinterpret entity multi-target allocation.
2. Retain polyline/panel geometry where the SRD permits shaped walls. Enforce
   length, panel-count, range, support elevation, placement and physical access
   before costs. Fire/Force/Ice/Thorns/Prismatic straight forms cannot bend. Wind
   and Stone permit contiguous authored segments. Preserve native support height;
   reject unsupported floating/horizontal/stacked placements explicitly.
3. Compose ephemeral solid sections from ordinary world items and Health, owned
   by one retained spatial condition. Existing attacks, destruction events and
   shared physical/optical indexes remain authoritative. Concentration retirement
   removes owned sections through native lifecycle APIs. Do not create a second
   object-attack route, infer mechanics from sprite alpha, or manually mutate
   registries. Ice sections leave frigid air; completed Stone concentration makes
   surviving sections permanent. Force sections are immune to ordinary damage.
4. Implement each wall's actual effects using native saves, damage, conditions,
   movement, spell protection and duration. Wind's projectile and gas restrictions
   require typed delivery/interactions; Thorns requires a real fourfold movement
   cost. Prismatic has independent layers, exemptions, sequential damage and
   removal, blindness, petrification and violet transport. Unsupported mechanics
   must be explicit holds, never silently replaced with generic damage or movement.
5. Connect Disintegrate and existing dispel/interaction sources through typed
   capabilities and native events. Preserve action slots, concentration source,
   effect origin and parent causality. Document unavoidable scope decisions.
6. Read and preserve the delivered Wall of Fire source. Register selected packed
   32 FPS media independently of authored behavior; execute presentation from cold
   retained geometry/events. Straight cardinal coverage is delivered. Ring,
   arbitrary angles and fine occlusion need actual compatible source exports;
   request missing companions, never manufacture XYZ or claim nonexistent banks.
7. Validate each mechanic, costs and discovery/execution agreement, controller
   selection, cold event serialization, cleanup, damage/destruction and support
   elevation. Run focused checks, then the complete engine and affected active
   game/controller checks. Report unrelated failures from the existing triage.
   Produce real-map, four-camera, saved-event Fire reviews using original H1 tiles.
8. Update the recovery checkpoint and prepare remaining walls' visual requirements
   from the final typed native geometry, triggers, lifecycle and supported shapes.

## Review gates

Before edits: independent anti-slop and anti-OOP/ECS review of this scope and its
native ownership choices. Before completion: both review implementation, with
special attention to controller authority, solid-section lifecycle, shared attack
delivery and retained rendering facts. No new behavior superclass hierarchy.

## Acceptance matrix

Fire: existing appearance/contact/heat, form/side, protection and concentration
regressions remain passing. Force: physical barrier, ethereal restriction, push,
immunity, Disintegrate, retirement. Ice: appearance push/save, section HP/AC/fire
vulnerability, residual-air crossing/upcast and retirement. Stone: panel budget,
stone support, displacement/enclosure, thickness/HP, permanent completion versus
early retirement. Thorns: opacity, fourfold movement, distinct piercing appearance
and slashing entry/turn end, first-per-turn and upcast. Wind: shaped placement,
appearance save, ordinary projectile miss, large projectile passage,
small-flying/gaseous passage and native gas interaction. Prismatic: no concentration,
invalid-through-creature cost semantics, caster/exemption, layer order, layer
removal, aura blindness, indigo tally and violet transport semantics.

Reference: 2014 SRD spell entries at
https://www.dndbeyond.com/sources/dnd/basic-rules-2014/spells.

## Completed checkpoint — October 1

Ordered point selection now reaches native execution through both Pygame and AI.
The engine supplies legal subsequent points; the controller caches these by the
current discovered choices and selected prefix. Click or P adds a point, Enter
confirms and Backspace removes a point. Space retains its pause behavior. The
primary target preview remains anchored to the selected origin. AI coordinates
are immutable strict integer pairs; invalid allocations, including points on
End Turn or non-path actions, receive typed rejection before costs.

Validation: 16 point-selection/session checks and 66 encounter, AI, controls and
Wall of Fire checks passed (**82 total**). Scoped typing for the seven changed
production modules reports **0 errors, 0 warnings**. Both independent anti-slop
and anti-OOP/ECS reviewers approved the corrected implementation. This checkpoint
does not claim a new full engine-suite run or complete implementation of all walls.

## Reviewed remaining native requirements

- Solid sections use ordinary WorldItem, Health and multi-cell placement, with
  one item per actual rules section. The retained condition records section UUIDs;
  inventory ownership and physical support links must not encode spell ownership.
- Ice residual air follows completed destruction after physical placement clears,
  using the previous section footprint. Expiry or concentration retirement must
  not create residual air. Remaining spatial coverage must follow surviving
  sections and residual air, rather than a stale original shell.
- Stone permanence belongs in successful duration progression at 100 rounds,
  before removal prepares descendants. Detach concentration ownership while
  retaining surviving ordinary sections; early termination retires them.
- Force immunity covers all damage types. Disintegrate must extend its existing
  typed route to destructible sections. Native ethereal travel is absent, so that
  restriction remains an explicit capability gap.
- Wind ordinary arrow/bolt misses occur after attack costs. Large missiles are
  exempt; magical ammunition is not granted a blanket exemption. Delivery facts
  belong to native attack data, independently of VFX projectile classification.
  Gas dispersal uses native spatial interaction; passage needs a gas-specific query.
- Thorns needs a shared movement factor after ordinary difficult-terrain handling;
  a tile modifier or difficult-terrain exemption must not erase its fourfold cost.
- Prismatic failed creature-overlap placement consumes its rules-defined costs.
  Its light, antimagic immunity and independent sequential layers require native
  owners. Violet planar transport remains a hold: current banishment cannot stand
  in for permanent transport to a chosen plane without native planar semantics.
- Deferred multi-Z does not permit silently approximating floating, horizontal or
  stacked forms. Supported ground placements retain their native elevation.

## Wall of Fire artwork received; production integration pending

Received source:
`/home/tommaso/.codex/worktrees/1aac/dnd_engine/output/weapon-vfx/fire-spells-review/interactions/production-handoff/wall-of-fire/HANDOFF.md`.
The accepted donor has cardinal straight front/back banks, four cameras, 32 FPS,
48 formation frames and a 64-frame hold. It lacks compatible XYZ companions,
ring and arbitrary-angle coverage. Numerical rules dimensions still require
registration against measured source geometry; exporter dimensions alone do not
establish the native one-foot width and twenty-foot height.

The artist supplied GEOMETRY_ASSESSMENT.md alongside the handoff. Future XYZ must
come from the actual deformed fragment geometry with the same seed, preprocessing,
sample times and pivots as accepted RGBA. XYZ cannot supply missing ring artwork.
The human paused Godot rendering in that chat, so further GPU exports remain on
hold. No artwork was imported or moved at this checkpoint; approved cloud and
window rendering remain unchanged.

Status: point-selection checkpoint complete and reviewed. Remaining native walls
and Wall of Fire production presentation are pending; crash diagnosis is handled
by the other agent at the user's request.

## Active follow-up — delivered Fire media integration

The human requested wiring the received Wall of Fire VFX and testing a real cast
end to end. Extend the existing maintained spatial binding with an explicit
cardinal wall-module layout and axis/variant media selection. Use original crop
offsets, pivots, numerical camera projection and native front/back layers. Native
retained wall geometry and currently disclosed flame cells supply placement;
heat cells never acquire flame media. Reuse the existing creation/hold/removal
clock and normal world painter. Import media registration separately from authored
spell/binding behavior; preserve sources and copy selected pages into private
production storage and the ignored installation.

Acceptance: native discovered point allocation -> cast -> cold player replay ->
formation, hold, exposure damage and concentration clear, for both cardinal axes
and four cameras. Reject rendering unsupported ring/diagonal geometry explicitly
in presentation coverage rather than silently substituting a circle or rotated
billboard. Keep native support elevation; no cloud/window changes or GPU exports.
Independent anti-slop and ECS reviewers check this bounded implementation.

### Delivered Fire presentation checkpoint

The selected cardinal delivery is installed and wired. The passive wall adapter
uses received flame positions and native support height, independently authored
axis/variant tables, original crop pivots and native camera rows. No hot-side
damage cells become flame cells. The 48-frame application and 64-frame hold share
82 original pages (31,027,806 bytes); all pinned originals and handoff records are
preserved privately. Initialization rejects missing alternate bank references,
invalid clocks, hold bounds and incomplete cameras. Original registration uses
pixel scale 1 on 128×64 supports, independently of the 64-pixel actor rig.

Native ordered discovery/cast, cold player-packet replay, formation, two-second
hold repetition, actual exposure damage, elevated support and concentration clear
pass six new tests. Relevant wall/point-selection/maintained-field/body-action/
coverage/XYZ ownership regressions pass 267 tests. Scoped production typing has
zero errors/warnings. This is not a full repository-suite rerun.

[Eight saved-event clips](http://127.0.0.1:8767/runs/20261001T180350Z-5ce5e7/index.html)
pass their recorded checks, with zero observed binding gaps. They include X/Y,
raised support and a retained hold, paired caster/target views in four cameras.
Formation, hold and removal frames were inspected. No rendering approval is
inferred from passing checks. Both independent anti-slop and ECS reviewers found
no blocking issue in the delivered scope. No cloud/window or native rules changed.

### Remaining wall artwork handoff contract

Wall of Fire still needs ring and arbitrary-angle banks, measured world dimensions
and genuinely matching XYZ/ownership companions before precise spatial clipping
can be claimed. Current cardinal crops are visually registered, but do not certify
the native twenty-foot height or fine actor occlusion. Coverage remains partial;
unsupported forms report gaps instead of borrowing or rotating other artwork.

For the remaining SRD walls, exports must identify the supported native shape,
segment axes or angular samples, measured width/height, support-plane origin,
all four camera projections, pivot/crop offsets and sample times. Separate
formation, sustained and removal windows explicitly. Keep native section/layer
identity for destructible Stone/Ice sections and Prismatic layers; retained state
must select surviving artwork. Any XYZ companions must come from the same actual
deformed geometry and temporal samples as the RGBA. Preserve complete originals,
install only selected shared production pages, and keep media registration
separate from gameplay authoring. Backend work for other walls remains pending;
this checkpoint neither registers their rules nor requests new GPU exports.
