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
Best for story beats and character banter.

---

## Recommended workflow (step-by-step)

## 1) Create your actors first

In **Actors**:

- add all characters you plan to use
- set name, voice, color, avatar
- keep actor IDs stable once used

## 2) Create a quest skeleton

In **Quests**:

- add quest
- set title and description
- choose whether it starts active
- create 2-5 initial stages

## 3) Define stage intent clearly

For each stage:

- description = short "where we are now"
- instructions = what player should do next

## 4) Add one transition first

In the stage’s **Choices**:

- add conditions that detect the event you care about
- add an action: `advance_stage` to your next stage

Get one transition working before adding complexity.

## 5) Add flavor (dialog/audio)

Now add:

- `npc_message` lines from actors
- `play_sound` where appropriate

## 6) Add fallback paths

Add loops/backtracks for wrong turn cases:

- player left the area
- jumped away
- undocked too early

---

## Designing good stages

Good stages are:

- **clear**: one objective at a time
- **observable**: tied to real in-game events
- **testable**: easy to trigger on demand

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
# Quest System

This document describes the complete quest system used by COVAS:NEXT: data format, runtime behavior, editor workflow, and troubleshooting.

## What the quest system does

At a high level, quests are event-driven state machines:

- A quest has stages.
- Each active quest listens to incoming game/status events.
- Each stage has plan steps (`conditions` + `actions`).
- When a step's conditions match the current event, its actions run.
- Actions can advance stages, activate/deactivate quests, log, play audio, and emit NPC dialog.

Quests are defined in `src/data/quests.yaml`.

## Architecture overview

Core pieces:

- **Catalog storage and validation**
  - `src/lib/QuestCatalogManager.py`
  - Loads/saves `src/data/quests.yaml`
  - Validates structure and action requirements before save
- **Runtime quest engine**
  - `src/lib/Assistant.py`
  - Loads quest catalog + actors
  - Syncs quest state to DB
  - Evaluates conditions and executes actions on incoming events
- **Quest state persistence**
  - `src/lib/Database.py` (`QuestDatabase`, table `quests_v1`)
  - Stores per-quest `quest_id`, `stage_id`, `active`, `version`
- **Event transport**
  - `src/lib/EventManager.py`
  - Emits `QuestEvent`s for quest updates/audio/dialog
- **Prompt/LLM representation**
  - `src/lib/PromptGenerator.py`
  - Converts non-audio quest updates into natural language context
  - Converts `npc_message` into a special conversation line for the model
- **UI quest editor**
  - `ui/src/app/components/quests-settings/quests-settings.component.ts`
  - `ui/src/app/services/quests.service.ts`
  - Reads and saves the catalog via backend messages

## Catalog file and schema

- Main file: `src/data/quests.yaml`
- JSON schema reference: `src/data/quests.schema.json`

Top-level shape:

```yaml
version: "1.0"
actors: []
quests: []
```

### Top-level fields

- `version` (string): used to determine whether persisted quest states should be reset to new defaults.
- `actors` (array): reusable speaker/audio actors.
- `quests` (array): quest definitions.

## Data model

### Actor

Required fields:

- `id` (string)
- `name` (string)
- `name_color` (hex color string, e.g. `#7cb3ff`)
- `voice` (string)
- `avatar_url` (string; URL or `avatar://<id>`)
- `prompt` (string)

Actors are referenced by action `actor_id`.

### Quest

Required fields:

- `id` (string)
- `title` (string)
- `description` (string)
- `stages` (array)

Optional:

- `active` (boolean): initial active state when first loaded/synced.

### Stage

Required fields:

- `id` (string)
- `description` (string)
- `instructions` (string)

Optional:

- `plan` (array of step objects)

### Plan step

Required fields:

- `conditions` (array)
- `actions` (array, at least 1 action)

### Condition

Fields:

- `source`: currently only `"event"` is supported
- `path`: dot path in incoming event payload (`event.XXX` prefix optional)
- `operator`: `"equals"` or `"=="`
- `value`: `string | number | boolean | null`

### Action types

Supported action names:

- `log`
- `advance_stage`
- `set_active`
- `play_sound`
- `npc_message`

Required per action:

- `log`: `message`
- `advance_stage`: `target_stage_id`
- `set_active`: `quest_id` (optional `active`, defaults `true`)
- `play_sound`: `file_name`, `transcription` (optional `actor_id`)
- `npc_message`: `actor_id`, `transcription`

## Runtime lifecycle

### 1) Loading quests

On startup and on `LoadGame`, the assistant loads `quests.yaml`:

- Normalizes actors (`prompt`, `name_color` defaults if missing)
- Builds in-memory maps:
  - `quest_catalog: {quest_id -> quest}`
  - `quest_actors: {actor_id -> actor}`
- Calls `_sync_quests_to_db()`

### 2) Syncing to persistent quest state

For each quest:

- If no DB state exists:
  - initialize at first stage
  - set `active` from quest's `active` field
  - store current catalog `version`
- If DB state exists and catalog `version` is newer:
  - reset quest to first stage + default active state
  - overwrite stored version

Version comparison is numeric by dot segments (`1.10` > `1.2`).

### 3) Processing events

On every incoming event, runtime loops all active quests:

- Fetch current stage from DB
- Read that stage's `plan`
- Evaluate each step's `conditions`
- Execute all actions of each matching step

Important: matching steps do **not** short-circuit. If multiple steps match one event, all of them run.

## Condition evaluation details

### Source and path

- Source must be `event`.
- For `GameEvent`, values come from `event.content`.
- For `StatusEvent`, values come from `event.status`.
- `event.` prefix is optional:
  - `event.StarSystem` and `StarSystem` both work.

### Equality behavior

The comparison logic supports:

- numeric-string coercion (`"300000"` equals `300000`)
- direct equality for strings/bools/others

Note: if the resolved value is missing (`None`), equality returns false.

## Action behavior in detail

### `log`

- Writes debug log only.
- Does not emit audio or dialog by itself.

### `advance_stage`

- Validates target stage exists in the same quest.
- Sets DB state to:
  - `stage_id = target_stage_id`
  - `active = true` (always)
  - version preserved from existing row (or current catalog version fallback)
- Emits a `QuestEvent` with:
  - `action: advance_stage`
  - quest + stage metadata

### `set_active`

- Target quest may be same quest or different quest.
- If target quest has no DB entry:
  - initializes target on its first stage
  - applies requested active state
- If target quest exists:
  - only updates active flag
- Emits a `QuestEvent` with `action: set_active`.

### `play_sound`

- Requires valid `file_name` (`.mp3`/`.wav`) and `transcription`.
- Optional `actor_id`:
  - if actor exists and has voice, that voice is attached to event payload
- Emits quest audio event via `EventManager.add_play_sound(...)`.

### `npc_message`

- Requires valid `actor_id` and `transcription`.
- Actor must exist and have `voice`.
- Enriches event with:
  - `actor_name`
  - `actor_name_color`
  - `avatar_url`
  - `prompt`
- Emits via `EventManager.add_npc_message(...)`.

## How quest events appear in chat/LLM context

### Non-audio quest updates

`advance_stage` and `set_active` are rendered into readable event text in prompt context, for example:

- "Quest updated: ... advanced to stage ..."
- "Quest activated/deactivated: ..."

### Audio and dialog quest actions

- `play_sound` and `npc_message` are intentionally omitted from generic event text.
- `npc_message` is transformed into a conversation-style prompt line:
  - `[Quest dialog] <Actor Name> said: <Transcription>`

This allows the assistant to react naturally to quest dialog without duplicating event noise.

## UI editor behavior

Quest editor is in the advanced settings UI:

- Loads catalog through backend command `get_quest_catalog`.
- Saves via `save_quest_catalog` with server-side validation.
- Includes:
  - quest list
  - actor list
  - stage graph (node map)
  - per-stage conditions/actions editor

Recent editor improvements include:

- ID edits committing on blur to avoid selection flicker
- actor ID rename propagation into `action.actor_id` references
- robust graph lifecycle when switching between actor/quest panels

## Backend API messages used by UI

From UI to backend:

- `get_quest_catalog`
- `save_quest_catalog`

From backend to UI:

- `quest_catalog` with `{ data, raw, error, path }`
- `quest_catalog_saved` with `{ success, message, data, raw }`

## Authoring guide

### Minimal quest template

```yaml
version: "1.0"
actors:
  - id: guide
    name: Guide
    name_color: "#7cb3ff"
    voice: "en-US-AvaMultilingualNeural"
    avatar_url: ""
    prompt: ""
quests:
  - id: sample_quest
    title: Sample Quest
    description: Demonstrates transitions.
    active: true
    stages:
      - id: start
        description: Wait for a jump.
        instructions: Perform an FSD jump.
        plan:
          - conditions:
              - source: event
                path: event
                operator: equals
                value: FSDJump
            actions:
              - action: npc_message
                actor_id: guide
                transcription: Nice jump, Commander.
              - action: advance_stage
                target_stage_id: done
      - id: done
        description: Complete
        instructions: Quest complete.
        plan:
          - conditions: []
            actions:
              - action: log
                message: Sample quest completed.
              - action: set_active
                quest_id: sample_quest
                active: false
```

### Authoring tips

- Keep IDs stable; they are references across actions.
- Use explicit event-name checks in conditions (`path: event`) to avoid accidental matches.
- Prefer one clear transition per condition set.
- If multiple transitions can match one event, be aware all matching steps run.
- Bump `version` when shipping structural quest changes to reset persisted stage state safely.

## Validation rules and common save errors

Validation runs server-side before write. Frequent errors:

- missing required fields (`id`, `stages`, etc.)
- invalid action payload (e.g. `npc_message` missing `actor_id`)
- unknown `actor_id` reference in actions
- wrong field types (`active` not boolean, etc.)
- invalid operator/source in conditions

If save fails, UI receives one combined error message from `quest_catalog_saved.message`.

## Troubleshooting

### Quest does not trigger

Check:

- quest is active in DB (or default `active: true` and version sync happened)
- condition `path` matches real incoming event payload keys exactly
- value type matches (string vs number/boolean)
- event type is actually processed as `GameEvent`/`StatusEvent`

### Stage never advances

Check:

- `target_stage_id` exists in same quest
- step conditions are not too strict
- another matching step is also firing and moving stage unexpectedly

### NPC message not spoken

Check:

- actor exists in `actors`
- actor has non-empty `voice`
- `actor_id` spelled exactly
- `transcription` non-empty

### Quest state seems stale after catalog edits

- Increase catalog `version` to force reset to first stage/default active for existing quests.

## Notes and limitations

- Condition operators beyond equality are not currently supported.
- Condition source is currently only `event`.
- Runtime has some tolerance for optional/missing fields, but save-time validation is strict.
- Stage-level `conditions` are read by runtime but are not part of the current schema/editor contract; prefer conditions inside plan steps.

## Related files

- `src/data/quests.yaml`
- `src/data/quests.schema.json`
- `src/lib/QuestCatalogManager.py`
- `src/lib/Assistant.py`
- `src/lib/EventManager.py`
- `src/lib/Database.py`
- `src/lib/PromptGenerator.py`
- `ui/src/app/components/quests-settings/quests-settings.component.ts`
- `ui/src/app/services/quests.service.ts`
