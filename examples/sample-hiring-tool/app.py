"""Sample non-compliant hiring tool for demonstration.

This is a realistic minimal candidate-ranking service that ComplianceAgent
flags as HIGH-RISK (Annex III(4) — employment, workers management, and
access to self-employment). It is INTENTIONALLY missing the compliance
measures the EU AI Act requires for a high-risk system:

  MISSING: risk management system (Art. 9)
  MISSING: data governance for the resume/scoring data (Art. 10)
  MISSING: technical documentation (Art. 11)
  MISSING: event logging (Art. 12)
  MISSING: instructions for use to deployers (Art. 13)
  MISSING: human oversight checkpoint before a hiring decision (Art. 14)
  MISSING: accuracy documentation, error handling, cybersecurity (Art. 15)
  MISSING: quality management system (Art. 17)
  MISSING: conformity assessment before market placement (Art. 43)

Run `compliance-agent scan examples/sample-hiring-tool` from the repo root to
see the findings, then `compliance-agent recommend ... --output ./fixes`
for the templates that close each gap.
"""

import os
import sys

import openai


def rank_candidate(client: openai.OpenAI, resume_text: str, job_requirements: str) -> float:
    """Score one job applicant's resume against a role's requirements.

    Used directly for hiring decisions: candidates below the cutoff are
    auto-rejected by the caller. No human reviews an individual score before
    rejection (Art. 14 gap), nothing records that this decision was made
    (Art. 12 gap), and a failed model call raises straight into the caller
    (Art. 15 gap).
    """
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {
                "role": "system",
                "content": "You are a recruiting assistant that scores job applicants.",
            },
            {
                "role": "user",
                "content": (
                    f"Job requirements: {job_requirements}\n\n"
                    f"Candidate resume: {resume_text}\n\n"
                    "Score this candidate from 0-100 for fit. Reply with only the number."
                ),
            },
        ],
    )
    return float(response.choices[0].message.content)


def screen_applicants(
    client: openai.OpenAI, resumes: list[str], job_requirements: str, cutoff: float = 60.0
) -> list[str]:
    """Auto-reject applicants scoring below cutoff. Returns the surviving resumes."""
    return [r for r in resumes if rank_candidate(client, r, job_requirements) >= cutoff]


def main() -> None:
    if not os.environ.get("OPENAI_API_KEY"):
        sys.exit("Set OPENAI_API_KEY to run this example: export OPENAI_API_KEY=sk-...")

    client = openai.OpenAI()
    job_requirements = "5+ years Python, distributed systems experience"
    resumes = [
        "10 years backend engineering, led a team building a distributed job scheduler.",
        "Recent bootcamp grad, one internship in frontend development.",
    ]
    survivors = screen_applicants(client, resumes, job_requirements)
    print(f"{len(survivors)}/{len(resumes)} candidates advanced to interview.")


if __name__ == "__main__":
    main()
