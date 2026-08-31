FROM python:3.11-slim

WORKDIR /usr/src/app

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./
COPY services/api_gateway/requirements.txt ./service_req.txt
RUN pip install --no-cache-dir -r requirements.txt -r service_req.txt

COPY frontend ./frontend
COPY services ./services

ENV PYTHONUNBUFFERED=1
EXPOSE 8000

CMD ["python", "services/api_gateway/main.py"]
