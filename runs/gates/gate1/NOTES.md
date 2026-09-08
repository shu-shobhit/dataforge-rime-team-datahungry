# Gate 1: the worker joins a room and the browser hears `say()`

Run on 6 Sep 2026 against `livekit-server --dev` 1.13.6, `livekit-agents` 1.8.0,
Rime `mistv3` over `/ws3`.

Four processes: the media server, the agent worker, the `aiohttp` token and web
server on 8080, and a browser tab.

## Result: pass

`events.jsonl` in this directory is the run, verbatim.

| what | evidence |
|---|---|
| worker registered | `worker.log` |
| audio reached the listener's output | `jitterBufferEmittedCount` = 515 520 samples at 48 kHz = 10.74 s emitted, `concealedSamples` = 0 |
| the rendered text was the real one | `speech.start` carries the text `render.py` produced, not a hand-written string |
| a completed utterance is played | `speech.finished` `interrupted: false`, `played: true` |
| a cut utterance is not played | `speech.finished` `interrupted: true`, `played: false` |
| the pedal reaches the agent | `input.pedal` with the page's own `at_ms` |

## The cut, timed

The pedal was pressed 3 005.7 ms into an utterance whose audio is 9.55 s long.

```
 2166.9  speech.start      u1  s1
 5172.6  input.pedal       advance
 5186.9  speech.finished   u1  interrupted: true   played: false
 5193.6  step.committed    s1
 5199.1  speech.start      u2  s2
 9331.8  speech.finished   u2  interrupted: false  played: true
```

Cut latency, agent side: **14.3 ms** from the pedal arriving to the utterance
being reported finished. This is not the number that matters for safety. What
left the speaker is later than what the agent thinks it sent, by the network hop
and the listener's buffers, and only the browser probe measures that. Task 10
adds it and gate 4 reports the difference. This number is the floor.

Version 0 has no gating, so the advance committed `s1` even though it was
unplayed. That is the state machine's job in Task 12; this gate is about whether
the mechanism underneath it reports the truth, and it does.

## Two bugs this gate found, both of which would have surfaced during the demo

**A room only dispatches an agent job when it is created.** Joining a room a
previous session left behind connects normally and then sits in silence, with
nothing in any log to explain it. That is exactly the state after a worker
restart or a page reload. `web/room.js` now mints a fresh room name on every
join.

**A missing microphone stopped the page joining at all.** `setMicrophoneEnabled`
throws when there is no capture device, and the exception took the whole connect
down. Without a microphone the scientist cannot speak or read back, but the
assistant should still read steps and the pedal should still work. The failure is
now caught, reported on screen, and sent to the agent in `page.ready`.
