import json
import os
from typing import Optional

from utils.logger import logger

PERSONAS_DIR = os.path.join(os.path.dirname(__file__), "personas")


class Persona:
    def __init__(self, data: dict):
        self.name: str = data["name"]
        self.description: str = data.get("description", "")
        self.traits: list[str] = data.get("traits", [])
        self.topics: list[str] = data.get("topics", [])
        self.tone: str = data.get("tone", "casual")
        self.writing_style: dict = data.get("writing_style", {})
        self.engagement_rules: dict = data.get("engagement_rules", {})

    def build_system_prompt(self) -> str:
        traits_str = ", ".join(self.traits)
        topics_str = ", ".join(self.topics)
        return (
            f"You are {self.name}, a Twitter/X user. {self.description}\n\n"
            f"Your traits: {traits_str}\n"
            f"Your interests: {topics_str}\n"
            f"Your tone: {self.tone}\n\n"
            f"Writing rules:\n"
            f"- Tweet length: {self.writing_style.get('avg_tweet_length', 'medium')}\n"
            f"- Emojis: {self.writing_style.get('use_emojis', 'sparingly')}\n"
            f"- Hashtags: use {self.writing_style.get('use_hashtags', 'selectively')}, max {self.writing_style.get('max_hashtags', 2)}\n\n"
            f"IMPORTANT: You are controlling a browser. You see screenshots of Twitter. "
            f"Your job is to browse naturally like a human would. "
            f"Scroll the timeline, read tweets, and engage with content that interests you.\n\n"
            f"Respond with a JSON action. Always include a natural 'reason' field explaining your thought process."
        )

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "description": self.description,
            "traits": self.traits,
            "topics": self.topics,
            "tone": self.tone,
            "writing_style": self.writing_style,
            "engagement_rules": self.engagement_rules,
        }


class PersonaManager:
    def __init__(self):
        self.personas: dict[str, Persona] = {}
        self._load_all()

    def _load_all(self):
        if not os.path.exists(PERSONAS_DIR):
            logger.warning(f"Personas directory not found: {PERSONAS_DIR}")
            return
        for fname in os.listdir(PERSONAS_DIR):
            if fname.endswith(".json"):
                path = os.path.join(PERSONAS_DIR, fname)
                with open(path) as f:
                    data = json.load(f)
                    persona = Persona(data)
                    key = persona.name.lower().replace(" ", "_")
                    self.personas[key] = persona
                    logger.info(f"Loaded persona: {persona.name}")

    def get(self, name: str) -> Optional[Persona]:
        key = name.lower().replace(" ", "_")
        return self.personas.get(key)

    def list_personas(self) -> list[str]:
        return [p.name for p in self.personas.values()]
