# Art brief: complete damage-type injury responses

For the existing material-art task, after its current user-directed work.
The production plan is [DAMAGE_MATERIAL_RESPONSES_2026-09-20.md](DAMAGE_MATERIAL_RESPONSES_2026-09-20.md).
Work in the art worktree; do not modify the main game branch or approved exports.

User request: all thirteen damage types need distinct authored responses.
Blood/bone/demonic materials stay recognizable. Spell tint is only a very light
accent (current 6%); color changes alone are insufficient. Strong initial
examples: frozen-looking fragments for cold, brief steam for fire, heavier
splats for force. The plan contains the complete thirteen-row direction table.

Use the **currently integrated** blood High56 material in
`/mnt/c/users/tommaso/documents/dev/dnd_engine/game/data/neuroclient/body-release-regions.json`
as baseline; the older compact blood export was superseded. Preserve bone,
corrosive and dread material identities. Their palettes are not interchangeable.

Produce a comparison page covering every damage type, with fixed subject,
lighting, source point, camera scale and supplied receiving region. Show the
untreated material alongside each response. Include normal/critical controls
and blood/bone/corrosive/dread selection, without requiring a unique atlas for
every combination. Keep true pixel-art resolution and restrained highlights.

Deliver:

- Authored motion/shape response data using the existing normalized fragment
  vocabulary. Preserve baseline depositing particle IDs, landing targets and
  kernels exactly. Delays, durations and airborne shapes may vary; additional
  vapor/sparks/chips that dissipate are explicitly non-depositing detail.
  Keep ground template targets separate from the body source. Supply a concise
  manifest mapping all thirteen damage types to shared response assets/data.
- New finite secondary media only where required: frost chips/mist, hot vapor,
  small crackles, glints/dust. Share useful effects across materials. They must
  not obscure the body, replace a spell impact or create a second large explosion.
- For directional media, actual required views or camera-independent world
  geometry. Give fixed source pivots, phase frames, FPS, world extent, source
  scale, alpha mode and depth expectations. Transparent pixel-art exports with
  nearest-neighbor treatment; no direction approximations by rotating baked
  isometric imagery.
- A human-readable note saying which variations reuse current runtime data,
  which require a small new sampler primitive, and which remain proposals.
  Do not implement a new main-game renderer to prove the artwork.

Constraints:

- Existing native regions own actual material destinations. An optional wider
  force/thunder footprint in the preview is an explicit proposed input layout,
  not a renderer expansion; provide its numerical region separately. In
  particular, widening corrosive/dread footprints changes real hazard reach
  and remains a separate production choice. Use existing regions as the baseline.
- Keep settled material templates/palettes unchanged for this chunk. Airborne
  variation must land into the original receiving contribution. Cold chunks may
  fragment into the existing material marks; new permanent frozen/charred terrain
  is not requested. Vapor/sparks dissipate without creating deposits.
- Supply one complete landing schedule for each response, shared by particles
  and ground reveal. Its finite duration must cover the latest landing. Original
  kernels must not appear before the corresponding material arrives.
- Wet blood and dry skeleton responses differ in silhouette, not just hue.
  Psychic is deliberately sparse; poison damage does not turn blood green or
  assign a new hazard. Existing poisonous/corrosive body material stays itself.
- Existing physical patterns remain approved baselines. Mixed elemental weapon
  hits need a subtle accent layered on that physical response, not replacement
  by a full second injury burst.
- Supply files and a preview to the user in your own task, plus a compact delivery
  path/status to the game task. This is new artwork authoring; game integration
  and event correctness stay with the game task.

Queue rather than interrupt the user's current environment-art corrections.
