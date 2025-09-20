# Prompt Mental Models (Short Guide)

## 1) Task + Context + Format
- **Task:** What do you want? (e.g., summarize, extract action items)
- **Context:** What’s the source? (meeting notes, PRD, email thread)
- **Format:** How should output look? (bullets, table, JSON)

## 2) Constrain for Reliability
- Limit length (e.g., "<= 5 bullets").
- Specify style (e.g., "one line each, imperative voice").
- Avoid ambiguity (e.g., define “owners” vs “stakeholders”).

## 3) Iterate Quickly
- Run, skim result, tighten instruction, re-run.
- Save good prompts in the **Prompt Library** and re-use.

## 4) Model Fit
- Encoder-decoder (T5/FLAN-T5) do well on summarize/extract.
- For longer contexts, consider long-context models or chunking.

## 5) Safety by Default
- Redact PII and cap output length when sharing or storing logs.
