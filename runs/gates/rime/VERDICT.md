# Rime control gates, measured from the audio

Speaker `cove`, model `mistv3`, lang `eng`, `/ws3`, 22050 Hz PCM.
Every verdict below comes from the waveform. Rime's word timestamps are
reported alongside as a claim, because for two of these cases the claim is wrong.

## Measured

| case | audio | speech (silence trimmed) | speech ends | timestamps claim |
|---|---|---|---|---|
| `base` | 2.73 s | 2.32 s | 2.44 s | 2.29 s |
| `paused` | 3.53 s | 3.14 s | 3.26 s | 4.06 s |
| `phoneme_plain` | 1.77 s | 1.30 s | 1.42 s | 1.06 s |
| `phoneme_marked` | 1.65 s | 1.36 s | 1.48 s | 2.47 s |
| `speed_plain` | 2.83 s | 2.44 s | 2.56 s | 2.29 s |
| `speed_permsg` | 2.77 s | 2.38 s | 2.50 s | 4.06 s |
| `speed_connflag` | 2.73 s | 2.36 s | 2.48 s | 4.06 s |

## Gate 2a: custom pauses. PASS

Two `<400>` markers added +0.80 s of audio against the same sentence without them, which is the 0.8 s asked for. The pauses are real.

## Gate 2b: inline phonemes on English Mist v3. PASS

`dNTP` plain speaks for 1.30 s, `{d1Enti0pi}` for 1.36 s. The audio differs, so the flag is honoured on English Mist v3, settling the contradiction between Rime's own pages in favour of the four that say it works. Whether the pronunciation is *correct* is a listening question, not this one.

## Gate 3: inlineSpeedAlpha. FAIL

Speech duration is 2.44 s plain, 2.38 s with the value sent per message, 2.36 s with it on the connection query string. All three are the same audio.

Rime's timestamps for both marked cases claim 4.06 s against 2.29 s plain, so the parameter was accepted and reported as applied while the synthesis ignored it. A verdict taken from the timestamps would have read PASS.

Consequence: mechanism 6.1 loses per-word slowing. H1 and H5 keep the custom pauses and the digit-by-digit spelling, which are measured and do work. `render.py` must never emit `[ ]`, because the brackets survive into the spoken text and the timestamps.

## The word timestamps are not a reliable clock

This was not one of the gates and it matters more than the ones that were.

A `<400>` marker comes back as its own word in the timestamps event, and it is given roughly 0.88 s rather than the 0.40 s of silence it actually inserts. The error accumulates across the utterance, so the last word of the paused clip is claimed to end at 4.06 s when the audio stops at 3.53 s and the speech stops at 3.26 s.

| word | start | end | duration |
|---|---|---|---|
| `Add` | 0.00 | 0.18 | 0.18 |
| `<400>` | 0.18 | 1.06 | 0.88 |
| `zero` | 1.06 | 1.23 | 0.18 |
| `point` | 1.23 | 1.41 | 0.18 |
| `five` | 1.41 | 1.59 | 0.18 |
| `microlitres` | 1.59 | 1.94 | 0.35 |
| `<400>` | 1.94 | 2.82 | 0.88 |
| `of` | 2.82 | 3.00 | 0.18 |
| `buffer.` | 3.00 | 4.06 | 1.06 |

Every reported duration is an integer multiple of 0.1764 s, which is a frame quantum rather than an acoustic alignment. Even with no markup at all the last word is claimed to end 0.15 s before the speech actually does.

Mechanism 6.2 maps hazard spans to audio positions through these numbers, and the error runs in the unsafe direction: a span whose timestamp ends earlier than its audio is counted as played before it has been. This needs a decision before `played.py` is written.
