#!/usr/bin/env python3
"""Five ways to make a hazard span unmistakable without sounding like a robot.

The first design bracketed every hazard span with <400> markers. Ten pauses in
one sentence is not emphasis, it is stuttering, and it was rejected on listening.
Per-span synthesis was worse: audible seams.

The idea here is that the safety does not come from silence. It comes from
spelling the number out and writing the unit in full, which removes the pairs
that actually get confused (0.5 uL against 0.5 mL, 15 against 50). Prosody is
then a separate question, and the natural tool for it is sentence structure,
because a model trained on speech already knows how to say a short sentence.

    conda run -n ML python scripts/gate_naturalness.py
"""

from __future__ import annotations

import asyncio
import base64
import io
import json
import os
import sys
import wave
from pathlib import Path
from urllib.parse import urlencode

import websockets
from dotenv import load_dotenv

WS_HOST = "wss://users-ws.rime.ai"
OUT = Path("runs/gates/naturalness")
SR = 22050

# The same step every time. Numbers spelled and units written out in all of them,
# because that is the part carrying the safety; only the shape changes.
VARIANTS: dict[str, tuple[str, bool, str]] = {
    "v1_plain": (
        "Add zero point five microlitres of ten millimolar d N T P mix to tube three. "
        "Incubate at ninety eight degrees for thirty seconds.",
        False,
        "One sentence, no markup at all. The baseline for natural.",
    ),
    "v2_one_pause": (
        "Add <300> zero point five microlitres of ten millimolar d N T P mix to tube three. "
        "Incubate at ninety eight degrees for thirty seconds.",
        True,
        "A single pause before the one value that would be catastrophic, nowhere else.",
    ),
    "v3_short_sentences": (
        "Add zero point five microlitres. Ten millimolar d N T P mix. Into tube three. "
        "Then incubate at ninety eight degrees for thirty seconds.",
        False,
        "Each value gets its own sentence, so the pause and the stress are the model's own.",
    ),
    "v4_value_last": (
        "Into tube three, add ten millimolar d N T P mix. The volume is zero point five microlitres. "
        "Incubate at ninety eight degrees for thirty seconds.",
        False,
        "Restructured so the critical volume lands at the end of its clause, where stress falls naturally.",
    ),
    "v5_confirming": (
        "Add zero point five microlitres of ten millimolar d N T P mix to tube three. "
        "That is zero point five, into tube three. "
        "Incubate at ninety eight degrees for thirty seconds.",
        False,
        "Says the two most dangerous values a second time, the way a person actually would.",
    ),
}


def wav_bytes(pcm: bytes) -> bytes:
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(pcm)
    return buf.getvalue()


async def synth(key: str, speaker: str, text: str, *, pauses: bool):
    params = {
        "speaker": speaker,
        "modelId": "mistv3",
        "lang": "eng",
        "audioFormat": "pcm",
        "samplingRate": SR,
        "segment": "never",
    }
    if pauses:
        params["pauseBetweenBrackets"] = "true"
    pcm = bytearray()
    words: list[str] = []
    ends: list[float] = []
    async with websockets.connect(
        f"{WS_HOST}/ws3?{urlencode(params)}",
        additional_headers={"Authorization": f"Bearer {key}"},
    ) as ws:
        await ws.send(json.dumps({"text": text, "contextId": "n"}))
        await ws.send(json.dumps({"operation": "flush", "contextId": "n"}))
        while True:
            ev = json.loads(await asyncio.wait_for(ws.recv(), timeout=40))
            if ev.get("type") == "chunk":
                pcm += base64.b64decode(ev["data"])
            elif ev.get("type") == "timestamps":
                wt = ev.get("word_timestamps") or {}
                words += wt.get("words", [])
                ends += wt.get("end", [])
            elif ev.get("type") == "done":
                break
            elif ev.get("type") == "error":
                raise RuntimeError(ev.get("message"))
    return bytes(pcm), words, ends


async def main() -> int:
    load_dotenv()
    key = os.environ.get("RIME_API_KEY")
    if not key:
        print("RIME_API_KEY is not set", file=sys.stderr)
        return 2
    speaker = os.environ.get("RIME_SPEAKER") or "alexis"
    OUT.mkdir(parents=True, exist_ok=True)

    lines = [
        "# Making a hazard span unmistakable without sounding like a robot",
        "",
        "Every variant spells the number out and writes the unit in full. That is what "
        "removes the confusable pairs. Only the shape of the sentence changes.",
        "",
        "| variant | audio | timestamp overrun | idea |",
        "|---|---|---|---|",
    ]
    for label, (text, pauses, note) in VARIANTS.items():
        pcm, _words, ends = await synth(key, speaker, text, pauses=pauses)
        (OUT / f"{label}.wav").write_bytes(wav_bytes(pcm))
        (OUT / f"{label}.txt").write_text(text)
        audio_s = len(pcm) / (SR * 2)
        overrun = (ends[-1] - audio_s) if ends else 0.0
        print(f"  {label:20s} {audio_s:5.2f}s  overrun {overrun:+.2f}s")
        lines.append(f"| `{label}` | {audio_s:.2f} s | {overrun:+.2f} s | {note} |")

    lines += [
        "",
        "Timestamp overrun is how far Rime's last reported word end sits past the actual "
        "end of the audio. Small is good: it means played state can trust the clock.",
        "",
    ]
    (OUT / "VERDICT.md").write_text("\n".join(lines))
    print()
    print("\n".join(lines))
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
