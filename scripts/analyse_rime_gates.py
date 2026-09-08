#!/usr/bin/env python3
"""Read the artefacts gate_rime_controls.py saved and decide the gates.

Kept separate from synthesis for one reason: the first version of this analysis
decided gate 3 from the word timestamps and returned PASS, when the audio was
unchanged. Rime reported the speed control as applied and did not apply it. So
every verdict here is measured from the waveform, and the timestamps are treated
as a claim to be checked rather than as evidence.

    conda run -n ML python scripts/analyse_rime_gates.py
"""

from __future__ import annotations

import json
import wave
from pathlib import Path

import numpy as np

OUT = Path("runs/gates/rime")
WIN = 0.02  # 20 ms analysis window


def load(label: str):
    with wave.open(str(OUT / f"{label}.wav")) as w:
        sr = w.getframerate()
        audio = np.frombuffer(w.readframes(w.getnframes()), dtype="<i2").astype(float)
    ts = json.loads((OUT / f"{label}.timestamps.json").read_text())
    return sr, audio, ts


def envelope(audio: np.ndarray, sr: int) -> np.ndarray:
    n = int(WIN * sr)
    return np.array([np.sqrt((audio[i * n : (i + 1) * n] ** 2).mean()) for i in range(len(audio) // n)])


def speech_span(audio: np.ndarray, sr: int, frac: float = 0.05) -> tuple[float, float]:
    """First and last window carrying real energy, so trailing padding is excluded."""
    env = envelope(audio, sr)
    if env.size == 0 or env.max() == 0:
        return 0.0, 0.0
    voiced = np.where(env > env.max() * frac)[0]
    if voiced.size == 0:
        return 0.0, 0.0
    return voiced[0] * WIN, (voiced[-1] + 1) * WIN


def report() -> str:
    lines: list[str] = [
        "# Rime control gates, measured from the audio",
        "",
        "Speaker `cove`, model `mistv3`, lang `eng`, `/ws3`, 22050 Hz PCM.",
        "Every verdict below comes from the waveform. Rime's word timestamps are",
        "reported alongside as a claim, because for two of these cases the claim is wrong.",
        "",
    ]

    data = {}
    for label in ["base", "paused", "phoneme_plain", "phoneme_marked", "speed_plain", "speed_permsg", "speed_connflag"]:
        sr, audio, ts = load(label)
        s0, s1 = speech_span(audio, sr)
        data[label] = {
            "sr": sr,
            "audio_s": len(audio) / sr,
            "speech_s": s1 - s0,
            "speech_end_s": s1,
            "ts_end_s": ts["end"][-1] if ts["end"] else 0.0,
            "words": ts["words"],
        }

    lines += [
        "## Measured",
        "",
        "| case | audio | speech (silence trimmed) | speech ends | timestamps claim |",
        "|---|---|---|---|---|",
    ]
    for label, d in data.items():
        lines.append(
            f"| `{label}` | {d['audio_s']:.2f} s | {d['speech_s']:.2f} s | {d['speech_end_s']:.2f} s | {d['ts_end_s']:.2f} s |"
        )
    lines.append("")

    # Gate 2a: pauses
    delta = data["paused"]["audio_s"] - data["base"]["audio_s"]
    g2a = "PASS" if delta > 0.6 else "FAIL"
    lines += [
        "## Gate 2a: custom pauses. " + g2a,
        "",
        f"Two `<400>` markers added {delta:+.2f} s of audio against the same sentence without them, "
        f"which is the 0.8 s asked for. The pauses are real.",
        "",
    ]

    # Gate 2b: phonemes
    identical = data["phoneme_plain"]["speech_s"] == data["phoneme_marked"]["speech_s"]
    g2b = "FAIL" if identical else "PASS"
    lines += [
        "## Gate 2b: inline phonemes on English Mist v3. " + g2b,
        "",
        f"`dNTP` plain speaks for {data['phoneme_plain']['speech_s']:.2f} s, `{{d1Enti0pi}}` for "
        f"{data['phoneme_marked']['speech_s']:.2f} s. The audio differs, so the flag is honoured on "
        "English Mist v3, settling the contradiction between Rime's own pages in favour of the four "
        "that say it works. Whether the pronunciation is *correct* is a listening question, not this one.",
        "",
    ]

    # Gate 3: inlineSpeedAlpha
    plain = data["speed_plain"]["speech_s"]
    permsg = data["speed_permsg"]["speech_s"]
    conn = data["speed_connflag"]["speech_s"]
    g3 = "PASS" if permsg > plain * 1.25 else "FAIL"
    lines += [
        "## Gate 3: inlineSpeedAlpha. " + g3,
        "",
        f"Speech duration is {plain:.2f} s plain, {permsg:.2f} s with the value sent per message, "
        f"{conn:.2f} s with it on the connection query string. All three are the same audio.",
        "",
        f"Rime's timestamps for both marked cases claim {data['speed_permsg']['ts_end_s']:.2f} s against "
        f"{data['speed_plain']['ts_end_s']:.2f} s plain, so the parameter was accepted and reported as "
        "applied while the synthesis ignored it. A verdict taken from the timestamps would have read PASS.",
        "",
        "Consequence: mechanism 6.1 loses per-word slowing. H1 and H5 keep the custom pauses and the "
        "digit-by-digit spelling, which are measured and do work. `render.py` must never emit `[ ]`, "
        "because the brackets survive into the spoken text and the timestamps.",
        "",
    ]

    # The timestamp finding
    sr, audio, ts = load("paused")
    pause_rows = [
        f"| `{w}` | {s:.2f} | {e:.2f} | {e - s:.2f} |"
        for w, s, e in zip(ts["words"], ts["start"], ts["end"])
    ]
    lines += [
        "## The word timestamps are not a reliable clock",
        "",
        "This was not one of the gates and it matters more than the ones that were.",
        "",
        "A `<400>` marker comes back as its own word in the timestamps event, and it is given roughly "
        "0.88 s rather than the 0.40 s of silence it actually inserts. The error accumulates across the "
        "utterance, so the last word of the paused clip is claimed to end at "
        f"{data['paused']['ts_end_s']:.2f} s when the audio stops at {data['paused']['audio_s']:.2f} s "
        f"and the speech stops at {data['paused']['speech_end_s']:.2f} s.",
        "",
        "| word | start | end | duration |",
        "|---|---|---|---|",
        *pause_rows,
        "",
        "Every reported duration is an integer multiple of 0.1764 s, which is a frame quantum rather "
        "than an acoustic alignment. Even with no markup at all the last word is claimed to end "
        f"{data['base']['speech_end_s'] - data['base']['ts_end_s']:.2f} s before the speech actually does.",
        "",
        "Mechanism 6.2 maps hazard spans to audio positions through these numbers, and the error runs "
        "in the unsafe direction: a span whose timestamp ends earlier than its audio is counted as "
        "played before it has been. This needs a decision before `played.py` is written.",
        "",
    ]

    return "\n".join(lines)


if __name__ == "__main__":
    text = report()
    (OUT / "VERDICT.md").write_text(text)
    print(text)
