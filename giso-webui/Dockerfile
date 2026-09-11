FROM python:3.12-alpine

RUN apk add --no-cache docker-cli
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && pip install --no-cache-dir -r requirements.txt
COPY app.py .
COPY templates templates
COPY static static
EXPOSE 8080
HEALTHCHECK --interval=15s --timeout=3s CMD wget -qO- http://127.0.0.1:8080/api/health || exit 1
CMD ["gunicorn", "--workers", "1", "--threads", "8", "--timeout", "0", "--bind", "0.0.0.0:8080", "app:app"]
