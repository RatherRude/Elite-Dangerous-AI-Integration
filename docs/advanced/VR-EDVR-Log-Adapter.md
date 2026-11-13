# EDVR Logfile Adapter (Prototype)

This Windows-only COVAS adapter compensates for EDVR's private recenter while
leaving electron-vr generic. It is included in the experimental standalone, not
installed into the user's working COVAS copy. It needs a visible cockpit test.

## Activation

`electron/vr-game-probe.js` must identify exactly one running Elite process,
with loaded EDVR module metadata, a readable executable path, and a start time.
The adapter looks only in that executable's `edvr_logs` directory, for a log
whose filename PID matches and whose creation time matches the current session.
It also requires the session's header to confirm `SteamVR/OpenXR` and natural
reference space `STAGE`. LOCAL, another runtime, ambiguous games, process access
failures, and unverified installed-but-not-loaded mods do not activate it.

This is automatic in the prototype; no extra user setting is added. It affects
only Seated Anchor. Head/world modes retain their requested placements.

## Transform

Successful `seat_reset` records contain `from=x/y/z/yaw` and `to=x/y/z/yaw` in
metres/degrees. `position_recentre` uses radians for yaw and is parsed separately.
Failed or malformed records are ignored. No process memory is inspected.

On attachment, existing log content establishes initial origin E0 only. No old
reset sequence is replayed. The current configured world pose W is retained.
Each fresh origin E produces world pose `E * inverse(E0) * W`; this moves and
rotates the whole overlay around the correct origin. It is not a direct addition
of translations, and it does not sum rounded log deltas over time.

While EDVR compensation is active, the controller sends generic world placement
to avoid applying SteamVR's seat origin a second time. Offset/angle edits update W
without replacing E0; leaving/reentering seated mode establishes a fresh baseline.
Curvature and size keep using their existing native setters.

The adapter reads appended bytes every 250 ms, buffering partial lines. Only the
current PID's successful entries at/after attachment, at most ten seconds old and
not more than two seconds in the future, are accepted. Out-of-order timestamps
are ignored. A session/file change or truncation rebaselines, never replays. An
unsupported frame switch disables that log until a new session is verified.
Append reads are bounded to 256 KiB; a larger backlog is dropped and rebaselined.
Attachment scans backwards at most 8 MiB for a baseline buried under performance
records. If none is found, the next fresh event's `from` pose establishes it. Loss
of the verified process/log clears compensation and restores native-seat handling.
Process identification is cached for up to five seconds. Destroying the overlay
stops the timer; it does not survive window recreation.

## Files and Checks

- `electron/vr-edvr-log-adapter.js`: session selection, format checks, bounded tailer.
- `electron/vr-seat-controller.js`: application-origin matrix conversion and lifecycle.
- `electron/index.js`: starts the adapter and logs activation/failure status.
- `test/electron/vr-edvr-log-adapter.test.js`: old/partial/failed records, PID/frame/runtime gating, truncation, shutdown and native retry.
- `test/electron/vr-seat-controller.test.js`: full transform, position edits and native fallback.

The process/log reader was checked read-only against the running EDVR session.
All 55 Electron tests pass. The packaged hidden-overlay check verified native
placement, offsets, curvature and the live EDVR logfile baseline. These checks
and visible recenter
behavior must be distinguished: a hidden overlay cannot prove cockpit alignment.

## Limits

Log flushing introduces latency; the poll interval is not a latency guarantee.
The log rounds positions to millimetres and seat-reset yaw to tenths of degrees.
Unlogged look compensation, eye alignment, private camera changes, and changes to
the natural STAGE frame are not comprehensively tracked. Format changes may stop
the adapter or make this model incomplete. This is not a general EDVR pose API.
A supported EDVR origin feed remains the better long-term transport.

Test one recenter, another in the opposite direction, several repeats, an offset
edit then recenter, curvature, head/world switching, COVAS restart and game restart.
Keep the previous standalone backup until these pass. No EDVR files, runtime
origins, working install, or global OpenXR-layer registration are changed here.
