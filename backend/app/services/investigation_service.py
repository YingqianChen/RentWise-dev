"""Investigation workflow service."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..db.models import InvestigationItem, SearchProject
from ..agent.investigation_graph import investigation_graph
from ..schemas.dashboard import InvestigationItemSummary


class InvestigationService:
    """Runs the lightweight investigation workflow."""

    async def run(self, project, candidates):
        """Run the graph and return the latest dashboard-oriented state."""
        initial_state = {
            "project": project,
            "candidates": candidates,
            "priority_candidates": [],
            "open_items": [],
            "current_advice": "",
        }
        return await investigation_graph.ainvoke(initial_state)

    async def sync_items(
        self,
        db: AsyncSession,
        project: SearchProject,
        generated_items: list[InvestigationItemSummary],
    ) -> tuple[list[InvestigationItemSummary], list[InvestigationItemSummary]]:
        """Persist current generated tasks while preserving user progress."""
        result = await db.execute(
            select(InvestigationItem).where(InvestigationItem.project_id == project.id)
        )
        existing_items = {item.id: item for item in result.scalars().all()}
        current_items: list[InvestigationItemSummary] = []

        for generated in generated_items:
            item = existing_items.get(generated.id)
            if item is None:
                item = InvestigationItem(
                    id=generated.id,
                    project_id=project.id,
                    candidate_id=generated.candidate_id,
                    category=generated.category,
                    title=generated.title,
                    question=generated.question,
                    priority=generated.priority,
                    status="open",
                )
                db.add(item)
                existing_items[item.id] = item
            else:
                item.candidate_id = generated.candidate_id
                item.category = generated.category
                item.title = generated.title
                item.question = generated.question
                item.priority = generated.priority

            current_items.append(
                generated.model_copy(update={"status": item.status, "note": item.note})
            )

        await db.flush()
        open_items = [item for item in current_items if item.status == "open"]
        closed_items = [item for item in current_items if item.status != "open"]
        return open_items, closed_items
