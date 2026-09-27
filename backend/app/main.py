from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.agents.graph import GRAPH_NODE_NAMES, compiled_graph
from app.api.admin import router as admin_router
from app.api.agent import router as agent_router
from app.api.appraisals import router as appraisals_router
from app.api.auth import router as auth_router
from app.api.activities import router as activities_router
from app.api.cycles import router as cycles_router
from app.api.evidence import router as evidence_router
from app.api.profile import router as profile_router
from app.api.reports import router as reports_router
from app.api.review import router as review_router
from app.api.teaching_requirements import router as teaching_requirements_router
from app.api.timetable import router as timetable_router
from app.api.attendance import router as attendance_router
from app.api.project_teams import router as project_teams_router
from app.core.config import get_settings
from app.scoring.engine import ENGINE_VERSION

settings = get_settings()

app = FastAPI(title="Faculty Appraisal Management System", version="0.2.0-phase2")
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(auth_router)
app.include_router(profile_router)
app.include_router(cycles_router)
app.include_router(activities_router)
app.include_router(evidence_router)
app.include_router(appraisals_router)
app.include_router(reports_router)
app.include_router(review_router)
app.include_router(admin_router)
app.include_router(agent_router)
app.include_router(teaching_requirements_router)
app.include_router(timetable_router)
app.include_router(attendance_router)
app.include_router(project_teams_router)


@app.get("/health")
def health() -> dict:
    _ = compiled_graph
    return {
        "status": "ok",
        "phase": 2,
        "pipeline": 2,
        "graph": "compiled",
        "graph_nodes": GRAPH_NODE_NAMES,
        "scoring_engine_version": ENGINE_VERSION,
        "llm_provider": settings.llm_provider,
        "storage_backend": settings.storage_backend,
        "scoring_disclaimer": "DEMO/TEST WEIGHTAGES — NOT OFFICIAL UGC",
    }
