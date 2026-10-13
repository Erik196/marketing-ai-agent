"""The agent definition and its SDK runtime entry point."""

import os

from agents import Agent, Runner, RunConfig

DEFAULT_MODEL = "gpt-4.1-mini"

SYSTEM_INSTRUCTIONS = """You are MarketPilot AI, a practical marketing assistant.
Help users plan campaigns and draft clear, audience-specific marketing content.
Keep responses concise and use Markdown headings or lists when useful.
State assumptions when product details, budget, or campaign goals are missing.
Ask a focused clarification only when you cannot give a useful draft otherwise.
All emails and social posts are drafts for human review. Never claim to send,
publish, schedule, or perform external actions.
You currently have no tools, browsing, knowledge retrieval, or CSV access.
Do not claim to have researched current competitors or analyzed external data.
Distinguish general marketing suggestions from verified facts; never invent
citations, statistics, product features, or customer testimonials.
"""

"""
Creates and returns our Agent
"""
def create_marketing_agent(model: str | None = None) -> Agent:
    return Agent( # creates the agent
        name="MarketPilot AI",
        instructions=SYSTEM_INSTRUCTIONS,
        model=model or os.environ.get("MARKETPILOT_MODEL") or DEFAULT_MODEL,
    )

"""
Runs the whole harness
"""
async def run_marketing_agent(prompt: str, model: str | None = None) -> str:
    if not prompt.strip(): # checks for empty prompt
        raise ValueError("Please provide a nonempty marketing request.")
    if not os.environ.get("OPENAI_API_KEY", "").strip(): # checks if api key is missing
        raise ValueError("OPENAI_API_KEY is not set. Set it in your local environment.")
    
    result = await Runner.run(
        create_marketing_agent(model),
        input=prompt.strip(),
        max_turns=3,
        run_config=RunConfig(tracing_disabled=True),
    )
    return str(result.final_output)

