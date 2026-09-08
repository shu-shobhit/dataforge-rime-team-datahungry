# Span assembly

Step: `Add 0.5 µL of 10 mM dNTP mix to tube 3. Incubate at 98 °C for 30 seconds.`

| build | duration |
|---|---|
| A, one request with `<400>` markers | 12.81 s |
| B, per span, hazards slowed at alpha 1.4 | 17.57 s |
| C, per span, no slowing | 14.82 s |

## Exact span offsets in build B

Known by construction, not read from any timestamps event.

| span | hazard | start | end |
|---|---|---|---|
| `s1.carrier0` | carrier | 0.00 s | 0.40 s |
| `s1.v1` | H1 | 0.80 s | 3.59 s |
| `s1.carrier2` | carrier | 3.99 s | 4.33 s |
| `s1.c1` | H7 | 4.73 s | 6.08 s |
| `s1.r1` | H3 | 6.48 s | 8.48 s |
| `s1.carrier6` | carrier | 8.88 s | 9.51 s |
| `s1.t1` | H5 | 9.91 s | 10.82 s |
| `s1.carrier8` | carrier | 11.22 s | 12.03 s |
| `s1.k1` | H7 | 12.43 s | 14.70 s |
| `s1.carrier10` | carrier | 15.10 s | 15.43 s |
| `s1.d1` | H7 | 15.83 s | 17.06 s |
| `s1.carrier12` | carrier | 17.46 s | 17.57 s |

Listen to A against B: the question is whether B sounds chopped at the joins.
