import os
import sys
import logging
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from services.common.schemas import SectionResearchRequest, SectionResearchResponse
from services.section_research_service.worker import worker

# Clean up empty env strings
for env_k in ["OPENAI_BASE_URL", "OPENAI_API_BASE", "OPENROUTER_BASE_URL", "OPENROUTER_API_BASE", "OPENROUTER_API_KEY", "GOOGLE_API_KEY", "ANTHROPIC_API_KEY"]:
    if env_k in os.environ and not os.environ[env_k].strip():
        del os.environ[env_k]

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger("section_research_service")

app = FastAPI(title="GPT Researcher - Section Research Microservice", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/health")
async def health_check():
    return {"status": "ok", "service": "section-research-service"}

@app.post("/research-section", response_model=SectionResearchResponse)
async def research_section(request: SectionResearchRequest):
    try:
        return await worker.research_section(request)
    except Exception as e:
        logger.error(f"Section research failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Section research error: {str(e)}")

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("SECTION_RESEARCH_PORT", "8012"))
    uvicorn.run(app, host="0.0.0.0", port=port)
