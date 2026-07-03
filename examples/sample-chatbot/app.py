"""Sample non-compliant chatbot for demonstration.

This is a realistic minimal chatbot that ComplianceAgent flags. It is
INTENTIONALLY missing the compliance measures the EU AI Act requires:

  MISSING: AI disclosure (Art. 50) — users are never told they are
           talking to an AI system.
  MISSING: event logging (Art. 12) — no record of any AI interaction
           is kept.

Run `compliance-agent scan examples/sample-chatbot` from the repo root to
see the findings, then `compliance-agent recommend ... --output ./fixes`
for the templates that close each gap.
"""

import os
import sys

import openai


def chat(client: openai.OpenAI, user_input: str) -> str:
    """Send one user message to the model and return the reply.

    Note: no logging around this call (Art. 12 gap) and nothing tells the
    user the reply is AI-generated (Art. 50 gap).
    """
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": user_input},
        ],
    )
    return response.choices[0].message.content


def main() -> None:
    if not os.environ.get("OPENAI_API_KEY"):
        sys.exit("Set OPENAI_API_KEY to run this example: export OPENAI_API_KEY=sk-...")

    client = openai.OpenAI()
    # An Art. 50-compliant bot would print an AI disclosure notice here.
    print("Chatbot ready. Type 'quit' to exit.")
    while True:
        user_input = input("You: ")
        if user_input.lower() in ("quit", "exit"):
            break
        print(f"AI: {chat(client, user_input)}")


if __name__ == "__main__":
    main()
