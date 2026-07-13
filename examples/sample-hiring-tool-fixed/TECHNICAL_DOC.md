# Technical Documentation — Resume Screener v2.1.0

_EU AI Act Article 11 / Annex IV. Generated 2026-07-13T09:26:08+00:00. Keep this document
in version control and update it with every release._

## 1. General description

- **Provider:** Example GmbH
- **System:** Resume Screener
- **Version:** 2.1.0

## 2. Intended purpose

Ranks job applicants by fit; a recruiter makes the final call.

## 3. Models and components

- gpt-4o-mini (OpenAI API)

## 4. System architecture

Resume + job requirements -> LLM scoring call -> recruiter review queue.

## 5. Data and data governance (see Art. 10)

- applicant tracking system (candidate resumes, consented)

## 6. Human oversight (see Art. 14)

A recruiter reviews and can override every ranking before rejection.

## 7. Performance and metrics

- **precision@10:** 0.71 (held-out 2025 hires)

## 8. Known limitations

- Underperforms on non-English resumes
- Not validated for executive roles
