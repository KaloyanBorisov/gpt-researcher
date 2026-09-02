import os
import sys
import logging
import shutil
from fastapi import FastAPI, HTTPException, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from typing import List, Dict, Any

# Ensure project root is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from services.common.schemas import DocumentQueryRequest, DocumentChunk
from services.common.config import settings
from gpt_researcher.document.document import DocumentLoader
from gpt_researcher.memory.embeddings import Memory

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger("document_service")

app = FastAPI(title="GPT Researcher - Document & Vector Microservice", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

os.makedirs(settings.DOCS_DIR, exist_ok=True)

@app.get("/health")
async def health_check():
    return {"status": "ok", "service": "document-service"}

@app.get("/documents")
async def list_documents():
    if not os.path.exists(settings.DOCS_DIR):
        return {"files": []}
    files = [f for f in os.listdir(settings.DOCS_DIR) if os.path.isfile(os.path.join(settings.DOCS_DIR, f))]
    return {"files": files, "count": len(files)}

@app.post("/upload")
async def upload_document(file: UploadFile = File(...)):
    safe_filename = os.path.basename(file.filename or "uploaded_doc")
    dest_path = os.path.join(settings.DOCS_DIR, safe_filename)
    try:
        with open(dest_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        logger.info(f"Uploaded file saved to {dest_path}")
        return {"filename": safe_filename, "status": "success", "path": dest_path}
    except Exception as e:
        logger.error(f"Failed to upload document: {e}")
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")

@app.delete("/documents/{filename}")
async def delete_document(filename: str):
    safe_filename = os.path.basename(filename)
    file_path = os.path.join(settings.DOCS_DIR, safe_filename)
    if os.path.exists(file_path):
        os.remove(file_path)
        logger.info(f"Deleted document {file_path}")
        return {"filename": safe_filename, "status": "deleted"}
    raise HTTPException(status_code=404, detail="File not found")

@app.post("/query", response_model=List[DocumentChunk])
async def query_documents(request: DocumentQueryRequest):
    logger.info(f"Vector search query: '{request.query}' in {settings.DOCS_DIR}")
    try:
        loader = DocumentLoader(settings.DOCS_DIR)
        pages = await loader.load()
        if not pages:
            return []
        
        # Ingest into memory embeddings
        memory = Memory(embedding_provider=os.getenv("EMBEDDING_PROVIDER", "openai"))
        vector_store = await memory.get_vector_store()
        vector_store.load(pages)
        
        results = await vector_store.similarity_search(request.query, k=request.top_k or 5)
        chunks = []
        for r in results:
            chunks.append(DocumentChunk(
                text=getattr(r, "page_content", str(r)),
                metadata=getattr(r, "metadata", {}),
                score=getattr(r, "score", None)
            ))
        return chunks
    except Exception as e:
        logger.error(f"Error querying documents: {e}")
        # Return fallback empty chunks on error
        return []

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("DOCUMENT_PORT", "8003"))
    uvicorn.run(app, host="0.0.0.0", port=port)
