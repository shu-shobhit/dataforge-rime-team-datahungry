#!/usr/bin/env python3
"""Are Rime's word timestamps accurate on /ws3, for text we would actually send?

The earlier verdict said they drift badly. Every clip in that test carried
markup, and the one plain case was off by 0.15 s while every large error
involved a <400> or [...] token. So the claim under test here is narrower:

    timestamps are accurate for plain text, and markup tokens corrupt them.

Method, so the answer does not rest on Rime describing its own output: slice the
audio at each reported word boundary and measure the energy inside each slice. A
window that is mostly silence means the boundary is in the wrong place. Every
slice is also written out so a person can listen and say what word they hear.

    conda run -n ML python scripts/gate_timestamps.py
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

import numpy as np
import websockets
from dotenv import load_dotenv

WS_HOST = "wss://users-ws.rime.ai"
OUT = Path("runs/gates/timestamps")
SR = 22050

CASES = {
    "plain": "Add zero point five microlitres of ten millimolar buffer to tube three.",
    "commas": "Add, zero point five microlitres, of ten millimolar buffer, to tube three.",
    "pauses": "Add <300> zero point five microlitres <300> of ten millimolar buffer to tube three.",
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
    url = f"{WS_HOST}/ws3?{urlencode(params)}"
    pcm = bytearray()
    words: list[str] = []
    starts: list[float] = []
    ends: list[float] = []
    async with websockets.connect(url, additional_headers={"Authorization": f"Bearer {key}"}) as ws:
        await ws.send(json.dumps({"text": text, "contextId": "t"}))
        await ws.send(json.dumps({"operation": "flush", "contextId": "t"}))
        while True:
            ev = json.loads(await asyncio.wait_for(ws.recv(), timeout=30))
            kind = ev.get("type")
            if kind == "chunk":
                pcm += base64.b64decode(ev["data"])
            elif kind == "timestamps":
                wt = ev.get("word_timestamps") or {}
                words += wt.get("words", [])
                starts += wt.get("start", [])
                ends += wt.get("end", [])
            elif kind == "done":
                break
            elif kind == "error":
                raise RuntimeError(ev.get("message"))
    return bytes(pcm), words, starts, ends


def env_of(a: np.ndarray, win_s: float = 0.01) -> tuple[np.ndarray, float]:
    n = int(win_s * SR)
    frames = len(a) // n
    return np.array([np.sqrt((a[i * n : (i + 1) * n] ** 2).mean()) for i in range(frames)]), win_s


def analyse(label: str, pcm: bytes, words, starts, ends) -> list[str]:
    a = np.frombuffer(pcm, dtype="<i2").astype(float)
    audio_s = len(a) / SR
    env, win = env_of(a)
    peak = env.max() if env.size else 0.0
    voiced = np.where(env > peak * 0.05)[0]
    speech_end = (voiced[-1] + 1) * win if voiced.size else 0.0

    (OUT / label).mkdir(parents=True, exist_ok=True)
    (OUT / label / "full.wav").write_bytes(wav_bytes(pcm))

    lines = [
        f"### `{label}`",
        "",
        f"audio {audio_s:.2f} s, speech ends {speech_end:.2f} s, "
        f"last timestamp {ends[-1] if ends else 0:.2f} s",
        "",
        "| word | start | end | energy in slice | verdict |",
        "|---|---|---|---|---|",
    ]
    misaligned = 0
    for i, (w, s, e) in enumerate(zip(words, starts, ends)):
        i0, i1 = int(s * SR), min(int(e * SR), len(a))
        seg = a[i0:i1] if i1 > i0 else np.array([])
        r = float(np.sqrt((seg**2).mean())) if seg.size else 0.0
        # A slice past the end of the audio, or one that is nearly silent while
        # the clip is not, means the reported boundary is in the wrong place.
        if i0 >= len(a):
            verdict, bad = "PAST END OF AUDIO", True
        elif peak and r < peak * 0.05:
            verdict, bad = "silent", True
        else:
            verdict, bad = "ok", False
        misaligned += bad
        if seg.size:
            (OUT / label / f"{i:02d}_{''.join(c for c in w if c.isalnum()) or 'tok'}.wav").write_bytes(
                wav_bytes(seg.astype("<i2").tobytes())
            )
        lines.append(f"| `{w}` | {s:.2f} | {e:.2f} | {r:7.0f} | {verdict} |")
    lines += ["", f"**{len(words) - misaligned} of {len(words)} slices contain speech.**", ""]
    return lines


async def main() -> int:
    load_dotenv()
    key = os.environ.get("RIME_API_KEY")
    if not key:
        print("RIME_API_KEY is not set", file=sys.stderr)
        return 2
    speaker = os.environ.get("RIME_SPEAKER") or "alexis"
    OUT.mkdir(parents=True, exist_ok=True)

    report = [
        "# Are the word timestamps accurate on /ws3?",
        "",
        "Each reported word boundary is used to slice the audio. A slice that is "
        "silent, or that starts past the end of the audio, means the boundary is wrong. "
        "Slices are saved so the words can be checked by ear.",
        "",
    ]
    for label, text in CASES.items():
        pcm, words, starts, ends = await synth(
            key, speaker, text, pauses=(label == "pauses")
        )
        print(f"  {label}: {len(pcm)/(SR*2):.2f}s audio, {len(words)} words")
        report += analyse(label, pcm, words, starts, ends)

    (OUT / "VERDICT.md").write_text("\n".join(report))
    print("\n".join(report))
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
