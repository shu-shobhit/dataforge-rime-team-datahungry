# Wet-lab protocol assistant

A voice assistant for lab protocols. It reads the steps out loud and answers
questions about them, so you can follow a protocol while your hands are busy.

You talk to it. There's no foot pedal and no list of commands to learn.

Built for the DataForge x Rime hackathon. Rime produces all spoken output.

## Why the protocol is prepared first

Protocols contain notation that is fine on a page and unreliable when passed
unchanged to a speech engine. For example:

`Add 25 µl of Q5 High-Fidelity 2X Master Mix to the reaction.`

The raw round-trip transcript was:

> Add twenty five **EL** of five **Guatemalan COTSOL's** high fidelity two
> **Master Mix** to the reaction.

That example is `neb_q5_m0492/s3` in
[`runs/roundtrip/roundtrip.json`](runs/roundtrip/roundtrip.json). The matching
audio is under [`runs/roundtrip/clips/quoted/`](runs/roundtrip/clips/quoted).

Across 31 steps, raw text recovered 93 of 107 scored values. Prepared text
recovered 105 of 107. The raw losses were units and reagent names. All 56
numeric tokens were recovered in both arms. See [RIME_EVIDENCE.md](RIME_EVIDENCE.md).

Preparation runs before a session. One model writes a spoken form for each
step, and another model checks that values did not change. The prepared files
are committed with the protocol.

## Run locally

Use Python 3.12 in the `ML` conda environment. Install once:

```bash
conda run -n ML pip install -e ".[dev]"
```

Copy `.env.example` to `.env` and add a Rime key, an OpenRouter key, and
LiveKit inference credentials. `.env` is ignored and must not be committed.
The media server is local. Recognition and turn detection use LiveKit's hosted
inference gateway, so the local development key pair is not sufficient.

Download the plugin files and local turn detector once:

```bash
conda run -n ML python -m livekit.agents download-files
```

Use `livekit.agents` for this command. `python -m wetlab.agent download-files`
only follows the plugins imported by this worker and does not download the
turn-detector weights.

Start the media server:

```bash
livekit-server --dev
```

Start the worker, page, and token server:

```bash
scripts/bench_up.sh
```

Open `http://127.0.0.1:8080`, choose a protocol, and select **Open protocol**.
Use `scripts/bench_up.sh status` to inspect the processes and
`scripts/bench_up.sh down` to stop them. Logs are written to `runs/logs/`.

A room names its protocol before LiveKit dispatches an agent job. Open a new
room to switch protocols. `PROTOCOL_ID` supplies the protocol for headless and
scripted runs that do not name one.

The page shows the source step and its spoken form, active timers, the two sides
of each conversation turn, the called tool, and the raw event stream.

## Prepare a protocol

Protocols must be ingested and prepared before they can be read. The worker
refuses an unprepared protocol. An earlier rule-based implementation converted
`20-30 mins` to “negative thirty”, so falling back to raw or partial preparation
is not allowed.

```bash
conda run -n ML python scripts/ingest_protocol.py <id> --variant "the 50 microlitre reaction column"
```

```bash
conda run -n ML python scripts/prepare_protocol.py <id>
```

Ingestion creates ordered steps from `source.md`. Preparation writes the spoken
form and retrieval terms, and rejects a step when the value checker finds a
change. Both outputs can be reviewed directly in the protocol directory.

## Measurements and tests

```bash
conda run -n ML python scripts/roundtrip.py --protocols neb_q5_m0492 addgene_transformation --out runs/roundtrip
WETLAB_SCRIPT=data/scenarios/questions.yaml conda run -n ML python -m wetlab.agent dev
conda run -n ML python scripts/metrics.py runs/<stamp>/events.jsonl
conda run -n ML pytest -q
```

There are 409 offline tests. Tests that require credentials are marked `live`
and skip when credentials are absent.

## Architecture

The local setup has four processes.

| Process | Responsibility |
|---|---|
| `livekit-server --dev` | Routes loopback audio and data. |
| Agent worker | Holds credentials, protocol state, timers, and the event log. |
| `aiohttp` server | Serves the page and mints join tokens. It is separate because the worker manages its own processes. |
| Browser tab | Provides microphone, speaker, display, and the listener-side probe. It does not hold product state. |

The browser could be replaced with a tablet client without changing the agent.

### Offline work and session work

Ingestion and preparation happen before the worker starts. They do not add
latency to a session.

| Script | Output |
|---|---|
| `scripts/ingest_protocol.py` | Ordered source steps and declared timers, using `z-ai/glm-5.3`. |
| `scripts/prepare_protocol.py` | Spoken steps and retrieval terms. `z-ai/glm-5.3-flash` writes; `openai/gpt-5-mini` checks values. |

A rule table was tested before the second model. On 30 prepared steps it
rejected five valid steps and did not catch an invalid one. The notation that
caused each false rejection was not covered by the table. Two deterministic
checks remain: prepared text contains no digits, and every retrieval term is a
plain word.

### Modules

| Module | Responsibility |
|---|---|
| `protocol.py` | Loads the corpus and prepared spoken form. Rejects unprepared protocols. |
| `position.py` | Stores the current protocol pointer. |
| `retrieval.py` | Ranks matching steps with BM25. |
| `markup.py` | Applies Rime `spell()` markup in `tts_node`; the model never receives markup. |
| `speech.py` | Supplies greetings, timer announcements, and tool-work status text. |
| `tools.py` | Changes state and returns text for the model to say. |
| `tts_rime.py` | Fences utterance contexts so interrupted audio cannot enter its replacement. |
| `timers.py` | Manages declared and spoken timers. |
| `events.py` | Writes the append-only event log used by measurement scripts. |
| `scoring.py` | Scores recovered numeric, unit, and acronym tokens. |
| `scripted.py` | Sends a fixed question list to a live session. |

The available tools are `start_protocol`, `read_current`, `next_step`,
`previous_step`, `go_to_step`, `look_up`, `start_timer`, `cancel_timer`,
`list_timers`, and `where_are_we`.

Tools change state and return the text to speak. The model produces the one
utterance sent to Rime. Earlier versions let tools speak directly and then also
spoke the model reply, which read each step twice.

## Services

| Service | Use |
|---|---|
| Rime | Speech synthesis: `mistv3`, `luna`, `lang=eng`, `wss://users-ws.rime.ai/ws3`, PCM 22,050 Hz mono, `segment=never`, `pauseBetweenBrackets=true`, and `phonemizeBetweenBrackets=true`. `POST /oov` is used offline to find unknown words. |
| OpenRouter | Conversation model `deepseek/deepseek-v4-flash`, pinned to `baidu/fp8`, plus the offline models. Section 2a of `RIME_EVIDENCE.md` records the measured choice. |
| LiveKit | Local media transport in development. |
| LiveKit inference gateway | Streaming recognition with `deepgram/nova-3`, turn detection with `turn-detector-v1`, and adaptive interruption at `https://agent-gateway.livekit.cloud/v1`. |

Microphone audio is sent to LiveKit's inference gateway for recognition and
turn detection. Media stays on loopback. OpenRouter receives text, not audio.
If turn detection fails, it uses the local `v1-mini` fallback downloaded above.
Recognition has no fallback.

`segment=never` prevents default segmentation at the decimal point in values
such as `0.5`. The speaker is explicit because the plugin default is `cove`,
which was not used for the measurements. Coda is not used because it lacks the
`spell()` stage and custom pauses used here.

## Failure behaviour

| Condition | Behaviour |
|---|---|
| User interruption | Stops the current utterance, handles the question, and asks before continuing. |
| Rime failure | Produces no substitute speech, holds the pointer, and logs `provider_failure`. |
| Recognition failure | Stops accepting speech input. |
| Missing protocol information | States that the protocol does not contain the answer. |
| Unprepared protocol | Refuses to load it. |
| Two timer expiries | Announces both in order. |
| Interrupted step | Does not record the step as read. |

## Limits

- Interruption latency has not been measured from user-speech onset to the last
  rendered audio sample. The mechanism has been exercised in live runs.
- The round-trip score uses a recogniser. It does not show listener performance
  in hood noise, and no listening test has been run.
- The result covers two protocols and 31 steps. One token changes a percentage
  by about one point.
- All reported media measurements use loopback on one laptop.
- A bench scientist has not reviewed the corpus. A non-specialist checked the
  sourced steps.

## Documents

| File | Contents |
|---|---|
| [`RIME_EVIDENCE.md`](RIME_EVIDENCE.md) | Measurement methods, results, source files, and limits. |
| [`data/corpus/`](data/corpus/) | Sources, parsed steps, spoken forms, and citations. |
