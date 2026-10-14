"""Explicit application-level rules and skills; no hidden discovery or plugin system."""

from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SKILLS = {"campaign-review": PROJECT_ROOT / "skills" / "campaign-review.md"}


def load_custom_instructions(skill: str | None = None) -> str:
    instructions = (PROJECT_ROOT / "rules" / "marketing.md").read_text(encoding="utf-8")
    if skill is not None:
        if skill not in SKILLS:
            raise ValueError(f"Unknown skill: {skill}. Available: {', '.join(SKILLS)}")
        instructions += "\n\nSelected procedure:\n" + SKILLS[skill].read_text(encoding="utf-8")
    return instructions
