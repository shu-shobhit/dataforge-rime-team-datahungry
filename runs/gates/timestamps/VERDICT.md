# Are the word timestamps accurate on /ws3?

Each reported word boundary is used to slice the audio. A slice that is silent, or that starts past the end of the audio, means the boundary is wrong. Slices are saved so the words can be checked by ear.

### `plain`

audio 4.13 s, speech ends 3.88 s, last timestamp 3.25 s

| word | start | end | energy in slice | verdict |
|---|---|---|---|---|
| `Add` | 0.00 | 0.17 |    3482 | ok |
| `zero` | 0.17 | 0.34 |    9245 | ok |
| `point` | 0.34 | 0.51 |    8315 | ok |
| `five` | 0.51 | 0.69 |    6613 | ok |
| `microlitres` | 0.69 | 1.03 |    4353 | ok |
| `of` | 1.03 | 1.20 |    6154 | ok |
| `ten` | 1.20 | 1.37 |    5437 | ok |
| `millimolar` | 1.37 | 1.88 |    5092 | ok |
| `buffer` | 1.88 | 2.06 |    3734 | ok |
| `to` | 2.06 | 2.23 |    4334 | ok |
| `tube` | 2.23 | 2.40 |    6571 | ok |
| `three.` | 2.40 | 3.25 |    4619 | ok |

**12 of 12 slices contain speech.**

### `commas`

audio 4.45 s, speech ends 4.16 s, last timestamp 6.00 s

| word | start | end | energy in slice | verdict |
|---|---|---|---|---|
| `Add,` | 0.00 | 0.51 |    6648 | ok |
| `zero` | 0.51 | 0.69 |    8767 | ok |
| `point` | 0.69 | 0.86 |    3488 | ok |
| `five` | 0.86 | 1.03 |    3989 | ok |
| `microlitres,` | 1.03 | 2.91 |    5237 | ok |
| `of` | 2.91 | 3.08 |    4198 | ok |
| `ten` | 3.08 | 3.25 |    3420 | ok |
| `millimolar` | 3.25 | 3.77 |    3662 | ok |
| `buffer,` | 3.77 | 4.80 |    2335 | ok |
| `to` | 4.80 | 4.97 |       0 | PAST END OF AUDIO |
| `tube` | 4.97 | 5.14 |       0 | PAST END OF AUDIO |
| `three.` | 5.14 | 6.00 |       0 | PAST END OF AUDIO |

**9 of 12 slices contain speech.**

### `pauses`

audio 4.65 s, speech ends 4.38 s, last timestamp 4.97 s

| word | start | end | energy in slice | verdict |
|---|---|---|---|---|
| `Add` | 0.00 | 0.17 |    3181 | ok |
| `<300>` | 0.17 | 1.03 |    6517 | ok |
| `zero` | 1.03 | 1.20 |    5365 | ok |
| `point` | 1.20 | 1.37 |    4613 | ok |
| `five` | 1.37 | 1.54 |    4828 | ok |
| `microlitres` | 1.54 | 1.88 |    5556 | ok |
| `<300>` | 1.88 | 2.74 |    3921 | ok |
| `of` | 2.74 | 2.91 |    6057 | ok |
| `ten` | 2.91 | 3.08 |    5460 | ok |
| `millimolar` | 3.08 | 3.60 |    4053 | ok |
| `buffer` | 3.60 | 3.77 |    3980 | ok |
| `to` | 3.77 | 3.94 |    2765 | ok |
| `tube` | 3.94 | 4.11 |    4230 | ok |
| `three.` | 4.11 | 4.97 |    1630 | ok |

**14 of 14 slices contain speech.**
