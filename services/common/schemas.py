from typing import Dict, List, Any, Optional
from pydantic import BaseModel, Field
from enum import Enum
import time

class ToneEnum(str, Enum):
    objective = "Objective"
    formal = "Formal"
    analytical = "Analytical"
    persuasive = "Persuasive"
    informative = "Informative"
    explanatory = "Explanatory"
    descriptive = "Descriptive"
    critical = "Critical"
    comparative = "Comparative"
    speculative = "Speculative"
    authoritative = "Authoritative"
    conversational = "Conversational"

class ReportTypeEnum(str, Enum):
    research_report = "research_report"
    detailed_report = "detailed_report"
    resource_report = "resource_report"
    outline_report = "outline_report"
    custom_report = "custom_report"
    subtopic_report = "subtopic_report"

class ResearchRequest(BaseModel):
    task: str = Field(..., description="The research question or topic")
    report_type: str = Field(default="research_report", description="Report format/style")
    report_source: str = Field(default="web", description="'web', 'local', or 'hybrid'")
    tone: str = Field(default="Objective", description="Tone of the research report")
    headers: Optional[Dict[str, Any]] = None
    repo_name: Optional[str] = ""
    branch_name: Optional[str] = ""
    generate_in_background: bool = True
    session_id: Optional[str] = None
    max_subtopics: Optional[int] = 5

class ResearchEvent(BaseModel):
    type: str = Field(default="logs", description="e.g. 'logs', 'source', 'path', 'report'")
    content: Any = Field(default="", description="Payload data or status message")
    output: Any = Field(default="", description="The output text/html/payload")
    timestamp: float = Field(default_factory=time.time)
    metadata: Optional[Any] = None

class ScrapeTask(BaseModel):
    url: str = Field(..., description="Target URL to scrape")
    scraper_type: Optional[str] = Field(default="bs4", description="bs4, playwright, selenium, web_base_loader")
    max_length: Optional[int] = 10000

class ScrapeResult(BaseModel):
    url: str
    title: Optional[str] = ""
    content: str
    status: str = "success"
    error: Optional[str] = None

class SearchQuery(BaseModel):
    query: str
    retriever: Optional[str] = "tavily"
    max_results: Optional[int] = 8

class SearchResultItem(BaseModel):
    title: str
    url: str
    content: str
    raw_content: Optional[str] = None
    score: Optional[float] = None

class SearchResponse(BaseModel):
    query: str
    retriever: str
    results: List[SearchResultItem] = []

class DocumentIngestRequest(BaseModel):
    filename: str
    content_base64: Optional[str] = None
    content_text: Optional[str] = None
    collection_name: Optional[str] = "default"

class DocumentQueryRequest(BaseModel):
    query: str
    collection_name: Optional[str] = "default"
    top_k: Optional[int] = 5

class DocumentChunk(BaseModel):
    text: str
    metadata: Dict[str, Any] = {}
    score: Optional[float] = None

class ExportFormat(str, Enum):
    pdf = "pdf"
    docx = "docx"
    markdown = "markdown"

class ExportRequest(BaseModel):
    report_markdown: str
    title: Optional[str] = "Research Report"
    format: ExportFormat = ExportFormat.pdf
    include_images: bool = True

class ExportResponse(BaseModel):
    file_path: str
    file_name: str
    download_url: str
    format: str

class ChatMessage(BaseModel):
    role: str
    content: str

class ChatRequest(BaseModel):
    report: str
    messages: List[ChatMessage]
