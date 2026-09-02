import os
import pytest
import httpx
from services.common.schemas import ExportRequest, ExportFormat, ResearchRequest

GATEWAY_URL = os.getenv("GATEWAY_URL", "http://api-gateway:8000")
ORCHESTRATOR_URL = os.getenv("ORCHESTRATOR_URL", "http://research-orchestrator:8001")
SCRAPER_URL = os.getenv("SCRAPER_URL", "http://scraper-service:8002")
DOCUMENT_URL = os.getenv("DOCUMENT_URL", "http://document-service:8003")
EXPORT_URL = os.getenv("EXPORT_URL", "http://export-service:8004")

@pytest.mark.asyncio
async def test_live_gateway_health():
    async with httpx.AsyncClient(timeout=5.0) as client:
        res = await client.get(f"{GATEWAY_URL}/health")
        assert res.status_code == 200
        data = res.json()
        assert data["status"] == "ok"
        assert data["service"] == "api-gateway"

@pytest.mark.asyncio
async def test_live_scraper_health():
    async with httpx.AsyncClient(timeout=5.0) as client:
        res = await client.get(f"{SCRAPER_URL}/health")
        assert res.status_code == 200
        assert res.json()["status"] == "ok"

@pytest.mark.asyncio
async def test_live_export_health():
    async with httpx.AsyncClient(timeout=5.0) as client:
        res = await client.get(f"{EXPORT_URL}/health")
        assert res.status_code == 200
        assert res.json()["status"] == "ok"

@pytest.mark.asyncio
async def test_live_document_health():
    async with httpx.AsyncClient(timeout=5.0) as client:
        res = await client.get(f"{DOCUMENT_URL}/health")
        assert res.status_code == 200
        assert res.json()["status"] == "ok"

@pytest.mark.asyncio
async def test_live_orchestrator_health():
    async with httpx.AsyncClient(timeout=5.0) as client:
        res = await client.get(f"{ORCHESTRATOR_URL}/health")
        assert res.status_code == 200
        assert res.json()["status"] == "ok"

@pytest.mark.asyncio
async def test_live_export_pipeline():
    async with httpx.AsyncClient(timeout=10.0) as client:
        payload = {
            "report_markdown": "# Container Test Report\n\nGenerated inside Docker container composition.",
            "title": "Container_Composition_Test",
            "format": "markdown"
        }
        res = await client.post(f"{EXPORT_URL}/export", json=payload)
        assert res.status_code == 200
        data = res.json()
        assert data["format"] == "markdown"
        assert "Container_Composition_Test" in data["file_name"]
