#!/usr/bin/env python3
"""Gates 2 and 3: do Rime's text controls actually do anything on English Mist v3?

Rime fails silently. Nearly every mistake returns 200 and playable audio while
doing something other than what was asked, so "it sounded fine" is not evidence.
This script measures the controls from the word timestamps instead of judging
them by ear.

    Gate 2  custom pauses and inline phonemes, sent as connection query flags
            exactly as the LiveKit plugin sends them.
    Gate 3  inlineSpeedAlpha as a PER-MESSAGE field. The plugin sends no
            synthesis parameters per message at all, so nothing in it says
            whether Rime accepts one. Mechanism 6.1 wants per-word slowing on
            hazard numbers, and this is the only way to find out.

Writes WAVs, the raw timestamps events, and a verdict to runs/gates/rime/.

    conda run -n ML python scripts/gate_rime_controls.py
"""

from __future__ import annotations

import asyncio
import base64
import json
import os
import struct
import sys
import wave
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urlencode

import websockets
from dotenv import load_dotenv

WS_HOST = "wss://users-ws.rime.ai"
OUT = Path("runs/gates/rime")
SAMPLE_RATE = 22050

BASE = "Add zero point five microlitres of buffer."
PAUSED = "Add <400> zero point five microlitres <400> of buffer."
SPEED_PLAIN = "Add zero point five microlitres of buffer."
SPEED_MARKED = "Add [zero] [point] [five] microlitres of buffer."
PHONEME_PLAIN = "Add the dNTP mix."
PHONEME_MARKED = "Add the {d1Enti0pi} mix."


@dataclass
class Result:
    label: str
    text: str
    extra: dict
    pcm: bytearray = field(default_factory=bytearray)
    words: list[str] = field(default_factory=list)
    starts: list[float] = field(default_factory=list)
    ends: list[float] = field(default_factory=list)
    error: str | None = None

    @property
    def duration(self) -> float:
        return len(self.pcm) / (SAMPLE_RATE * 2)

    def word_duration(self, word: str) -> float | None:
        for w, s, e in zip(self.words, self.starts, self.ends):
            if w.strip().lower() == word:
                return e - s
        return None

    def gap_before(self, word: str) -> float | None:
        for i, w in enumerate(self.words):
            if w.strip().lower() == word and i > 0:
                return self.starts[i] - self.ends[i - 1]
        return None


def url(speaker: str, **flags) -> str:
    params = {
        "speaker": speaker,
        "modelId": "mistv3",
        "lang": "eng",
        "audioFormat": "pcm",
        "samplingRate": SAMPLE_RATE,
        "segment": "never",
        **{k: ("true" if v is True else "false" if v is False else v) for k, v in flags.items()},
    }
    return f"{WS_HOST}/ws3?{urlencode(params)}"


async def synth(api_key: str, speaker: str, label: str, text: str, *, flags: dict, extra: dict) -> Result:
    """One utterance on its own connection, so connection flags never leak between cases."""
    res = Result(label=label, text=text, extra=extra)
    try:
        async with websockets.connect(
            url(speaker, **flags), additional_headers={"Authorization": f"Bearer {api_key}"}
        ) as ws:
            await ws.send(json.dumps({"text": text, "contextId": label, **extra}))
            await ws.send(json.dumps({"operation": "flush", "contextId": label}))
            while True:
                raw = await asyncio.wait_for(ws.recv(), timeout=30)
                ev = json.loads(raw)
                kind = ev.get("type")
                if kind == "chunk":
                    res.pcm += base64.b64decode(ev["data"])
                elif kind == "timestamps":
                    wt = ev.get("word_timestamps") or {}
                    res.words += wt.get("words", [])
                    res.starts += wt.get("start", [])
                    res.ends += wt.get("end", [])
                elif kind == "done":
                    break
                elif kind == "error":
                    res.error = ev.get("message", "(no message)")
                    break
    except Exception as exc:  # noqa: BLE001 - the verdict records whatever went wrong
        res.error = f"{type(exc).__name__}: {exc}"
    return res


def save_wav(path: Path, pcm: bytes) -> None:
    with wave.open(str(path), "wb") as f:
        f.setnchannels(1)
        f.setsampwidth(2)
        f.setframerate(SAMPLE_RATE)
        f.writeframes(pcm)


def rms(pcm: bytes) -> float:
    if not pcm:
        return 0.0
    n = len(pcm) // 2
    vals = struct.unpack(f"<{n}h", pcm[: n * 2])
    return (sum(v * v for v in vals) / n) ** 0.5


async def main() -> int:
    load_dotenv()
    api_key = os.environ.get("RIME_API_KEY")
    if not api_key:
        print("RIME_API_KEY is not set", file=sys.stderr)
        return 2
    speaker = os.environ.get("RIME_SPEAKER") or "cove"
    OUT.mkdir(parents=True, exist_ok=True)

    cases = [
        ("base", BASE, {}, {}),
        ("paused", PAUSED, {"pauseBetweenBrackets": True}, {}),
        ("phoneme_plain", PHONEME_PLAIN, {"phonemizeBetweenBrackets": True}, {}),
        ("phoneme_marked", PHONEME_MARKED, {"phonemizeBetweenBrackets": True}, {}),
        ("speed_plain", SPEED_PLAIN, {}, {}),
        ("speed_permsg", SPEED_MARKED, {}, {"inlineSpeedAlpha": "2.0, 2.0, 2.0"}),
        ("speed_connflag", SPEED_MARKED, {"inlineSpeedAlpha": "2.0, 2.0, 2.0"}, {}),
    ]

    results: dict[str, Result] = {}
    for label, text, flags, extra in cases:
        print(f"  synthesising {label} ...", flush=True)
        r = await synth(api_key, speaker, label, text, flags=flags, extra=extra)
        results[label] = r
        if r.error:
            print(f"    error: {r.error}")
            continue
        save_wav(OUT / f"{label}.wav", bytes(r.pcm))
        (OUT / f"{label}.timestamps.json").write_text(
            json.dumps({"words": r.words, "start": r.starts, "end": r.ends}, indent=2)
        )
        print(f"    {r.duration:.2f}s audio, {len(r.words)} words, rms {rms(bytes(r.pcm)):.0f}")

    lines: list[str] = ["# Rime control gates", "", f"speaker `{speaker}`, model `mistv3`, lang `eng`", ""]

    # Gate 2a: do custom pauses lengthen the silence before a bracketed span?
    base, paused = results["base"], results["paused"]
    verdict2a = "INCONCLUSIVE"
    if not base.error and not paused.error:
        delta = paused.duration - base.duration
        gap_base = base.gap_before("zero") or 0.0
        gap_paused = paused.gap_before("zero") or 0.0
        verdict2a = "PASS" if delta > 0.5 else "FAIL"
        lines += [
            "## Gate 2a: custom pauses",
            "",
            f"- audio without `<400>`: {base.duration:.2f} s",
            f"- audio with two `<400>`: {paused.duration:.2f} s (delta {delta:+.2f} s, expected about +0.8)",
            f"- gap before \"zero\": {gap_base:.3f} s to {gap_paused:.3f} s",
            f"- **{verdict2a}**",
            "",
        ]

    # Gate 2b: does an inline phoneme string change the audio at all?
    pp, pm = results["phoneme_plain"], results["phoneme_marked"]
    verdict2b = "INCONCLUSIVE"
    if not pp.error and not pm.error:
        same_len = abs(pp.duration - pm.duration) < 0.02
        identical = bytes(pp.pcm) == bytes(pm.pcm)
        verdict2b = "FAIL (ignored)" if identical else "PASS"
        lines += [
            "## Gate 2b: inline phonemes on English Mist v3",
            "",
            f"- plain \"dNTP\": {pp.duration:.2f} s, words {pp.words}",
            f"- with `{{d1Enti0pi}}`: {pm.duration:.2f} s, words {pm.words}",
            f"- audio identical: {identical}; durations within 20 ms: {same_len}",
            f"- **{verdict2b}** (differing audio means the flag was honoured, not that the pronunciation is right; listen to confirm)",
            "",
        ]

    # Gate 3: is inlineSpeedAlpha honoured per message, or only per connection?
    sp, permsg, connflag = results["speed_plain"], results["speed_permsg"], results["speed_connflag"]
    verdict3 = "INCONCLUSIVE"
    if not sp.error:
        rows = []
        for name, r in (("plain", sp), ("per-message", permsg), ("connection flag", connflag)):
            if r.error:
                rows.append(f"- {name}: error {r.error}")
                continue
            d = r.word_duration("zero")
            rows.append(
                f"- {name}: total {r.duration:.2f} s, \"zero\" {d:.3f} s" if d else f"- {name}: total {r.duration:.2f} s, \"zero\" not found"
            )
        base_d = sp.word_duration("zero")
        msg_d = permsg.word_duration("zero") if not permsg.error else None
        conn_d = connflag.word_duration("zero") if not connflag.error else None
        if base_d and msg_d:
            verdict3 = "PASS" if msg_d > base_d * 1.25 else "FAIL"
        lines += ["## Gate 3: per-message inlineSpeedAlpha", "", *rows, ""]
        if base_d and conn_d:
            lines.append(
                f"- connection-flag form {'does' if conn_d > base_d * 1.25 else 'does not'} slow the word, "
                f"which is the fallback if the per-message form fails"
            )
        lines += [
            f"- **{verdict3}**",
            "",
            "If FAIL, H1 and H5 keep pauses and digit-by-digit spelling and `render.py` never emits `[ ]`.",
            "",
        ]

    (OUT / "VERDICT.md").write_text("\n".join(lines))
    print("\n".join(lines))
    print(f"written to {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
