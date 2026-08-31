import pytest
from fastapi.testclient import TestClient
from services.common.schemas import (
    ResearchRequest, ScrapeTask, SearchQuery, DocumentQueryRequest,
    ExportRequest, ExportFormat, ResearchEvent
)
from services.scraper_service.main import app as scraper_app
from services.export_service.main import app as export_app
from services.document_service.main import app as doc_app
from services.research_orchestrator.main import app as orchestrator_app
from services.api_gateway.main import app as gateway_app

def test_scraper_health():
    client = TestClient(scraper_app)
    res = client.get("/health")
    assert res.status_code == 200
    assert res.json()["status"] == "ok"

def test_export_health():
    client = TestClient(export_app)
    res = client.get("/health")
    assert res.status_code == 200
    assert res.json()["status"] == "ok"

def test_document_health():
    client = TestClient(doc_app)
    res = client.get("/health")
    assert res.status_code == 200
    assert res.json()["status"] == "ok"

def test_orchestrator_health():
    client = TestClient(orchestrator_app)
    res = client.get("/health")
    assert res.status_code == 200
    assert res.json()["status"] == "ok"

def test_gateway_health():
    client = TestClient(gateway_app)
    res = client.get("/health")
    assert res.status_code == 200
    assert res.json()["status"] == "ok"

def test_export_markdown():
    client = TestClient(export_app)
    req = ExportRequest(
        report_markdown="# Test Report\n\nThis is a test summary.",
        title="Microservices Test Report",
        format=ExportFormat.markdown
    )
    res = client.post("/export", json=req.model_dump())
    assert res.status_code == 200
    data = res.json()
    assert data["format"] == "markdown"
    assert "Microservices_Test_Report" in data["file_name"]

def test_schemas_validation():
    req = ResearchRequest(task="Quantum Computing breakthroughs")
    assert req.task == "Quantum Computing breakthroughs"
    assert req.report_type == "research_report"
    assert req.tone == "Objective"

    event = ResearchEvent(event_type="logs", content="Processing subtopics...")
    assert event.event_type == "logs"
    assert event.content == "Processing subtopics..."
