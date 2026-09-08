#!/usr/bin/env python3
"""Speak both arms of the claim, so the difference can be judged by ear.

The gate scripts spoke hand-written strings. This one goes through the real
loader, so what comes out of the speaker is what the product would say. Two
files per step: the protocol as written, and the prepared spoken form the
assistant actually reads. Same speaker, same model, same step, so a listening
comparison varies only the preparation.

    conda run -n ML python scripts/render_preview.py
    conda run -n ML python scripts/render_preview.py --protocol handwritten --step 0
"""

from __future__ import annotations

import argparse
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

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from wetlab import protocol as protocol_mod  # noqa: E402
from wetlab import render  # noqa: E402

WS_HOST = "wss://users-ws.rime.ai"
OUT = Path("runs/gates/render_preview")
SR = 22050


def wav_bytes(pcm: bytes) -> bytes:
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(pcm)
    return buf.getvalue()


async def synth(key: str, speaker: str, text: str) -> bytes:
    """One utterance over /ws3, with the flags the product uses (PS section 8)."""
    params = {
        "speaker": speaker,
        "modelId": "mistv3",
        "lang": "eng",
        "audioFormat": "pcm",
        "samplingRate": SR,
        "segment": "never",
        "pauseBetweenBrackets": "true",
        "phonemizeBetweenBrackets": "true",
    }
    pcm = bytearray()
    async with websockets.connect(
        f"{WS_HOST}/ws3?{urlencode(params)}",
        additional_headers={"Authorization": f"Bearer {key}"},
    ) as ws:
        await ws.send(json.dumps({"text": text, "contextId": "p"}))
        await ws.send(json.dumps({"operation": "flush", "contextId": "p"}))
        while True:
            ev = json.loads(await asyncio.wait_for(ws.recv(), timeout=40))
            kind = ev.get("type")
            if kind == "chunk":
                pcm += base64.b64decode(ev["data"])
            elif kind == "done":
                break
            elif kind == "error":
                raise RuntimeError(ev.get("message"))
    return bytes(pcm)


async def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--protocol", default="handwritten")
    ap.add_argument("--step", type=int, default=0)
    ap.add_argument("--corpus", type=Path, default=Path("data/corpus"))
    args = ap.parse_args()

    load_dotenv()
    key = os.environ.get("RIME_API_KEY")
    if not key:
        print("RIME_API_KEY is not set", file=sys.stderr)
        return 2
    speaker = os.environ.get("RIME_SPEAKER") or "alexis"

    proto = protocol_mod.load(args.corpus, args.protocol)
    step = proto.steps[args.step]
    OUT.mkdir(parents=True, exist_ok=True)

    # `raw` is the protocol as its citation says it reads. `prepared` is what
    # the assistant says: the committed spoken form if the offline pass has
    # been run, and the detector's rendering if it has not.
    arms = {"raw": step.text, "prepared": proto.speech_for(step)}

    for mode, text in arms.items():
        print(f"{mode:9s} {text}")
        pcm = await synth(key, speaker, text)
        stem = OUT / f"{proto.id}_{step.id}_{mode}"
        stem.with_suffix(".wav").write_bytes(wav_bytes(pcm))
        stem.with_suffix(".txt").write_text(text + "\n")
        print(f"          {len(pcm) / (SR * 2):.2f} s -> {stem.with_suffix('.wav')}")

    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
