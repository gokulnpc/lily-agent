"""Live router quality check — runs the real Haiku 4.5 router over varied
utterances and prints each classification. The one real LLM call in step 2.

    AWS_PROFILE=partselect-dev uv run python -m lily_orchestrator.tools.router_demo
"""

from __future__ import annotations

import os

import boto3

from lily_orchestrator.converse import DEFAULT_ROUTER_MODEL
from lily_orchestrator.router import classify

UTTERANCES = [
    "Is PS11752778 compatible with my WDT780SAEM1 model?",
    "How can I install part number PS11752778?",
    "The ice maker on my Whirlpool fridge is not working. How can I fix it?",
    "Where's my order 38123, email jane@x.com?",
    "I need to return a part I bought last week",
    "do you sell a door bin for a Frigidaire fridge?",
    "how much is PS11746591 and is it in stock",
    "Can you recommend a good microwave?",  # out of scope
    "what should I make for dinner",  # out of scope
    "find me a drain pump and check if it fits my WDT780SAEM1",  # ambiguous / multi-intent
]


def main() -> int:
    region = os.environ.get("AWS_REGION", "us-east-1")
    model = DEFAULT_ROUTER_MODEL
    client = boto3.client("bedrock-runtime", region_name=region)
    print(f"router model: {model}\n", flush=True)
    for utterance in UTTERANCES:
        intents = classify(client, utterance, model_id=model)
        print(f"  {intents!s:40}  {utterance}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
