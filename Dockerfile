FROM python:3.12-slim

WORKDIR /opt/squeeze
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY config.yaml pyproject.toml ./
COPY src src
COPY models models
COPY tests/test_household_gap.yaml tests/test_household_gap.yaml
COPY data/snapshot data/snapshot
COPY data/manifest.json data/manifest.json
ENV PYTHONPATH=/opt/squeeze/src
ENV PYTHONUNBUFFERED=1
