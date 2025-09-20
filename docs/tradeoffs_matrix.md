# Model Tradeoffs (Speed vs Quality)

| Task          | Baseline Model         | Speed (↑ faster) | Quality (↑ better) | Notes                                   |
|---------------|-------------------------|------------------:|-------------------:|-----------------------------------------|
| Summary       | `t5-small`              | High             | Medium             | Good enough for short notes             |
| Action Items  | `google/flan-t5-small`  | Medium           | Higher             | More instruction-following               |
| Brainstorm    | `google/flan-t5-small`  | Medium           | Higher             | Slightly richer, still lightweight       |
| Risk Scan     | `google/flan-t5-small`  | Medium           | Higher             | Add guardrails for sensitive terms       |

**Tip:** Start small (T5/FLAN-T5). If you hit quality limits, jump to larger FLAN-T5 or task-specific models.
