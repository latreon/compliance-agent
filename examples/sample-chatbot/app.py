"""Sample non-compliant chatbot for demonstration.

Intentionally missing: AI disclosure (Art. 50), event logging (Art. 12).
Run `compliance-agent scan examples/sample-chatbot` to see the findings.
"""

import openai

client = openai.OpenAI()


def chat(user_input: str) -> str:
    """Simple chat function without any compliance measures."""
    response = client.chat.completions.create(
        model="gpt-4",
        messages=[
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": user_input},
        ],
    )
    return response.choices[0].message.content


if __name__ == "__main__":
    while True:
        user_input = input("You: ")
        if user_input.lower() in ("quit", "exit"):
            break
        print(f"AI: {chat(user_input)}")
