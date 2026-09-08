# Gate 4: the agent's idea of playback against the listener's

Run on 6 Sep 2026, ten sessions on one laptop over loopback. Each session
connects to a fresh room, hears one step, and is cut part way through, at 0.8 s
through 8.0 s in 0.8 s increments. `deltas.csv` is the data.

**delta = agent-side `playback_position` minus listener-side `rendered_s`.**

## Result

| | |
|---|---|
| clean cuts | 10 |
| delta, median | **-0.080 s** |
| delta, range | -0.208 s to +0.030 s |
| listener report age at the cut, median, ten clean cuts | 5.5 ms (max 181.6 ms) |
| listener report age at the cut, median, all 18 cuts with a report | 66.9 ms (max 193.4 ms) |
| jitter buffer depth during playback, median | 0.036 s (0.020 to 0.135 s, 151 probe reports in `cuts.jsonl`) |
| cuts with no listener report | 2 of 20, both second cuts inside the first poll interval |

## This corrects the architecture doc

Section 7.4 said the agent-side position "overstates what left the speaker by the
network hop and the listener's buffers". Measured, it does the opposite: the
listener has heard **more** than the agent believes, by a median of 80 ms.

The bias in the measurement runs the same way, which makes the finding stronger
rather than weaker. The probe reports every 200 ms, so `rendered_s` is up to a
poll interval stale and therefore reads low. The delta is negative anyway, so the
true gap is at least this large.

The doc has been corrected. Nothing else changes: played state does not consult
either number (architecture 7.4), so this is a measurement of a quantity the
safety argument deliberately does not depend on.

It is worth saying which direction is which, because it is not obvious. An agent
that **understates** what played would, under a span-level design, mark spans
unplayed that the scientist had in fact heard, and re-read them needlessly. That
is the harmless direction. Overstating is the dangerous one, and it is not what
happens here.

## Why only ten of the twenty cuts are usable

`jitterBufferEmittedCount` is one monotonic sample total for the whole track. It
cannot say which utterance a sample belonged to. An utterance that begins while
the previous one is still draining therefore takes that drainage into its own
baseline, and its `rendered_s` is inflated by it.

Every cut in this gate is flagged `after_cut` or not, and only the ones that
started from silence are averaged. The first attempt at this gate cut the same
utterance ten times in a row, and every reading after the first was contaminated;
the deltas plateaued near -0.21 s and looked like a real effect. They were an
artefact of the measurement. Redone as ten separate sessions.

The first attempt is also where the buffer-depth hypothesis died: the jitter
buffer held about 20 ms there, and a median of 36 ms in the kept run, not the
200 ms the plateau would have needed.

## Incidental: the fence catches real audio

`stale_dropped` reached 26, 4 and 66 on three consecutive cuts in the first
attempt, where utterances were cut and restarted quickly. Those are events Rime
sent for a context that had already been cut, which the plugin would have pushed
at whatever was speaking next. That is gate 5's claim appearing on its own,
without the test flag that gate 5 uses to force it. The first attempt's log was
not kept, so these three counts rest on this note alone. In the kept run
`stale_dropped` is 0 on all 20 cuts.

## Corrections, 7 Sep 2026

The results table was re-derived from `deltas.csv` and `cuts.jsonl`. The report
age median had been computed over all 18 cuts with a report, contaminated ones
included, while the table said ten clean cuts; both populations are now shown.
The jitter buffer depth had been quoted from the discarded first attempt; the
kept run's figure replaces it. The cut counts read 12 and 18 where the file has
20.
