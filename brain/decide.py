import json
import re
from typing import Optional

from brain.context import Context
from brain.memory import Memory
from config import config


def build_vision_prompt(
    persona_prompt: str,
    context: Context,
    memory: Memory,
    page_url: str,
) -> str:
    return (
        f"{persona_prompt}\n\n"
        f"## Current State\n"
        f"URL: {page_url}\n"
        f"Step in session: {context.step_count + 1}\n"
        f"Session actions so far: {memory.session_actions}\n\n"
        f"## Recent Activity\n"
        f"{memory.recent_summary()}\n\n"
        f"## Available Actions\n"
        f'Respond with a JSON object:\n'
        f'{{"action": "...", "reason": "...", ...params}}\n\n'
        f"Actions:\n"
        f"- click (target)\n"
        f"- type (target, text)\n"
        f"- scroll_down (amount)\n"
        f"- scroll_up (amount)\n"
        f"- navigate (url)\n"
        f"- wait (seconds)\n"
        f"- tweet (text)\n"
        f"- like (tweet_index)\n"
        f"- reply (tweet_index, text)\n"
        f"- retweet (tweet_index)\n"
        f"- bookmark (tweet_index)\n"
        f"- done (reason)\n"
    )


def parse_decision(text: str) -> Optional[dict]:
    json_match = re.search(r"\{.*\}", text, re.DOTALL)
    if not json_match:
        return None
    try:
        return json.loads(json_match.group())
    except json.JSONDecodeError:
        return None
