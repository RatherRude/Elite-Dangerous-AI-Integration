# Quests Guide (for Creators)

This guide is for people who want to **design quest experiences** in COVAS:NEXT.
No coding knowledge required.

---

## What is a quest?

A quest is a guided story or objective that progresses in **steps**.

Each step is called a **stage**.  
The player does something in-game, and the quest reacts:

- moves to the next stage
- shows instructions
- triggers dialog
- plays sounds
- turns other quests on/off

Think of it like a branching checklist that reacts to gameplay events.

---

## What is an actor?

An actor is a **character profile** used by quests for voice + identity.

An actor gives your quest dialog personality:

- display name (what players see)
- text color
- voice
- avatar image
- optional character prompt/personality notes

When a quest stage triggers dialog, it references an actor.
That is how "who is speaking" is determined.

---

## How quests and actors interact

Quests and actors are connected through dialog and audio actions:

- **NPC Message**: an actor "speaks" a line
- **Play Sound**: a sound can optionally be attributed to an actor voice

In simple terms:

1. You define actors (your cast).
2. You define quest stages (your story flow).
3. In a stage action, you pick which actor delivers each line.

If you rename an actor ID in the editor, actor references in quest actions are updated automatically.

---

## Quest structure in plain language

A quest is made of:

- **Quest info**
  - Quest ID (internal name)
  - Title (player-facing)
  - Description (player-facing)
  - Active on start (whether it starts enabled)
- **Stages**
  - Stage ID (internal name)
  - Description (short stage name)
  - Instructions (what player should do)
  - Choices (rules for how this stage reacts)

Each **Choice** has:

- **Conditions** (what must happen)
- **Actions** (what to do when conditions match)

**Conditions** watch for things that happen in the game—for example docking, jumping, or arriving in a system. In the editor you pick which event should trigger that step. If you're not sure what events exist, start with one the editor suggests and test it.

**Heads-up:** If more than one choice's conditions match the same moment in the game, *all* of those choices run (not just the first). So if two choices both react to "player docked," both sets of actions will fire. Keep conditions specific to avoid surprises.

---

## Available action types (creator view)

### 1) Log

Adds a debug note for you (not player dialog).
Useful while testing.

### 2) Advance Stage

Moves this quest to another stage.

### 3) Set Active

Turns a quest on or off.
Great for chained questlines.

### 4) Play Sound

Plays an audio clip and optional transcription text.
Can optionally use an actor reference.

### 5) NPC Message

Makes an actor speak a line.
Best for story beats and character banter. The AI assistant sees these lines and can respond to them in conversation—so your quest dialog can shape how the AI talks to the player.

---

## Recommended workflow (step-by-step)

### 1) Create your actors first

In **Actors**:

- add all characters you plan to use
- set name, voice, color, avatar
- keep actor IDs stable once used

### 2) Create a quest skeleton

In **Quests**:

- add quest
- set title and description
- choose whether it starts active
- create 2-5 initial stages

### 3) Define stage intent clearly

For each stage:

- description = short "where we are now"
- instructions = what player and AI should do next

### 4) Add one transition first

In the stage’s **Choices**:

- add conditions that detect the event you care about  
  To see what events exist, watch the COVAS:NEXT chat (it prints them as they happen) or check the Elite Dangerous log files written by the game at `C:\Users\%USERNAME%\Saved Games\Frontier Developments\Elite Dangerous`.
- add an action: `advance_stage` to your next stage

Get one transition working before adding complexity.

### 5) Add flavor (dialog/audio)

Now add:

- `npc_message` lines from actors
- `play_sound` where appropriate

### 6) Add fallback paths

Add loops/backtracks for wrong turn cases:

- player left the area
- player died

---

## Designing good stages

Good stages are:

- **clear**: one objective at a time
- **observable**: tied to real in-game events
- **testable**: easy to trigger on demand  
  To test without the game running, you can write events into the Elite Dangerous log file—COVAS:NEXT will read them as if the game had written them.

Good instructions answer:

- what should the player do now?
- where?
- what confirms success?

---

## Practical writing tips

- Keep stage descriptions short and scannable.
- Keep instructions direct and player-facing.
- Use actor voices consistently (same character tone).
- Keep dialog lines short enough for TTS pacing.
- Give every quest a clean ending stage.
- Turn off finished quests with `set_active: false`.

---

## Common pitfalls (and how to avoid them)

### "Nothing happens"

Usually conditions are too strict or mismatched.
Simplify conditions and test one at a time.

### "Wrong actor / empty actor"

Check actor selection in your action.
If you changed actor IDs manually, verify references still point to valid actors.

### "Quest jumps unexpectedly"

Multiple choices can match the same event.
Review all choices in the current stage and make conditions more specific.

### "Quest keeps retriggering"

You likely need an `advance_stage` or `set_active` action to move out of that stage.

### "Save failed" or validation errors

When you save, the editor checks that everything is in order. If it fails, read the message: it usually means something is missing (e.g. an NPC message with no actor chosen) or an action points to an actor or quest that no longer exists. Fix those and try again.

### "Quest feels stuck" after I changed it

The game remembers each player's progress (which stage they're on). If you changed your quest structure a lot, saved progress might not match the new stages. Use the **reset all quests' progress** button in the quest editor when testing after big edits.

---

## Simple quest pattern you can reuse

Use this story rhythm:

1. **Start stage**: detect first key event
2. **Travel stage**: move player to destination
3. **Interaction stage**: dock/talk/collect/do task
4. **Return stage**: bring player back or report in
5. **Outro stage**: final dialog + deactivate quest

This pattern is easy to build, test, and expand.

---

## When to use multiple quests

Use separate quests when:

- you have clearly separate chapters
- you want optional side arcs
- one quest should unlock another

Use `set_active` actions to chain them:

- Quest A outro -> activate Quest B
- Quest A outro -> deactivate Quest A

---

## Quick checklist before saving

- All actors you reference actually exist
- Stage IDs are unique within each quest
- Every stage has clear instructions
- Main path has at least one valid transition
- Ending stage deactivates quest (if intended)
- Dialog lines have correct actor assignments

---

## Final advice

Start small.

Build one short quest that works end-to-end:

- start
- 2-3 transitions
- actor dialog
- clean finish

Once that feels solid, expand into bigger branching stories.

That approach is faster, easier to debug, and much more fun to author.
