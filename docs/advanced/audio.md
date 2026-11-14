# Audio devices

COVAS:NEXT uses SoundCard 0.4.6 on every platform: WASAPI shared mode on Windows,
CoreAudio on macOS, and PulseAudio on Linux. PipeWire is supported through its
PulseAudio compatibility server (`pipewire-pulse`). There is no direct ALSA or
PortAudio audio path and no need to install PortAudio development headers.

## Selecting devices

Choose input and output independently in Settings. Each entry displays the device
name and its exact ID; the saved configuration fields `input_device_name` and
`output_device_name` now contain IDs, despite their historical names. Duplicate
display names do not identify the same device. Playback opens the selected sink
directly without changing the system's default output.

`System default` saves `default` and resolves the current default whenever a new
recording or playback stream opens. Empty/absent selections and the old `pulse`
alias also intentionally follow the system default. An explicit missing ID is an
error, never a reason to choose another device. Disconnecting/recreating a device
can require selecting it again. Old saved human-readable device names must also
be reselected after upgrading; names and substrings are not matched automatically.

Windows saves WASAPI endpoint IDs and Linux saves PulseAudio source/sink names.
macOS SoundCard IDs are transient CoreAudio object numbers, so COVAS instead saves
the persistent CoreAudio device UID with a `coreaudio:` prefix. This small metadata
adapter uses SoundCard's private CoreAudio property helper; the pinned dependency
and UID test must be reviewed when upgrading SoundCard. No custom audio I/O
backend is used.

## Setup and packaging

- **Windows:** no additional audio library installation is required. Use shared
  mode so the audio engine handles conversion. Capture requests at least two
  channels (or all device channels for larger devices), then averages to mono.
  This avoids SoundCard's documented broken single-channel WASAPI recording path,
  including on mono endpoints by requesting shared-mode remixing. Drivers that
  reject that format produce a visible error instead of silently recording
  garbage or switching microphones. Such devices still need hardware testing.
- **macOS:** grant microphone access to the application/terminal running COVAS.
  SoundCard documents silent recording when microphone permission is missing.
  No Homebrew PortAudio package is needed.
- **Linux:** install the runtime `libpulse` client library (`libpulse0` on Debian/
  Ubuntu), and run PulseAudio or PipeWire with `pipewire-pulse` in the user session.
  A bare ALSA-only system is not supported. The Flatpak already grants the
  PulseAudio socket; it also works with PipeWire's compatible socket.
- **Frozen applications:** `Chat.spec` explicitly collects SoundCard package data,
  including its platform CFFI `.py.h` declarations. SoundCard supplies a PyInstaller
  data hook as well. WASAPI/CoreAudio are system libraries; Linux uses libpulse
  from the runtime. There is no Python dependency lockfile in this repository;
  the existing npm lockfiles do not describe Python packages.

The application still sends/receives mono signed little-endian PCM16: 24 kHz for
TTS and decoded auxiliary audio files, 16 kHz for STT. The adapter converts to/from
SoundCard's normalized float32 NumPy arrays; capture averages channels before
clipping/quantizing. SoundCard/OS backends perform sample-rate conversion, rather
than opening ALSA hardware at those speech rates. Existing plugin TTS generators
continue to return PCM bytes through the same playback path.

## Streaming, completion, and interruption limits

Playback submits at most 20 ms of audio at a time and paces submissions, so a large
provider chunk is not queued to the backend all at once. Capture requests VAD-sized
blocks (normally 32 ms at 16 kHz). Each playback line/file opens its own stream on
first audio and closes it on completion, failure, or interruption. Line completion
callbacks run after the completion padding/close, not immediately after the last
speech bytes are submitted.

SoundCard has **no portable public cancel/drain API**. Its Linux context exit
drains queued playback before disconnecting; its Windows exit stops/releases the
client, and macOS closes the AudioUnit without a portable drain. Normal completion
therefore submits 100 ms of silence and allows a further 100 ms settling time
before closing, so short clips can leave the backend rather than being immediately
truncated. This is a conservative completion allowance, **not a measured hardware
drain guarantee** for every device. It adds about 200 ms per line/file.

Abort skips remaining chunks and completion padding, and cleanup stays on the
stream-owning worker. It does not manipulate a native stream from the UI thread.
Already-buffered audio may remain audible, particularly on Linux where context
exit drains. SoundCard documents that WASAPI can ignore `blocksize` and underrun;
hardware/server buffering can exceed the requested 20 ms. A blocked native
play/record/open/close call cannot be forcibly interrupted safely through
SoundCard's public API. Shutdown waits up to two seconds for the TTS worker, logs
if a backend/provider is still blocked, and leaves that daemon to clean up when
the call returns. These are real limitations, not immediate-cancellation promises.

## Validation

Hardware-free tests cover exact routing, duplicate names, defaults, missing
devices, CoreAudio UID metadata, multichannel/downmixed capture, PCM conversion,
small final clips, bounded writes, interruption, and cleanup. Before shipping on
each OS, verify real microphone permission, mono/stereo/multichannel endpoints,
non-default output routing with the system default unchanged, short clips, long
speech interruption, unplug/replug, and application shutdown. In particular, test
Linux resampling with a 48 kHz sink/source and PipeWire, plus mono Windows input.

Upstream references: [SoundCard documentation](https://soundcard.readthedocs.io/),
[known issues and channel maps](https://github.com/bastibe/SoundCard/blob/0.4.6/README.rst),
and the pinned lifecycle implementations for
[WASAPI](https://github.com/bastibe/SoundCard/blob/0.4.6/soundcard/mediafoundation.py),
[CoreAudio](https://github.com/bastibe/SoundCard/blob/0.4.6/soundcard/coreaudio.py), and
[PulseAudio](https://github.com/bastibe/SoundCard/blob/0.4.6/soundcard/pulseaudio.py).
