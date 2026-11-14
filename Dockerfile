# CaseForge website with Chromium for the designed-report PDFs.
# The Playwright image already contains Chromium and its system libraries.
FROM mcr.microsoft.com/playwright/python:v1.63.0-noble

WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .

# Render sets $PORT; 8000 for local `docker run -p 8000:8000`
CMD uvicorn web.main:app --host 0.0.0.0 --port ${PORT:-8000} --proxy-headers --forwarded-allow-ips="*"
