FROM python:3.11-slim

WORKDIR /usr/src/app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential curl libpango-1.0-0 libharfbuzz0b libpangoft2-1.0-0 libffi-dev \
    fonts-liberation \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./
COPY services/export_service/requirements.txt ./service_req.txt
RUN pip install --no-cache-dir -r requirements.txt -r service_req.txt

COPY gpt_researcher ./gpt_researcher
COPY services ./services

ENV PYTHONUNBUFFERED=1
EXPOSE 8004

CMD ["python", "services/export_service/main.py"]
