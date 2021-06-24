FROM python:3.9-slim

ENV PYTHONUNBUFFERED=1

WORKDIR /usr/src/app

COPY . .

ENTRYPOINT ["/usr/src/app/get_metrics_from_prom.py"]
