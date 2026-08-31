FROM python:3.11-slim

WORKDIR /usr/src/app

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./
COPY services/document_service/requirements.txt ./service_req.txt
RUN pip install --no-cache-dir -r requirements.txt -r service_req.txt

COPY gpt_researcher ./gpt_researcher
COPY services ./services

ENV PYTHONUNBUFFERED=1
EXPOSE 8003

CMD ["python", "services/document_service/main.py"]
