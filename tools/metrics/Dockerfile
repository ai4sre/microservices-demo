FROM python:3.9

RUN mkdir /work
COPY ./ /work
WORKDIR /work

ENTRYPOINT ["/work/get_metrics_from_prom.py"]
