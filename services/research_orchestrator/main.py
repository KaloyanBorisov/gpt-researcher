import os
import sys
import uuid
import logging
from fastapi import FastAPI, BackgroundTasks, HTTPException
from fastapi.middleware.cors import CORSMiddleware

# Ensure project root is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from services.common.schemas import ResearchRequest
from services.research_orchestrator.orchestrator import orchestrator

# Clean up empty env strings so SDKs (OpenAI, Anthropic, Tavily, etc.) don't attempt to use empty strings as URLs
for env_k in ["OPENAI_BASE_URL", "OPENAI_API_BASE", "GOOGLE_API_KEY", "ANTHROPIC_API_KEY"]:
    if env_k in os.environ and not os.environ[env_k].strip():
        del os.environ[env_k]

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger("research_orchestrator")

app = FastAPI(title="GPT Researcher - Research Orchestrator Microservice", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/health")
async def health_check():
    return {"status": "ok", "service": "research-orchestrator"}

@app.post("/research")
async def start_research(request: ResearchRequest, background_tasks: BackgroundTasks):
    session_id = request.session_id or str(uuid.uuid4())
    logger.info(f"Received research request: {request.task} (Session: {session_id})")

    if request.generate_in_background:
        background_tasks.add_task(orchestrator.execute_research, request, session_id)
        return {
            "session_id": session_id,
            "status": "processing",
            "message": "Research task started in background. Subscribe to events via WebSocket."
        }
    else:
        result = await orchestrator.execute_research(request, session_id)
        return result

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("ORCHESTRATOR_PORT", "8001"))
    uvicorn.run(app, host="0.0.0.0", port=port)
