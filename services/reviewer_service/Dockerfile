FROM python:3.11-slim

WORKDIR /usr/src/app

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./
COPY services/reviewer_service/requirements.txt ./services/reviewer_service/
RUN pip install --no-cache-dir -r requirements.txt -r services/reviewer_service/requirements.txt

COPY gpt_researcher ./gpt_researcher
COPY services ./services

EXPOSE 8013

CMD ["python", "services/reviewer_service/main.py"]
