"""Sample hiring tool — AFTER applying ComplianceAgent's recommended fixes.

This is the same candidate-ranking service as the original sample-hiring-tool,
with the Art. 9/10/11/12/13/14/17/43 gaps closed using the exact templates
`compliance-agent recommend` generates (copied into ./compliance and ./fixes,
unmodified). See the sibling docs/ files and risk_register.json/TECHNICAL_DOC.md
for the artifact-level fixes; this file wires in the code-level ones:

  FIXED: event logging around every model call (Art. 12) — compliance/event_logging.py
  FIXED: human oversight checkpoint before a rejection (Art. 14) — compliance/human_oversight.py
  FIXED: AI transparency notice shown to operators (Art. 50) — compliance/transparency_notice.py

Run `compliance-agent scan .` from this directory and compare against
`compliance-agent scan ../sample-hiring-tool` to see the gap count drop.
"""

import logging
import os
import sys

import openai

from compliance.event_logging import AILogger, log_ai_call
from compliance.human_oversight import DecisionRisk, HumanOversightCheckpoint
from compliance.transparency_notice import ai_transparency_notice

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

ai_logger = AILogger(log_dir="ai_logs")
oversight = HumanOversightCheckpoint(
    risk_level=DecisionRisk.HIGH,
    audit_file="oversight_audit.jsonl",
    # A real deployment wires this to the recruiter's review queue; a fixed
    # "yes" here simulates an already-reviewed decision for this demo script
    # so it runs non-interactively instead of blocking on stdin.
    prompt_fn=lambda _prompt: "yes",
)


@log_ai_call(ai_logger=ai_logger)
def rank_candidate(client: openai.OpenAI, resume_text: str, job_requirements: str) -> float:
    """Score one job applicant's resume against a role's requirements.

    The score is a recommendation only: `screen_applicants` below routes every
    rejection through a human oversight checkpoint before it takes effect
    (Art. 14), and every call here is now recorded via `@log_ai_call` (Art. 12).
    """
    logger.info("Scoring candidate against job requirements")
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
    """Reject applicants scoring below cutoff, subject to human oversight.

    A recruiter (represented here by the oversight checkpoint) reviews and can
    override every rejection before it takes effect — the model's score never
    auto-rejects a candidate on its own (Art. 14(4)(d)-(e)).
    """
    survivors = []
    for resume in resumes:
        score = rank_candidate(client, resume, job_requirements)
        if score >= cutoff:
            survivors.append(resume)
            continue
        outcome = oversight.require_approval(
            decision=f"reject candidate (score={score:.0f})",
            context=resume[:80],
        )
        if not outcome["approved"]:
            survivors.append(resume)
    return survivors


@ai_transparency_notice
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
    logger.info("%d/%d candidates advanced to interview.", len(survivors), len(resumes))
    print(f"{len(survivors)}/{len(resumes)} candidates advanced to interview.")


if __name__ == "__main__":
    main()
