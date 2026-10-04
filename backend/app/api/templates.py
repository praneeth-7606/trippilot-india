from fastapi import APIRouter

from app.planner.templates import list_templates

router = APIRouter(tags=["templates"])


@router.get("/itinerary-templates")
def get_templates():
    return {"templates": list_templates()}
