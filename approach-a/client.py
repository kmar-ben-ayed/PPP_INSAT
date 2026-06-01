"""
client.py
─────────────────────────────────────────────────────────────────────────────
Interactive CLI client for the INSAT FAQ chatbot running on Hugging Face Spaces.

Install dependency (once):
    pip install gradio_client

Run:
    python client.py

Multi-turn conversation is supported: the history is kept in memory and sent
with every request so the model has context for follow-up questions.
Type  'clear'  to wipe history,  'exit'  to quit.
─────────────────────────────────────────────────────────────────────────────
"""

import json
import time
from gradio_client import Client

# ─────────────────────────────────────────────────────────────────────────────
#  CONFIG  ← change these two lines before running
# ─────────────────────────────────────────────────────────────────────────────
SPACE_URL = "elyes0007/phi3-mini-chat"
HF_TOKEN  = None       # set to "hf_xxxxxxxxxxxx" if your Space is private
# ─────────────────────────────────────────────────────────────────────────────


def make_client() -> Client:
    """Connect to the Hugging Face Space."""
    return Client(SPACE_URL, token=HF_TOKEN)


def ask(question: str, history: list, client: Client) -> str:
    """
    Send one question to the Space and return the answer string.

    history: list of {"role": "user"/"assistant", "content": "..."} dicts.
             Pass an empty list [] for a fresh conversation.
    """
    response = client.predict(
        question,           # positional arg 1 → message
        json.dumps(history),# positional arg 2 → history_json
        api_name="/chat",
    )
    return response


def main() -> None:
    print(f"\n🔗  Connecting to {SPACE_URL} …")
    client = make_client()
    print("✅  Connected\n")
    print("INSAT FAQ Chatbot — remote CLI")
    print("Commands:  'clear' = reset history   |   'exit' = quit")
    print("─" * 60)

    history: list = []   # [{"role": "user"/"assistant", "content": "..."}]

    while True:
        try:
            question = input("\n You ▶ ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nBye!")
            break

        if not question:
            continue

        if question.lower() == "exit":
            print("Bye!")
            break

        if question.lower() == "clear":
            history = []
            print("  [history cleared]")
            continue

        t0 = time.perf_counter()
        try:
            answer = ask(question, history, client)
        except Exception as exc:
            print(f"  ❌  Request failed: {exc}")
            continue
        elapsed = time.perf_counter() - t0

        print(f"\n Bot ▶ {answer}")
        print(f"       ⏱  {elapsed:.2f}s")

        # Append to history for the next turn
        history.append({"role": "user",      "content": question})
        history.append({"role": "assistant", "content": answer})


if __name__ == "__main__":
    main()
