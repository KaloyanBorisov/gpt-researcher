import os
import sys
import json
import logging
import uuid
import httpx
import time
from typing import Dict, Any, Optional
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, UploadFile, File, HTTPException, Request, Body
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse, FileResponse
from contextlib import asynccontextmanager

# Ensure project root is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from services.common.schemas import ResearchRequest, ExportRequest, ChatRequest
from services.common.config import settings
from services.common.redis_pubsub import event_bus

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger("api_gateway")

@asynccontextmanager
async def lifespan(app: FastAPI):
    await event_bus.initialize()
    os.makedirs(settings.OUTPUTS_DIR, exist_ok=True)
    os.makedirs(settings.DOCS_DIR, exist_ok=True)
    logger.info("API Gateway initialized with microservices backend.")
    yield
    logger.info("API Gateway shutting down.")

app = FastAPI(title="GPT Researcher - API Gateway", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Static files mount
if os.path.exists(settings.OUTPUTS_DIR):
    app.mount("/outputs", StaticFiles(directory=settings.OUTPUTS_DIR), name="outputs")

frontend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../frontend"))
if os.path.exists(frontend_dir):
    app.mount("/site", StaticFiles(directory=frontend_dir), name="frontend")
    static_dir = os.path.join(frontend_dir, "static")
    if os.path.exists(static_dir):
        app.mount("/static", StaticFiles(directory=static_dir), name="static")

@app.get("/health")
async def health_check():
    async with httpx.AsyncClient(timeout=3.0) as client:
        services_status = {}
        for name, url in [
            ("orchestrator", settings.ORCHESTRATOR_URL),
            ("scraper", settings.SCRAPER_URL),
            ("document", settings.DOCUMENT_URL),
            ("export", settings.EXPORT_URL),
        ]:
            try:
                res = await client.get(f"{url}/health")
                services_status[name] = res.json().get("status", "unknown")
            except Exception as e:
                services_status[name] = f"unreachable ({e.__class__.__name__})"

    return {
        "status": "ok",
        "service": "api-gateway",
        "services": services_status
    }

@app.post("/api/research")
async def start_research(request: ResearchRequest):
    session_id = request.session_id or str(uuid.uuid4())
    request.session_id = session_id

    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            res = await client.post(
                f"{settings.ORCHESTRATOR_URL}/research",
                json=request.model_dump()
            )
            return res.json()
        except Exception as e:
            logger.error(f"Failed to forward research request to orchestrator: {e}")
            raise HTTPException(status_code=502, detail=f"Orchestrator service unavailable: {str(e)}")

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    session_id = str(uuid.uuid4())
    logger.info(f"Client connected to WebSocket with session ID {session_id}")

    channel = f"research:{session_id}"
    
    async def listen_to_events():
        async for event in event_bus.subscribe(channel):
            try:
                await websocket.send_json(event)
            except Exception as e:
                logger.error(f"Error sending event to WebSocket client: {e}")
                break

    import asyncio
    listener_task = asyncio.create_task(listen_to_events())

    try:
        while True:
            data = await websocket.receive_text()
            if data.startswith("start "):
                json_str = data[6:]
                payload = json.loads(json_str)
                req = ResearchRequest(
                    task=payload.get("task", ""),
                    report_type=payload.get("report_type", "research_report"),
                    report_source=payload.get("report_source", "web"),
                    tone=payload.get("tone", "Objective"),
                    session_id=session_id,
                    generate_in_background=True
                )
                async with httpx.AsyncClient(timeout=10.0) as client:
                    await client.post(f"{settings.ORCHESTRATOR_URL}/research", json=req.model_dump())
            elif data == "ping":
                await websocket.send_text("pong")
    except WebSocketDisconnect:
        logger.info(f"Client disconnected from WebSocket session {session_id}")
    finally:
        listener_task.cancel()

# Forward document endpoints
@app.get("/api/documents")
async def get_documents():
    async with httpx.AsyncClient(timeout=10.0) as client:
        res = await client.get(f"{settings.DOCUMENT_URL}/documents")
        return res.json()

@app.post("/api/upload")
async def upload_document(file: UploadFile = File(...)):
    async with httpx.AsyncClient(timeout=30.0) as client:
        file_bytes = await file.read()
        res = await client.post(
            f"{settings.DOCUMENT_URL}/upload",
            files={"file": (file.filename, file_bytes, file.content_type)}
        )
        return res.json()

# Forward export endpoint
@app.post("/api/export")
async def export_report(request: ExportRequest):
    async with httpx.AsyncClient(timeout=30.0) as client:
        res = await client.post(f"{settings.EXPORT_URL}/export", json=request.model_dump())
        return res.json()

# Reports Storage & Chat Endpoints
REPORTS_DB_PATH = os.path.join(settings.OUTPUTS_DIR, "reports_history.json")

def load_reports_db() -> Dict[str, Any]:
    if os.path.exists(REPORTS_DB_PATH):
        try:
            with open(REPORTS_DB_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}

def save_reports_db(data: Dict[str, Any]):
    os.makedirs(settings.OUTPUTS_DIR, exist_ok=True)
    with open(REPORTS_DB_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

@app.get("/api/reports")
async def list_reports():
    db = load_reports_db()
    return {"reports": list(db.values())}

@app.post("/api/reports")
async def create_report(payload: Dict[str, Any] = Body(...)):
    db = load_reports_db()
    report_id = payload.get("id") or str(uuid.uuid4())
    payload["id"] = report_id
    if "created_at" not in payload:
        payload["created_at"] = time.time()
    db[report_id] = payload
    save_reports_db(db)
    return payload

@app.get("/api/reports/{id}")
async def get_report(id: str):
    db = load_reports_db()
    if id in db:
        return db[id]
    return {"id": id, "report": "", "title": "Research Report", "created_at": time.time()}

@app.put("/api/reports/{id}")
async def update_report(id: str, payload: Dict[str, Any] = Body(...)):
    db = load_reports_db()
    report_data = db.get(id, {"id": id, "created_at": time.time()})
    report_data.update(payload)
    db[id] = report_data
    save_reports_db(db)
    return report_data

@app.delete("/api/reports/{id}")
async def delete_report(id: str):
    db = load_reports_db()
    if id in db:
        del db[id]
        save_reports_db(db)
    return {"success": True}

@app.get("/api/reports/{id}/chat")
async def get_report_chat(id: str):
    db = load_reports_db()
    report = db.get(id, {})
    return report.get("chat_history", [])

@app.post("/api/reports/{id}/chat")
async def post_report_chat(id: str, payload: Dict[str, Any] = Body(...)):
    db = load_reports_db()
    report = db.get(id, {"id": id, "created_at": time.time()})
    chat_history = report.get("chat_history", [])
    message = payload.get("message", "")
    chat_history.append({"role": "user", "content": message, "timestamp": time.time()})
    
    ai_response = "Thank you for your question regarding this report."
    report_text = report.get("report", "")
    if settings.OPENAI_API_KEY and report_text:
        try:
            from openai import AsyncOpenAI
            client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
            comp = await client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": f"You are a helpful assistant answering questions about the following research report:\n\n{report_text[:4000]}"},
                    {"role": "user", "content": message}
                ]
            )
            ai_response = comp.choices[0].message.content or ai_response
        except Exception as chat_err:
            logger.warning(f"Error generating chat answer: {chat_err}")
    
    chat_history.append({"role": "assistant", "content": ai_response, "timestamp": time.time()})
    report["chat_history"] = chat_history
    db[id] = report
    save_reports_db(db)
    return {"response": ai_response, "chat_history": chat_history}

@app.post("/api/chat")
async def general_chat(payload: Dict[str, Any] = Body(...)):
    report = payload.get("report", "")
    messages = payload.get("messages", [])
    
    user_message = ""
    for msg in reversed(messages):
        if msg.get("role") == "user":
            user_message = msg.get("content", "")
            break
            
    openai_key = os.getenv("OPENAI_API_KEY") or settings.OPENAI_API_KEY
    ai_answer = ""
    
    if openai_key and user_message:
        try:
            chat_prompts = [
                {
                    "role": "system",
                    "content": (
                        "You are an expert research analyst assistant. Answer the user's questions accurately and concisely "
                        f"based on the following research context:\n\n{report[:6000] if report else 'General research query.'}"
                    )
                }
            ]
            
            for m in messages[-6:-1]:
                chat_prompts.append({"role": m.get("role", "user"), "content": m.get("content", "")})
            
            chat_prompts.append({"role": "user", "content": user_message})
            
            async with httpx.AsyncClient(timeout=30.0) as client:
                res = await client.post(
                    "https://api.openai.com/v1/chat/completions",
                    headers={
                        "Authorization": f"Bearer {openai_key.strip()}",
                        "Content-Type": "application/json"
                    },
                    json={
                        "model": "gpt-4o-mini",
                        "messages": chat_prompts,
                        "temperature": 0.4
                    }
                )
                if res.status_code == 200:
                    data = res.json()
                    ai_answer = data["choices"][0]["message"]["content"]
                else:
                    logger.error(f"OpenAI chat response error: {res.status_code} - {res.text}")
                    ai_answer = f"Error from OpenAI: {res.text}"
        except Exception as e:
            logger.error(f"Error in /api/chat endpoint: {e}", exc_info=True)
            ai_answer = f"Error generating answer: {str(e)}"
    elif not openai_key:
        ai_answer = "Please configure your OPENAI_API_KEY in .env to enable interactive chat on research reports."
    else:
        ai_answer = "I'm ready to answer any questions about your report. What would you like to know?"
            
    return {
        "response": {
            "role": "assistant",
            "content": ai_answer,
            "timestamp": int(time.time() * 1000)
        }
    }

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("GATEWAY_PORT", "8000"))
    uvicorn.run(app, host="0.0.0.0", port=port)
