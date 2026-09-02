FROM python:3.11-slim

WORKDIR /usr/src/app

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./
COPY services/writer_service/requirements.txt ./services/writer_service/
RUN pip install --no-cache-dir -r requirements.txt -r services/writer_service/requirements.txt

COPY gpt_researcher ./gpt_researcher
COPY services ./services

EXPOSE 8014

CMD ["python", "services/writer_service/main.py"]
