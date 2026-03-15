# Event reactions

Event reactions (also called event triggers) are in-game events that the AI can respond to. When something happens in Elite: Dangerous like taking damage, entering a new system, docking, receiving chat, and so on-the integration can send that event to the AI so it can react with a message or suggestion. There are event categories and a search option to help you find for the relevant ones of the hundreds of events.

## The three reaction settings

Each event type has **three possible states**:

| Setting | Meaning |
|--------|--------|
| **React** | The AI is notified of the event and may comment or suggest actions. The event is included in the conversation context and can trigger a reply. |
| **No react (known)** | The event is still sent to the AI as part of the conversation context, so the AI is *aware* it happened, but it does **not** trigger a reaction. Use this when you want the AI to have the information without prompting it to speak every time. |
| **Hidden from the LLM** | The event is **not** sent to the AI at all. The LLM never sees it. Use this only when the information would cause **unwanted or spammy commentary**. |

### When to use “Hidden from the LLM”

Prefer **React** or **No react (known)** whenever possible. Reserve **Hidden** for cases where the event creates noise or unwanted commentary, for example:

- **Fuel scoop events** (e.g. FuelScoop, FuelScoopStarted, FuelScoopEnded) - repetitive “scooping” updates that don’t add value.
- **System / starsystem chat at community goals** - high-volume or generic system messages that clutter the conversation.
- **Spammy NPC chatter** (e.g. via ReceiveText from NPCs) - if the AI keeps reacting to every NPC line, hiding that channel can reduce noise.

If you hide too many events, the AI loses useful context (e.g. where you are, what you’re doing) and may give less relevant answers. Use **No react (known)** when you want to keep context but stop the AI from commenting on that event type.

## Configuring reactions

Reactions are configured in the **Reactions** tab of the settings UI, per character. You can:

- Set each event to **React**, **No react (known)**, or **Hidden from the LLM**.
- Use the category toggles to set all events in a category at once.
- Search events by name or category.
- **Reset to Defaults** to restore built-in defaults.
- **Import from other character** to copy another character’s reaction settings.

Enable or disable the whole feature with the **Enable Event Reactions** toggle at the top.

## How it works

When an event occurs in the game, the integration can add it to the conversation context and optionally trigger a reply. Only events set to **React** are treated as “important” and can prompt the AI to respond. Events set to **No react (known)** still appear in context so the AI can refer to them if relevant. Events set to **Hidden** are never sent to the AI.

## Events with special configuration

Some events have extra options that appear in the UI when you expand them. These control *when* or *what* the AI reacts to for that event.

### ProspectedAsteroid

- **React to material** - Multi-select list of materials (e.g. Alexandrite, Low Temperature Diamond, Painite, Platinum, Tritium). The AI will only react when a prospected asteroid contains one of the selected materials. If the list is empty, behaviour depends on implementation (often “react to all” or “react to none”).

### InDanger

- **React while mining** - Turn reactions to danger off while mining asteroids. (Prevents proximity warnings near asteroids.)
- **React while on-foot** - Turn reactions to danger off while on foot in settlements or stations. (Prevents high-altitude warnings when jumping and alerts doing illegal things.)
- **React while in supercruise** - Turn reactions to danger off while in supercruise and having an active jump route. (Prevents proximity warnings when scooping dangerously close to stars.)

### ReceiveText

- **React to local text** - React to messages in local chat.
- **React to starsystem text** - React to messages in system (star system) chat.
- **React to squadron text** - React to messages in squadron chat.
- **React to NPC text** - React to messages from NPCs (can be noisy; consider disabling or hiding if the AI comments too much).

### Idle

- **Idle Timeout (seconds)** - Number of seconds of inactivity before the AI considers you idle and may comment (minimum 60). Default is 300.

## Tips

- If the AI talks too much, set some event types to **No react (known)** or disable specific reactions (e.g. NPC text, fuel scoop) rather than hiding everything.
- Use **Hidden** only for events that produce unwanted commentary (fuel scoop, system chat at CGs, spammy NPC chatter).
- For a quieter experience, set non-critical events to **No react (known)** and keep **React** for safety-related ones (e.g. UnderAttack, LowFuelWarning, InDanger).
- You can change settings at any time; no restart is required.
