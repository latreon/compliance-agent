# Fundamental Rights Impact Assessment — Resume Screener

**System:** Resume Screener v2.1.0
**Deployer role:** private operator (internal recruiting tool)
**Process:** Ranks incoming job applications by fit against a role's stated
requirements; a recruiter reviews and can override every score before a
rejection takes effect.

## Affected persons

Job applicants whose resumes are scored by the system.

## Specific risks

- Uneven score distribution across demographic groups (disparate impact).
- A fabricated scoring rationale being trusted over the resume itself.

## Mitigation measures

- Quarterly bias audit of score distributions by demographic group.
- A recruiter reviews and can override every ranking before a rejection
  takes effect — the model's score never auto-rejects a candidate.
- Every rejection routes through a human oversight checkpoint
  (`compliance/human_oversight.py`) with a full audit trail.

## Complaint mechanism

A rejected candidate may request a human review of their application within
30 days via the recruiting team's published contact address. Requests are
logged and tracked to resolution alongside the oversight audit trail.
