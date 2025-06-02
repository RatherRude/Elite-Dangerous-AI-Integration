# Frequently Asked Questions

## Does this cost money?

No, but we recommend OpenAI, which costs money based on usage. Typical usage costs are **around $0.10 per hour**, depending on your playstyle. Alternatives are [available](./advanced/freeSetup.md), but will need some additional setup and may not work as well.

## Do I need a microphone?

Yes, you will need a working microphone to interact with the AI and preferably a headset to prevent the AI from hearing itself.

## My antivirus software is flagging the application as a virus. What should I do?

Some antivirus software may flag the application as a virus due to **a false positive**. This can be very annoying and you may need to add an exception in your antivirus software or disable it, if you encounter this issue. All our source code is publicly available and our build process is available (and can be replicated) in the repository.
Please also report this to your antivirus software vendor as a false-positive, to hopefully get this resolved in the future.
After you have added an exception, you may need to re-download and re-extract the application, as the antivirus software might have quarantined or deleted important files.

## How do I keep my configuration settings and conversations when upgrading the application?

All configuration settings and conversations are stored in the `resources` folder. To keep your configuration settings, you can copy the `config.json` file from the old folder to the new folder. To keep your previous conversations, you can do the same with the `covas.db` file.

## Do you support other languages than English?

Generally yes, but there are a few places that are currently english-only. The AI can understand and speak multiple languages, but due to some additionally process for numbers they might not be read correctly. Additionally, the AI tends to fall back to english sometimes, due to most of the game-events being in english. This can usually be fixed by reminding the AI of the language you want to use.

## I paid money for the OpenAI API, but the AI is still not working. What should I do?

OpenAI sometimes needs a few minutes to process your payment. If you are still having issues after a few minutes, please check your OpenAI account for any issues. If you are still having issues, please get in touch with us.

## Does it work on Linux, Steam Deck, Proton, Wine?

We have a native Linux version available, but it requires some special setup. Please contact us on discord and we will help you get it running.

## Can I use Deepseek or other reasoning models?

While technically possible, reasoning models have a response time of many seconds to minutes, which is not suitable for real-time interaction. The advantage of these models in coding and mathematics is not useful in the context of creative writing and storytelling and due to the long reasoning chains, these models are far more expensive than our recommended configuration.