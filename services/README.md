# GPT Researcher Microservices Architecture

This directory contains the microservices decomposition of GPT Researcher.

## Architecture

The monolith has been separated into isolated services coordinated via the **API Gateway** and an **Event Bus (Redis Pub/Sub)**:

```
                  ┌───────────────────────┐
                  │ Next.js Frontend / UI │
                  └──────────┬────────────┘
                             │ HTTP / WebSocket
                             ▼
                  ┌───────────────────────┐
                  │      API Gateway      │ (:8000)
                  └──────────┬────────────┘
                             │
     ┌───────────────────────┼───────────────────────┐
     ▼                       ▼                       ▼
┌─────────────┐       ┌─────────────┐       ┌─────────────┐
│  Scraper &  │       │  Research   │       │  Document   │
│  Retriever  │       │Orchestrator │       │  & Vector   │
│  Service    │       │   Service   │       │   Service   │
│  (:8002)    │       │   (:8001)   │       │   (:8003)   │
└─────────────┘       └──────┬──────┘       └─────────────┘
                             │
                      ┌──────┴──────┐
                      │   Export    │
                      │   Service   │
                      │   (:8004)   │
                      └─────────────┘
```

## Services Summary

| Service | Port | Description |
|---|---|---|
| **`api_gateway`** | `8000` | Client entry point, WebSocket relay, auth & routing proxy |
| **`research_orchestrator`** | `8001` | Coordinates LangGraph/Multi-agents, planning & report synthesis |
| **`scraper_service`** | `8002` | Headless Playwright / BS4 scraping and search retriever integrations |
| **`document_service`** | `8003` | Local doc parsing (PDF, DOCX, CSV, TXT) and vector similarity search |
| **`export_service`** | `8004` | PDF (WeasyPrint), Word (DOCX), and Markdown document generator |
| **`common`** | - | Shared Pydantic data schemas, settings, and Redis Pub/Sub client |

## Running with Docker Compose

To launch the full microservices stack:

```bash
docker compose -f docker-compose.microservices.yml up --build
```

Access the services:
- **Web UI**: [http://localhost:3000](http://localhost:3000)
- **API Gateway Docs**: [http://localhost:8000/docs](http://localhost:8000/docs)
- **Research Orchestrator**: [http://localhost:8001/docs](http://localhost:8001/docs)
- **Scraper Service**: [http://localhost:8002/docs](http://localhost:8002/docs)
- **Document Service**: [http://localhost:8003/docs](http://localhost:8003/docs)
- **Export Service**: [http://localhost:8004/docs](http://localhost:8004/docs)

## Running Services Individually (Local Development)

```bash
# 1. API Gateway
python services/api_gateway/main.py

# 2. Research Orchestrator
python services/research_orchestrator/main.py

# 3. Scraper Service
python services/scraper_service/main.py

# 4. Document Service
python services/document_service/main.py

# 5. Export Service
python services/export_service/main.py
```
