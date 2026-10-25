# First Steps

Start with the [Getting Started](./index.md) guide if you have not set up COVAS:NEXT yet. Once you are ready, start the AI Assistant, launch Elite Dangerous, and try talking to your assistant in-game.

You can ask questions about the game, request help with your ship, or simply have a conversation. The settings below let you make the experience your own.

## Give your assistant a personality

In the **Character** settings, describe how you would like your assistant to speak and behave. For example, mention a cat aboard your ship if you would like your assistant to bring it up in conversation. Find more ideas on our [Discord server](https://discord.gg/9c58jxVuAT).

## Talk to your assistant

Use your chosen push-to-talk button or voice activation to speak. If you use voice activation, headphones help prevent the assistant from hearing its own replies.

## Choose when it speaks and what it can do

In **Reactions**, choose which in-game events your assistant should comment on. Turn off reactions you would rather not hear. See the [Reactions guide](./25_reactions.md) for more options.

In **Actions**, review the things your assistant can do in-game. The app will point out anything that needs a control assigned. You can turn off actions you do not want to use. See the [Actions guide](./20_actions.md) for details.

## Personalize the appearance

You can give your assistant an avatar and choose what appears in the overlay. Explore the appearance settings to find a look that suits you.

## Explore more features

Browse [Plugins](./plugins/index.md) if you want to add more voices or other capabilities later. You can start using COVAS:NEXT without configuring plugins.

## Windows keyboard layouts

Localized key names from Elite Dangerous, such as `Key_è`, `Key_ç`, `Key_à`, and `Key_Underline`, are supported, as are named symbols such as `Key_Ampersand`, `Key_Circumflex`, `Key_Dollar`, `Key_ExclamationPoint`, and `Key_SuperscriptTwo`. On Windows, these keys are resolved using the `KeyboardLayout` declared in the game's `.binds` file. This covers the French AZERTY number row and symbols, including shifted symbols such as `¨`, `£`, `µ`, `%`, `§`, `/`, `+`, and `°`. Explicit modifiers are preserved: for example, `Key_è` with `Key_LeftShift` presses the French AZERTY `è/7` key with Shift; there is no need to change the binding to `Key_7`. Dead keys such as `^` and `¨` are sent as physical key presses rather than composed text.

Characters requiring AltGr, such as `@`, `#`, `{`, `}`, `|`, `\`, and `€`, are also resolved on Windows. Windows reports implicit AltGr as Ctrl+Alt. If the binding already specifies `Key_RightAlt`, that modifier is preserved without adding a second Ctrl+Alt combination.

For a full list of actions and their required keyboard buttons, see the [Actions](./20_actions.md) page.

## Stay up to date

The app will let you know when a new version is available. Download the update for your platform and install it as you normally would; your settings and conversations will carry over.
