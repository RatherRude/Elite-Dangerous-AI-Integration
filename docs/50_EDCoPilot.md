# EDCoPilot Integration

We are excited to work with Razzafrag on integrating **COVAS:NEXT** with **EDCoPilot**.

The EDCoPilot integration lets both applications coordinate speech output, show COVAS:NEXT dialogue in EDCoPilot, optionally read or react to EDCoPilot commentary through COVAS:NEXT, and optionally let COVAS:NEXT control EDCoPilot's UI.

## Availability

COVAS:NEXT only shows the EDCoPilot plugin settings when EDCoPilot is installed. The integration is disabled by default. To enable it, open **Plugin Settings -> EDCoPilot** and turn on **Enable EDCoPilot Integration**.

## Privacy and Shared Context

By default, EDCoPilot does not add gameplay knowledge to COVAS:NEXT. The integration primarily exchanges conversation and speech coordination messages.

If **EDCP UI Awareness** is enabled, COVAS:NEXT receives a summary of the currently visible EDCoPilot panel contents and may use that summary as context. This setting is enabled by default after the EDCoPilot integration itself is enabled.

## Show Dialogue in EDCoPilot

When the integration is enabled, COVAS:NEXT forwards commander messages and COVAS:NEXT replies to EDCoPilot. EDCoPilot can display this dialogue in its voice/activity UI.

## Choose How COVAS:NEXT Is Voiced

The integration supports two ways to voice COVAS:NEXT responses:

1. **Voice via COVAS:NEXT**
2. **Voice via EDCoPilot**

### 1. Voice via COVAS:NEXT

This is the normal mode. Choose any COVAS:NEXT TTS provider you like.

In this mode, COVAS:NEXT speaks its own responses directly, taking advantage of COVAS:NEXT's low-latency TTS and immersive TTS filters. This avoids routing COVAS:NEXT responses through EDCoPilot's speech queue.

### 2. Voice via EDCoPilot

Use this mode when you want EDCoPilot to handle COVAS:NEXT speech output.

To enable it, open **Advanced Settings -> TTS Settings** and select EDCoPilot as the TTS provider.

In this mode, COVAS:NEXT sends its response text to EDCoPilot. EDCoPilot then handles the actual voice output. Slower or delayed responses are expected because COVAS:NEXT speech is routed through EDCoPilot.

## Read EDCoPilot Commentary Through COVAS:NEXT

The **Read out EDCoPilot commentary** setting lets COVAS:NEXT voice EDCoPilot commentary through COVAS:NEXT's current TTS setup.

If EDCoPilot sends an interrupting phrase, COVAS:NEXT stops its current TTS before reading the EDCoPilot commentary. You can set **EDCoPilot Voice** to choose which COVAS:NEXT character voice should read EDCoPilot commentary.

## React to EDCoPilot Commentary

The **React to EDCoPilot commentary** setting lets EDCoPilot commentary become an event that COVAS:NEXT can react to.

This is disabled by default. Enable it only if you want COVAS:NEXT to generate responses based on EDCoPilot's spoken commentary.

## EDCoPilot UI Awareness

The **EDCP UI Awareness** setting lets COVAS:NEXT receive a compact summary of the currently visible EDCoPilot panels, including panel titles, status messages, and table summaries.

This can help COVAS:NEXT answer questions about what EDCoPilot is currently showing. Disable this setting if you do not want EDCoPilot panel summaries included in COVAS:NEXT context.

## Control EDCoPilot's UI via COVAS:NEXT

EDCoPilot UI actions are disabled by default. If you enable **Enable EDCoPilot UI Actions**, COVAS:NEXT can use tools to:

1. Open specific EDCoPilot panels.
2. Navigate the current EDCoPilot panel by scrolling, going back, or selecting an item.

We strongly recommend enabling only one set of UI actions at a time, either COVAS:NEXT's or EDCoPilot's.
