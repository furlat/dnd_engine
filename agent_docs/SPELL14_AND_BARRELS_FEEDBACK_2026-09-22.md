# Latest fourteen spells and barrels — focused feedback handoff

[Open the focused gallery](http://127.0.0.1:8767/runs/20260922T113258Z-latest-spells-and-barrels/index.html). This replaces the overly broad 181-clip
collection for the current review: **62 latest-spell clips and 28 existing barrel
clips**, with paired subjective perspectives and four synchronized cameras per clip.
Use `review:new-14` or `review:barrels` to select a group. Mark an issue, name the
camera and export its trace; original saved input and capture identities are retained.

## Blood correction

The persistent-spell review actors omitted the existing blood-response composition.
Their damage was real, but the captured events consequently had no body release.
The fixture now installs `BLOOD_BODY_RESPONSE` through `install_body_response`, as
other humanoid fixtures already do. No engine rule, renderer behavior or asset was
changed for this correction. Canceled hits and nondamaging effects stay nondamaging.

All 18 affected injury experiments were recorded again through real native commands,
producing 36 replacement clips. Saved injuries retain material release facts and
persistent floor residue. Valid nondamaging spell recordings and the existing barrel
recordings are reused. The gallery excludes the earlier 45 spell presentations.

## Included spell batch

Mage Armor; Shield; Protection from Energy (all five elements); Grease;
Spike Growth; Fog Cloud; Cloudkill; Stinking Cloud; Darkness; Incendiary Cloud;
Insect Plague; Blur; Mirror Image; Enlarge/Reduce (both modes).

Variants include protection removal and subsequent damage, real Shield interception
versus critical damage, equipment changes, terrain entry/saves and next-turn recovery,
jump contacts, hidden/discovered thorns, cloud boundaries and elevation, upcast Fog,
subjective visibility, duplicate depletion and size-dependent body/attachment alignment.
They are recorded gameplay stories, not renderer-only event imitations.

## Verification and preserved limits

- 43 focused persistent-gameplay/body-release tests pass; changed-module typing is clean.
- All 36 replacement clips pass their capture checks. Saved-input inspection confirms
  25 positive damage facts in the injured actors' own perspectives retain blood and
  deposited material; their final subjective ground state contains blood. Foreign
  unseen effects are not required to disclose extra information.
- MP4 review checks actual blood and floor stains through both perspectives and four
  cameras. Automated checks and our visual review are not a claim of human approval.
- Gallery membership, all referenced files, replacement origins and browser trace
  export are checked. The original 1,476 engine / 2,120 game test results predate this
  fixture-only correction; they were not rerun unnecessarily.

Barrels cover water, oil, grease, poison, normal blood and dread blood. Their existing
production clips are retained; previously identified source-coverage corrections
remain queued. Wet has native state but no bound body media. Burning-surface artwork
is outside this unit. Upcast Fog uses a wide review frame, and Stinking Cloud's story
shows a successful Constitution save rather than its failed-save nausea branch.

## Evidence

Replacement source runs: `20260922T112436Z-49a41f`,
`20260922T112436Z-298fe4`, `20260922T112438Z-1226dd`.

Local diagnostic evidence under `.runtime/spell14-20260922/`:
`blood-after.log`, `blood-typing.log`, `blood-capture-audit.json`,
`visual-blood-correction/`, `feedback-browser-blood.log`.
The broader implementation record remains [SPELL14_INTEGRATION_2026-09-22.md](SPELL14_INTEGRATION_2026-09-22.md).
