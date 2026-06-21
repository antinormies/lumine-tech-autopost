import argparse

from agent.driver import BrowserDriver
from agent.vision import VisionAgent
from config import config
from llm.client import LLMClient
from persona.manager import PersonaManager
from utils.logger import logger


def main():
    parser = argparse.ArgumentParser(description="Lumine Tech Autopost - Twitter vision bot")
    parser.add_argument("--persona", default=config.DEFAULT_PERSONA, help="Persona name")
    parser.add_argument("--headless", action="store_true", help="Run browser headless")
    parser.add_argument("--steps", type=int, default=30, help="Max agent steps")
    args = parser.parse_args()

    logger.info("=== Lumine Tech Autopost ===")
    logger.info(f"LLM: {config.LLM_BASE_URL}, model={config.LLM_MODEL}")

    pm = PersonaManager()
    persona = pm.get(args.persona)
    if not persona:
        logger.error(f"Persona '{args.persona}' not found. Available: {pm.list_personas()}")
        return

    logger.info(f"Using persona: {persona.name}")
    system_prompt = persona.build_system_prompt()

    llm = LLMClient()

    driver = BrowserDriver(headless=args.headless)
    try:
        page = driver.start()

        if not driver.is_logged_in():
            logger.error("Not logged in. Make sure Brave profile has an active X session.")
            return

        agent = VisionAgent(page=page, llm=llm, system_prompt=system_prompt)
        agent.run_session(max_steps=args.steps)
    except KeyboardInterrupt:
        logger.info("Interrupted by user")
    finally:
        driver.close()


if __name__ == "__main__":
    main()
