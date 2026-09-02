import os
import sys
import logging
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from services.common.schemas import SynthesisRequest, SynthesisResponse
from services.writer_service.writer import writer

# Clean up empty env strings
for env_k in ["OPENAI_BASE_URL", "OPENAI_API_BASE", "OPENROUTER_BASE_URL", "OPENROUTER_API_BASE", "OPENROUTER_API_KEY", "GOOGLE_API_KEY", "ANTHROPIC_API_KEY"]:
    if env_k in os.environ and not os.environ[env_k].strip():
        del os.environ[env_k]

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger("writer_service")

app = FastAPI(title="GPT Researcher - Writer & Synthesis Microservice", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/health")
async def health_check():
    return {"status": "ok", "service": "writer-service"}

@app.post("/synthesize", response_model=SynthesisResponse)
async def synthesize_report(request: SynthesisRequest):
    try:
        return await writer.synthesize_report(request)
    except Exception as e:
        logger.error(f"Report synthesis failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Synthesis error: {str(e)}")

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("WRITER_PORT", "8014"))
    uvicorn.run(app, host="0.0.0.0", port=port)
