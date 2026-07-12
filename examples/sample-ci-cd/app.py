"""Sample AI feature for the CI/CD gating example.

Deliberately non-compliant, same as the other examples — the point here is
not this file, it is `.github/workflows/compliance-gate.yml` next to it. This
file only needs to give the workflow something real to scan and fail on.

  MISSING: AI disclosure (Art. 50)
  MISSING: event logging (Art. 12)
"""

import os
import sys

import openai


def summarize_ticket(client: openai.OpenAI, ticket_text: str) -> str:
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": "Summarize this support ticket in one sentence."},
            {"role": "user", "content": ticket_text},
        ],
    )
    return response.choices[0].message.content


def main() -> None:
    if not os.environ.get("OPENAI_API_KEY"):
        sys.exit("Set OPENAI_API_KEY to run this example: export OPENAI_API_KEY=sk-...")
    client = openai.OpenAI()
    print(summarize_ticket(client, "My login keeps failing after the last update."))


if __name__ == "__main__":
    main()
