"""Optional structured final reports, rendered as Markdown for the CLI."""

from typing import Literal

from pydantic import BaseModel


class CampaignDraft(BaseModel):
    kind: Literal["ad_copy", "headlines", "blog_outline", "social_posts", "email"]
    content: str


class CampaignReport(BaseModel):
    """The schema guarantees report shape, not factual accuracy or tool execution."""
    title: str
    summary: str
    knowledge: list[str]
    research: list[str]
    analytics: list[str]
    drafts: list[CampaignDraft]
    recommendations: list[str]
    limitations: list[str]

    def to_markdown(self) -> str:
        sections = [f"# {self.title}", self.summary]
        for title, items in [("Knowledge", self.knowledge), ("Research", self.research),
                             ("Analytics", self.analytics), ("Recommendations", self.recommendations),
                             ("Limitations", self.limitations)]:
            sections.extend([f"## {title}", "\n".join(f"- {item}" for item in items)
                             or "Not requested or unavailable."])
        sections.append("## Drafts — for human review")
        sections.extend(f"### {draft.kind.replace('_', ' ').title()}\n\n{draft.content}" for draft in self.drafts)
        if not self.drafts:
            sections.append("No drafts requested or available.")
        return "\n\n".join(sections)
