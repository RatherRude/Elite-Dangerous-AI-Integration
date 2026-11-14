# Running on Linux

!!! danger

        WARNING: This setup is highly experimental and is potentially difficult, please contact us on discord


We have a native Linux version available, but it requires some special setup. Starting with version 2.6.0, we provide a flatpak package for easier installation, but it is still experimental and may not work on all distributions. If you encounter any issues, please contact us on discord.

## Starting the application

1. Ensure you have [Flatpak](https://flatpak.org/setup/) installed on your system. You can check if Flatpak is installed by running:

    ```bash
    flatpak --version
    ```

   If it is not installed, follow the instructions on the Flatpak website to install it.

2. Download the flatpak file from out latest release at [GitHub](https://github.com/RatherRude/Elite-Dangerous-AI-Integration/releases) (or contact us on discord if it is not available).

3. Open a terminal and navigate to the directory where you downloaded the flatpak file.

4. Run the following command to install the flatpak package:

    ```bash
    flatpak install <path_to_flatpak_file>
    ```

5. Once the installation is complete, you can start the application by running:

    ```bash
    flatpak run com.covasnext.ui
    ```

6. The application should now start and you should see the main menu.
7. Open the advanced settings tab and scroll to the `Linux Settings` section at the bottom.
8. Configure the following settings:

    ```
        ED AppData Path: "/home/<username>/.steam/steam/steamapps/compatdata/359320/pfx/drive_c/users/steamuser/AppData/Local/Frontier Developments/Elite Dangerous/"
        ED Journal Path: "/home/<username>/.steam/steam/steamapps/compatdata/359320/pfx/drive_c/users/steamuser/Saved Games/Frontier Developments/Elite Dangerous"
    ```
    Depending on your system, the paths may be different. The above paths are for a steam + proton installation of the game.

9. In General Settings, select your input and output audio devices. `pulse` uses the server default; `pulse:<name>` selects a specific microphone/source or speaker/sink independently of the system default.
10. Follow the regular [Getting Started](../index.md) guide to configure the rest of the application.
11. Start the AI and it should now work 🤞 If you have any issues, please contact us on discord.

## Audio routing and dependencies

Linux enumeration, microphone capture, and speech/audio-file playback use the native
PulseAudio client library, including on PipeWire systems running `pipewire-pulse`.
The server converts 16 kHz mono signed-16-bit microphone audio and 24 kHz mono
signed-16-bit playback to/from the hardware's supported rates and channel layouts.
Windows and macOS continue to use PortAudio/PyAudio.

For source installations, install `libpulse.so.0` (Debian/Ubuntu: `libpulse0`;
Fedora: `pulseaudio-libs`; Arch: `libpulse`) and run PulseAudio or PipeWire with
its PulseAudio compatibility service in your user session. No `pactl`, `pacat`,
or Python PulseAudio package is required. Linux executable builds bundle libpulse
and its resolved dependencies; Flatpak also provides libpulse in its runtime and
grants access with `--socket=pulseaudio`. The audio server itself runs on the host.

Device entries use server symbolic names, not ALSA hardware names or numeric
indices. These names distinguish devices with identical descriptions and are
stored in the existing input/output device configuration fields. Existing `pulse`,
`default`, and empty selections use the server default at stream creation. An old
selection matching a server name or a unique server description is also accepted.
Other old ALSA selections must be reselected in Settings; missing or ambiguous
devices produce an error rather than silently recording/playing elsewhere.
Monitor sources are listed too, for users intentionally recording a sink's output.

Explicitly selected streams cannot be moved by server routing policy; unplugging
the device fails the stream instead of falling back to another device. This also
means external mixers cannot move an existing stream: change Settings and restart
the AI to select another device. No system default is changed. `pulse` resolves
the default when opening/reopening the stream, not continuously while playing.
If enumeration is empty, check that the audio server is running and reachable
from the app's session/sandbox and check the application log. There is no direct
ALSA fallback. Connection and stalled I/O timeouts are five seconds; a suspended
device can therefore report an audio error and require reconnection.

The backend binds the public [libpulse stream API](https://www.freedesktop.org/software/pulseaudio/doxygen/stream_8h.html)
and [device introspection API](https://www.freedesktop.org/software/pulseaudio/doxygen/introspect_8h.html).
It deliberately does not request `PA_STREAM_FIX_RATE` or `PA_STREAM_FIX_CHANNELS`:
the client PCM format stays fixed while the server resamples/remixes for hardware.

### Manual Linux verification

Mocked tests do not validate live audio routing. On both PulseAudio and
PipeWire/pipewire-pulse (including Flatpak), check:

- Select a non-default sink and a different explicit microphone; play speech and
  an audio file while recording. Verify routing in the server mixer and confirm
  system defaults and other applications are unchanged.
- Use 44.1/48 kHz stereo hardware and confirm 24 kHz playback and 16 kHz capture
  work without an invalid-sample-rate error.
- Test `pulse`, two same-description devices, monitor sources, an unavailable
  saved device, unplug/replug, server restart, repeated abort and app shutdown.
- Check that errors are visible, streams reconnect only to the selected device,
  and no contexts/streams remain after stopping the application.

## VR overlay

In **General Settings → Overlay**, select **VR Overlay** and turn on the content you want to see. Choose a voice provider if you want the avatar or chat to appear; with voice output set to **None**, both are hidden.

If COVAS:NEXT offers **Enable integration** or **Update integration**, select it and restart Elite Dangerous. Connect your headset, launch Elite in VR, and start the AI Assistant. Enabling integration by itself does not start the overlay.

If the overlay is still missing, use **Check again** in the VR overlay settings. **Waiting for a VR application** means COVAS:NEXT has not connected to Elite yet; **Connected to Elite Dangerous** means the VR connection is working, so check your overlay content settings.
