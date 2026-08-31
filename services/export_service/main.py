import os
import sys
import logging
import urllib.parse
import re
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

# Ensure project root is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from services.common.schemas import ExportRequest, ExportResponse, ExportFormat
from services.common.config import settings

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger("export_service")

app = FastAPI(title="GPT Researcher - Export Microservice", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

os.makedirs(settings.OUTPUTS_DIR, exist_ok=True)
app.mount("/outputs", StaticFiles(directory=settings.OUTPUTS_DIR), name="outputs")

def _sanitize_filename(name: str) -> str:
    cleaned = re.sub(r'[^a-zA-Z0-9_\- ]', '', name).strip().replace(" ", "_")
    return cleaned[:50] or "research_report"

def _preprocess_images_for_pdf(text: str) -> str:
    base_path = os.path.abspath(".")
    def replace_image_url(match):
        alt_text = match.group(1)
        url = match.group(2)
        if url.startswith("/outputs/"):
            abs_path = os.path.join(base_path, url.lstrip("/"))
            return f"![{alt_text}]({abs_path})"
        return match.group(0)
    pattern = r'!\[([^\]]*)\]\((/outputs/[^)]+)\)'
    return re.sub(pattern, replace_image_url, text)

@app.get("/health")
async def health_check():
    return {"status": "ok", "service": "export-service"}

@app.post("/export", response_model=ExportResponse)
async def export_document(request: ExportRequest):
    safe_name = _sanitize_filename(request.title)
    
    if request.format == ExportFormat.markdown:
        filename = f"{safe_name}.md"
        file_path = os.path.join(settings.OUTPUTS_DIR, filename)
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(request.report_markdown)
        return ExportResponse(
            file_path=file_path,
            file_name=filename,
            download_url=f"/outputs/{filename}",
            format="markdown"
        )
        
    elif request.format == ExportFormat.docx:
        filename = f"{safe_name}.docx"
        file_path = os.path.join(settings.OUTPUTS_DIR, filename)
        try:
            import mistune
            from docx import Document
            from htmldocx import HtmlToDocx
            html = mistune.html(request.report_markdown)
            doc = Document()
            HtmlToDocx().add_html_to_document(html, doc)
            doc.save(file_path)
            return ExportResponse(
                file_path=file_path,
                file_name=filename,
                download_url=f"/outputs/{filename}",
                format="docx"
            )
        except Exception as e:
            logger.error(f"Error generating DOCX: {e}")
            raise HTTPException(status_code=500, detail=f"DOCX generation failed: {str(e)}")

    elif request.format == ExportFormat.pdf:
        filename = f"{safe_name}.pdf"
        file_path = os.path.join(settings.OUTPUTS_DIR, filename)
        try:
            import markdown
            from weasyprint import HTML, CSS
            css_path = os.path.join(os.path.dirname(__file__), "styles", "pdf_styles.css")
            processed_text = _preprocess_images_for_pdf(request.report_markdown)
            html_body = markdown.markdown(processed_text, extensions=['tables', 'fenced_code'])
            full_html = f"<html><head><meta charset='utf-8'></head><body>{html_body}</body></html>"
            stylesheets = [CSS(filename=css_path)] if os.path.exists(css_path) else []
            HTML(string=full_html, base_url=os.path.abspath(".")).write_pdf(file_path, stylesheets=stylesheets)
            return ExportResponse(
                file_path=file_path,
                file_name=filename,
                download_url=f"/outputs/{filename}",
                format="pdf"
            )
        except Exception as e:
            logger.error(f"Error generating PDF: {e}")
            raise HTTPException(status_code=500, detail=f"PDF generation failed: {str(e)}")

    else:
        raise HTTPException(status_code=400, detail=f"Unsupported format: {request.format}")

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("EXPORT_PORT", "8004"))
    uvicorn.run(app, host="0.0.0.0", port=port)
