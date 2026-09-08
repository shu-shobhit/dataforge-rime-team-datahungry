# Gate 3: inlineSpeedAlpha, measured from the waveform

Speakers: mistv3 `alexis`, mistv2 `abbie`. Text: `Add [zero] [point] [five] microlitres of buffer.`

| case | total | speech |
|---|---|---|
| `http_v3_plain` | 2.65 s | 2.26 s |
| `http_v3_marked_noalpha` | 2.61 s | 2.22 s |
| `http_v3_slow_3` | 4.13 s | 3.72 s |
| `http_v3_fast_0.3` | 1.97 s | 1.58 s |
| `http_v3_slow_nospace` | 4.17 s | 3.78 s |
| `http_v2_plain` | error | - |
| `http_v2_slow_3` | error | - |
| `ws_v3_plain` | 2.67 s | 2.26 s |
| `ws_v3_slow_msg` | 2.67 s | 2.26 s |
| `ws_v3_slow_conn` | 2.67 s | 2.28 s |

## Verdicts

- HTTP Mist v3, alpha 3.0 (slower): 2.22 s to 3.72 s, ratio 1.68. HONOURED
- HTTP Mist v3, alpha 0.3 (faster): 2.22 s to 1.58 s, ratio 0.71. HONOURED
- WebSocket Mist v3, per message: 2.26 s to 2.26 s, ratio 1.00. IGNORED
- WebSocket Mist v3, connection flag: 2.26 s to 2.28 s, ratio 1.01. IGNORED

Clips are in `runs/gates/gate3` for a listening check.
