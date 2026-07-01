# Abilities.md - Implementation Notes

## Status: MOSTLY COMPLETE

Core ability system is solid. Missing pieces are low priority.

## Fully Implemented
- Ability scores 1-30 with modifier formula `(score-10)//2`
- All 6 abilities (STR, DEX, CON, INT, WIS, CHA)
- All 18 skills with correct ability mappings
- Proficiency and Expertise for skills
- All 6 saving throws with proficiency
- Finesse weapons (uses higher of STR/DEX)
- Advantage/Disadvantage cancellation logic

## Not Implemented (Low Priority)

### Initiative
- Just a DEX-based ModifiableValue when needed
- No turn system exists yet anyway
- Trivial to add: `initiative: ModifiableValue` on Entity

### Passive Checks
- Formula: `10 + modifiers` (+5 advantage, -5 disadvantage)
- Useful for stealth/perception but not urgent
- Trivial: computed property on Skill block

### Contests (Opposed Checks)
- Both roll, compare, tie = status quo
- Needed for grapple/shove eventually
- Trivial: utility function comparing two rolls

### Help Action
- Gives advantage to leader
- Just applies advantage modifier
- Trivial when we need it

### Carrying Capacity
- STR × 15 lbs carrying, STR × 30 push/drag
- Inventory system not in scope yet

### Variant: Skills with Different Abilities
- GM option, not core rule
- Would need skill check to accept ability override parameter

## Notes for Future
- When turn-based combat is added, initiative becomes relevant
- When stealth system is fleshed out, passive perception matters
- These are all simple additions to existing ModifiableValue system
