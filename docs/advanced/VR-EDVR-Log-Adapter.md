# EDVR Log Adapter

`electron/vr-edvr-log-adapter.js` follows EDVR's private origin without changing
electron-vr or SteamVR's tracking origin.

## Detection

Requires one running Elite process with loaded EDVR module evidence, a readable
executable path and a start time. Selects its PID-matched log under `edvr_logs`.
The log must confirm `SteamVR/OpenXR` and natural reference space `STAGE`.

## Updates

Successful `seat_reset` records contain position in metres and yaw in degrees.
`position_recentre` uses radians and is parsed separately. Existing records
establish the current origin only; old recenter sequences are not replayed.

The controller renders `E * inverse(B) * W`: current EDVR origin E, captured
SteamVR seated basis B, and configured pose W. This uses the same seat-local
placement as stock Elite, including after offset edits.

The reader polls every 250 ms and buffers partial lines. Process detection is
cached for up to five seconds. Reads are capped at 256 KiB; attachment scans
backwards at most 8 MiB for the last origin. If absent, the next fresh event's
`from` pose establishes it. Failed, malformed, wrong-PID, out-of-order and stale
records are ignored. Log rotation/truncation rebaselines without replaying history.
Loss of the process/log clears compensation; an unsupported frame disables that
session. Destroying the overlay stops the reader.

## Precision

Log flushing can delay updates. Logged seat resets round positions to millimetres
and yaw to tenths of degrees. Unlogged camera adjustments are not tracked; a
documented EDVR origin API would be preferable to parsing logs.

## Verification

Parser, session filtering, buffering, retry and transform tests pass. The packaged
hidden-overlay check verified the live EDVR log connection. Visible cockpit
checks passed for recentering, offset edits, centering and 90-degree turns.
