# Making a hazard span unmistakable without sounding like a robot

Every variant spells the number out and writes the unit in full. That is what removes the confusable pairs. Only the shape of the sentence changes.

| variant | audio | timestamp overrun | idea |
|---|---|---|---|
| `v1_plain` | 8.83 s | -1.64 s | One sentence, no markup at all. The baseline for natural. |
| `v2_one_pause` | 9.01 s | -0.96 s | A single pause before the one value that would be catastrophic, nowhere else. |
| `v3_short_sentences` | 10.37 s | -1.29 s | Each value gets its own sentence, so the pause and the stress are the model's own. |
| `v4_value_last` | 10.51 s | -0.92 s | Restructured so the critical volume lands at the end of its clause, where stress falls naturally. |
| `v5_confirming` | 11.51 s | -1.75 s | Says the two most dangerous values a second time, the way a person actually would. |

Timestamp overrun is how far Rime's last reported word end sits past the actual end of the audio. Small is good: it means played state can trust the clock.
