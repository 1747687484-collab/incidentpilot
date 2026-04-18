FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY incidentpilot ./incidentpilot

EXPOSE 9100
CMD ["python", "-m", "incidentpilot.main"]

