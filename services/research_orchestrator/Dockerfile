FROM python:3.11-slim

WORKDIR /usr/src/app

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./
COPY services/research_orchestrator/requirements.txt ./service_req.txt
RUN pip install --no-cache-dir -r requirements.txt -r service_req.txt

COPY gpt_researcher ./gpt_researcher
COPY multi_agents ./multi_agents
COPY services ./services

ENV PYTHONUNBUFFERED=1
EXPOSE 8001

CMD ["python", "services/research_orchestrator/main.py"]
