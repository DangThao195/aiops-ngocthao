import asyncio
import logging
import time
from typing import Optional
from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel, Field

logging.basicConfig(
    level=logging.INFO, 
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s'
)
logger = logging.getLogger('aiops')

app = FastAPI(
    title='AIOps Incident Pipeline',
    version='1.0.0',
    description='Correlate alerts → RCA → suggest action',
)

@app.middleware('http')
async def add_timing(request: Request, call_next):
    start = time.perf_counter()
    response = await call_next(request)
    duration_ms = (time.perf_counter() - start) * 1000
    response.headers['X-Response-Time-Ms'] = f"{duration_ms:.1f}"
    logger.info(
        f"{request.method} {request.url.path} "
        f"Status: {response.status_code} Duration: {duration_ms:.0f}ms"
    )
    return response

class Alert(BaseModel):
    id: str
    ts: str
    service: str
    metric: str
    severity: str
    value: float
    threshold: float
    labels: Optional[dict] = Field(default_factory=dict)

class IncidentRequest(BaseModel):
    alerts: list[Alert]

class Cluster(BaseModel):
    cluster_id: str
    alert_count: int
    services: list[str]
    time_range: list[str]

class RootCause(BaseModel):
    service: str
    confidence: float
    reasoning: str

class SimilarIncident(BaseModel):
    id: str
    similarity: float
    summary: str

class IncidentResponse(BaseModel):
    clusters: list[Cluster]
    root_cause: RootCause
    recommended_actions: list[str]
    similar_incidents: list[SimilarIncident]

GRAPH_LOADED = True 
HISTORY_LOADED = True

async def mock_process_pipeline(alerts: list[Alert]) -> dict:
    await asyncio.sleep(1.6)
    
    unique_services = list(set([a.service for a in alerts]))
    primary_service = unique_services[0] if unique_services else "unknown-svc"
    timestamps = [a.ts for a in alerts]
    time_range = [min(timestamps), max(timestamps)] if timestamps else ["N/A", "N/A"]

    return {
        'clusters': [
            {
                'cluster_id': 'c-hash-2026',
                'alert_count': len(alerts),
                'services': unique_services,
                'time_range': time_range
            }
        ],
        'root_cause': {
            'service': primary_service,
            'confidence': 0.85,
            'reasoning': f"High error rate / latency spikes detected on dependency path of {primary_service}."
        },
        'recommended_actions': [
            f"Check downstream connection pool of {primary_service}.",
            "Verify if any automated deployment/config change occurred within the gap window."
        ],
        'similar_incidents': [
            {
                'id': 'INC-2026-0512',
                'similarity': 0.78,
                'summary': f"Database connection exhaustion breaking {primary_service}."
            }
        ]
    }

@app.get('/healthz')
def healthz() -> dict:
    return {'status': 'ok'}

@app.get('/readyz')
def readyz() -> dict:
    checks = {
        'graph_data': GRAPH_LOADED,
        'incident_history': HISTORY_LOADED
    }
    if not all(checks.values()):
        logger.error(f"Readiness check failed: {checks}")
        raise HTTPException(status_code=503, detail=checks)
    return {'status': 'ready', 'checks': checks}

@app.post('/incident', response_model=IncidentResponse)
async def post_incident(req: IncidentRequest) -> IncidentResponse:
    logger.info(f"Received production batch with {len(req.alerts)} alerts")

    if not req.alerts:
        raise HTTPException(status_code=400, detail='Empty alert list')
    
    try:
        result = await mock_process_pipeline(req.alerts)
        return IncidentResponse(**result)
    except Exception as e:
        logger.error(f"Pipeline processing collapsed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal Pipeline Error: {str(e)}")