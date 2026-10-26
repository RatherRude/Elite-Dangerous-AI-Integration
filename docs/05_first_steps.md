
# First Steps

If you have not already done so, you should first complete the [Getting Started](./index.md) guide. This guide will help you set up your AI and get you started with the basics.

Once you have completed the setup, you can start using the AI in-game. The AI can help you with a variety of tasks, such as navigating the galaxy map, managing your ship's systems, and providing information about the game world. The AI can also assist you in combat, mining, trading, and other activities.

There are several configuration options, that you can adjust to customize the AI to your liking.

## Character Prompt

The AI Character Prompt is a description of the AI's personality. You can modify this text to your liking – if you want the AI to talk about your ships cat, you can mention "We have a cat on our ship that likes to get in the way of my controls when it wants attention.", causing the AI to role-play and mention the cats current whereabouts regularly. More examples can be found on our discord server.

## Audio

The integration uses your microphone for speech recognition. We support voice activation and push-to-talk (PTT). When using voice activation, we recommend using headphones to avoid the AI hearing itself, which causes a feedback loop.

## Event Triggers

Changes in the game world can trigger events that the AI can respond to. For example, when the ship is in danger, the AI can be programmed to inform you. These reactions are configured in the UI in the **Reactions** tab of the settings, where you can choose to silence some events or have the AI respond to others, making the AI more or less chatty.

For a more in-depth guide on reactions and event triggers, see the [Reactions](./25_reactions.md) page.

## Keyboard Bindings

Certain keyboard bindings are required for the AI to trigger game actions. In the **Actions** tab of the settings, the UI will inform you if actions are unassigned, conflicting, or unsupported. Actions can be toggled on and off to disable unwanted ones, such as ejecting all cargo.

Localized key names from Elite Dangerous, such as `Key_è`, `Key_ç`, `Key_à`, and `Key_Underline`, are supported, as are named symbols such as `Key_Ampersand`, `Key_Circumflex`, `Key_Dollar`, `Key_ExclamationPoint`, and `Key_SuperscriptTwo`. On Windows, these keys are resolved using the `KeyboardLayout` declared in the game's `.binds` file. This covers the French AZERTY number row and symbols, including shifted symbols such as `¨`, `£`, `µ`, `%`, `§`, `/`, `+`, and `°`. Explicit modifiers are preserved: for example, `Key_è` with `Key_LeftShift` presses the French AZERTY `è/7` key with Shift; there is no need to change the binding to `Key_7`. Dead keys such as `^` and `¨` are sent as physical key presses rather than composed text.

Only the modifiers explicitly recorded in the `.binds` entry are sent, in their saved order. Left and right Shift, Control, and Alt remain distinct; `Key_RightAlt` is never replaced with Ctrl+Alt. Windows is used to find the physical key's scan code, not to generate a text-entry combination.

If Windows reports that a key name requires Shift, Control, or Alt to produce its character, the **Actions** settings show a keyboard mapping warning. The physical key remains available with only its explicit game modifiers. This can indicate an unexpected key name or a layout mismatch. When reporting it, include the action, key name, game layout, and modifier details shown in the warning. Keys that cannot resolve at all appear separately as unsupported bindings.

For a full list of actions and their required keyboard buttons, see the [Actions](./20_actions.md) page.

## Avatars

Avatars allow you to give the AI a face. You provide a 2×2 grid with equal sections; each section shows the same styled character in one of four attitudes:

| <img src="../ui/src/assets/cn_avatar_default.png" alt="Default avatar grid" width="120" /> | **Top-left:** the character is listening<br>**Top-right:** the character is speaking<br>**Bottom-left:** the character is thinking<br>**Bottom-right:** the character is performing searches or actions |
|----------------------------------------------------------------|------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|

## Plugins

Explore [Plugins](./plugins/index.md) to enhance your experience: fast, on-device speech-to-text (STT), text-to-speech (TTS), and embedding.

## Upgrading the AI

You will automatically receive a notification when a new version of the AI is available during the launch of the application. After downloading the new version, run the MSI installer. The one-click installer updates your existing installation; your configuration and conversations are migrated automatically.
