FROM python:3.11-slim

WORKDIR /usr/src/app

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl build-essential libnss3 libatk1.0-0 libatk-bridge2.0-0 libcups2 libdrm2 \
    libxkbcommon0 libxcomposite1 libxdamage1 libxfixes3 libxrandr2 libgbm1 libasound2 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./
COPY services/scraper_service/requirements.txt ./service_req.txt
RUN pip install --no-cache-dir -r requirements.txt -r service_req.txt

COPY gpt_researcher ./gpt_researcher
COPY services ./services

ENV PYTHONUNBUFFERED=1
EXPOSE 8002

CMD ["python", "services/scraper_service/main.py"]
