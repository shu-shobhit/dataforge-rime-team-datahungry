#!/usr/bin/env python3
"""Gate 3, properly: is inlineSpeedAlpha honoured anywhere we can use it?

The first attempt only tried /ws3 and read the verdict off Rime's own word
timestamps, which reported the parameter as applied when the audio was
unchanged. This version:

  * measures speech duration from the waveform, never from the timestamps;
  * tries the HTTP endpoint as well, because Rime documents inlineSpeedAlpha as
    a body parameter and the websocket may simply not carry it;
  * tries both directions of the value, since below 1.0 is faster on this
    parameter and above 1.0 is slower;
  * tries Mist v2 as a control, because if v2 responds and v3 does not, the
    limit is the model rather than the transport;
  * saves every clip so a person can listen and say what they hear.

    conda run -n ML python scripts/gate3_inline_speed.py
"""

from __future__ import annotations

import asyncio
import io
import json
import os
import sys
import wave
from pathlib import Path
from urllib.parse import urlencode

import aiohttp
import numpy as np
import websockets
from dotenv import load_dotenv

HTTP_URL = "https://users.rime.ai/v1/rime-tts"
WS_HOST = "wss://users-ws.rime.ai"
CATALOG = "https://users.rime.ai/data/voices/all-v2.json"
OUT = Path("runs/gates/gate3")
SR = 22050

PLAIN = "Add zero point five microlitres of buffer."
MARKED = "Add [zero] [point] [five] microlitres of buffer."


def speech_seconds(wav_bytes: bytes) -> tuple[float, float]:
    """(total, speech-only) seconds, silence trimmed at 5 percent of peak.

    Mist v1 and v2 answer with a JSON envelope rather than audio even when the
    Accept header asks for WAV, so a non-RIFF body is a shape difference and not
    a failure to synthesize.
    """
    if wav_bytes[:4] != b"RIFF":
        raise ValueError(
            f"not a WAV: body starts {wav_bytes[:16]!r} "
            "(Mist v1 and v2 return a JSON envelope, not audio)"
        )
    with wave.open(io.BytesIO(wav_bytes)) as w:
        sr = w.getframerate()
        a = np.frombuffer(w.readframes(w.getnframes()), dtype="<i2").astype(float)
    if a.size == 0:
        return 0.0, 0.0
    n = int(0.02 * sr)
    env = np.array([np.sqrt((a[i * n : (i + 1) * n] ** 2).mean()) for i in range(len(a) // n)])
    if env.size == 0 or env.max() == 0:
        return len(a) / sr, 0.0
    voiced = np.where(env > env.max() * 0.05)[0]
    speech = (voiced[-1] - voiced[0] + 1) * 0.02 if voiced.size else 0.0
    return len(a) / sr, speech


def pcm_to_wav(pcm: bytes, sr: int = SR) -> bytes:
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes(pcm)
    return buf.getvalue()


async def pick_speakers(session: aiohttp.ClientSession) -> dict[str, str]:
    """One valid English speaker per model, from the live catalog."""
    async with session.get(CATALOG) as r:
        cat = await r.json(content_type=None)
    out: dict[str, str] = {}
    for model in ("mistv3", "mistv2"):
        node = cat.get(model) or {}
        for lang in ("eng", "en"):
            names = node.get(lang)
            if names:
                out[model] = names[0]
                break
    return out


async def http_case(session, key, label, *, model, speaker, text, alpha):
    body = {
        "text": text,
        "speaker": speaker,
        "modelId": model,
        "lang": "eng",
        "samplingRate": SR,
    }
    if alpha is not None:
        body["inlineSpeedAlpha"] = alpha
    async with session.post(
        HTTP_URL,
        json=body,
        headers={"Authorization": f"Bearer {key}", "Accept": "audio/wav"},
    ) as r:
        if r.status != 200:
            return label, None, f"HTTP {r.status}: {(await r.text())[:120]}"
        return label, await r.read(), None


async def ws_case(key, label, *, model, speaker, text, alpha_conn=None, alpha_msg=None):
    params = {
        "speaker": speaker,
        "modelId": model,
        "lang": "eng",
        "audioFormat": "pcm",
        "samplingRate": SR,
        "segment": "never",
    }
    if alpha_conn is not None:
        params["inlineSpeedAlpha"] = alpha_conn
    url = f"{WS_HOST}/ws3?{urlencode(params)}"
    pcm = bytearray()
    try:
        async with websockets.connect(
            url, additional_headers={"Authorization": f"Bearer {key}"}
        ) as ws:
            msg = {"text": text, "contextId": label}
            if alpha_msg is not None:
                msg["inlineSpeedAlpha"] = alpha_msg
            await ws.send(json.dumps(msg))
            await ws.send(json.dumps({"operation": "flush", "contextId": label}))
            while True:
                ev = json.loads(await asyncio.wait_for(ws.recv(), timeout=30))
                if ev.get("type") == "chunk":
                    import base64

                    pcm += base64.b64decode(ev["data"])
                elif ev.get("type") == "done":
                    break
                elif ev.get("type") == "error":
                    return label, None, ev.get("message")
    except Exception as exc:  # noqa: BLE001
        return label, None, f"{type(exc).__name__}: {exc}"
    return label, pcm_to_wav(bytes(pcm)), None


async def main() -> int:
    load_dotenv()
    key = os.environ.get("RIME_API_KEY")
    if not key:
        print("RIME_API_KEY is not set", file=sys.stderr)
        return 2
    OUT.mkdir(parents=True, exist_ok=True)

    async with aiohttp.ClientSession() as session:
        speakers = await pick_speakers(session)
        v3 = os.environ.get("RIME_SPEAKER") or speakers.get("mistv3", "cove")
        v2 = speakers.get("mistv2")
        print(f"speakers: mistv3={v3}  mistv2={v2}\n")

        cases = []
        # HTTP, Mist v3: the form Rime documents.
        cases.append(await http_case(session, key, "http_v3_plain", model="mistv3", speaker=v3, text=PLAIN, alpha=None))
        cases.append(await http_case(session, key, "http_v3_marked_noalpha", model="mistv3", speaker=v3, text=MARKED, alpha=None))
        cases.append(await http_case(session, key, "http_v3_slow_3", model="mistv3", speaker=v3, text=MARKED, alpha="3.0,3.0,3.0"))
        cases.append(await http_case(session, key, "http_v3_fast_0.3", model="mistv3", speaker=v3, text=MARKED, alpha="0.3,0.3,0.3"))
        cases.append(await http_case(session, key, "http_v3_slow_nospace", model="mistv3", speaker=v3, text=MARKED, alpha="3.0, 3.0, 3.0"))
        # HTTP, Mist v2: the control. If v2 moves and v3 does not, the limit is the model.
        if v2:
            cases.append(await http_case(session, key, "http_v2_plain", model="mistv2", speaker=v2, text=PLAIN, alpha=None))
            cases.append(await http_case(session, key, "http_v2_slow_3", model="mistv2", speaker=v2, text=MARKED, alpha="3.0,3.0,3.0"))
        # WebSocket, both placements, for completeness.
        cases.append(await ws_case(key, "ws_v3_plain", model="mistv3", speaker=v3, text=PLAIN))
        cases.append(await ws_case(key, "ws_v3_slow_msg", model="mistv3", speaker=v3, text=MARKED, alpha_msg="3.0,3.0,3.0"))
        cases.append(await ws_case(key, "ws_v3_slow_conn", model="mistv3", speaker=v3, text=MARKED, alpha_conn="3.0,3.0,3.0"))

    rows = []
    for label, wav, err in cases:
        if err or not wav:
            rows.append((label, None, None, err or "no audio"))
            print(f"  {label:26s} ERROR {err}")
            continue
        (OUT / f"{label}.wav").write_bytes(wav)
        try:
            total, speech = speech_seconds(wav)
        except ValueError as exc:
            rows.append((label, None, None, str(exc)))
            print(f"  {label:26s} SKIPPED {exc}")
            continue
        rows.append((label, total, speech, None))
        print(f"  {label:26s} total {total:5.2f}s   speech {speech:5.2f}s")

    def speech_of(name: str) -> float | None:
        for label, _t, s, err in rows:
            if label == name and not err:
                return s
        return None

    lines = ["# Gate 3: inlineSpeedAlpha, measured from the waveform", "",
             f"Speakers: mistv3 `{v3}`, mistv2 `{v2}`. Text: `{MARKED}`", "",
             "| case | total | speech |", "|---|---|---|"]
    for label, t, s, err in rows:
        lines.append(f"| `{label}` | {'error' if err else f'{t:.2f} s'} | {'-' if err else f'{s:.2f} s'} |")
    lines.append("")

    base3 = speech_of("http_v3_marked_noalpha") or speech_of("http_v3_plain")
    slow3 = speech_of("http_v3_slow_3")
    fast3 = speech_of("http_v3_fast_0.3")
    base2, slow2 = speech_of("http_v2_plain"), speech_of("http_v2_slow_3")

    def verdict(base, changed, name):
        if base is None or changed is None:
            return f"- {name}: inconclusive, a case errored"
        ratio = changed / base
        moved = abs(ratio - 1.0) > 0.15
        return f"- {name}: {base:.2f} s to {changed:.2f} s, ratio {ratio:.2f}. {'HONOURED' if moved else 'IGNORED'}"

    lines += ["## Verdicts", ""]
    lines.append(verdict(base3, slow3, "HTTP Mist v3, alpha 3.0 (slower)"))
    lines.append(verdict(base3, fast3, "HTTP Mist v3, alpha 0.3 (faster)"))
    if base2 and slow2:
        lines.append(verdict(base2, slow2, "HTTP Mist v2, alpha 3.0 (slower, control)"))
    lines.append(verdict(speech_of("ws_v3_plain"), speech_of("ws_v3_slow_msg"), "WebSocket Mist v3, per message"))
    lines.append(verdict(speech_of("ws_v3_plain"), speech_of("ws_v3_slow_conn"), "WebSocket Mist v3, connection flag"))
    lines += ["", f"Clips are in `{OUT}` for a listening check.", ""]

    (OUT / "VERDICT.md").write_text("\n".join(lines))
    print()
    print("\n".join(lines))
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
