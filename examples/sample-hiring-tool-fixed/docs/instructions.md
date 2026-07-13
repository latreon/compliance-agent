# Instructions for Use — Resume Screener v2.1.0

_EU AI Act Article 13(2)-(3). Generated 2026-07-13T09:26:08+00:00. Give this document to
every deployer before they operate the system; update it every release._

## 1. Provider identity

Example GmbH, compliance@example.com

## 2. Intended purpose

Ranks incoming job applications by fit against a role's stated requirements. Output is a recommendation, not a hiring decision.

## 3. Accuracy, robustness, and cybersecurity (see Art. 15)

- **precision@10:** 0.71
- **measured on:** held-out 2025 hires

## 4. Known and foreseeable limitations

- Underperforms on non-English resumes
- Not validated for executive-level roles

## 5. Foreseeable misuse

- Using the score as the sole basis for rejection

## 6. Human oversight measures (see Art. 14)

A recruiter reviews and can override every ranking before rejection.

## 7. Input data requirements

Resume must be plain text or PDF, under 10 pages.

## 8. How to interpret outputs

Score is 0-100 relative fit, not a probability of success.

## 9. Expected lifetime and maintenance

- **Expected lifetime:** Re-validate accuracy every 6 months or after a model change.
- **Maintenance measures:** Retraining triggers a new version and a new instructions document.
