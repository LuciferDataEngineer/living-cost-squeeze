.PHONY: install snapshot pipeline dashboard lint test sqlmesh-test lakefs argo ci

export PATH := $(HOME)/.local/bin:$(PATH)
export PYTHONPATH := src

install:
	python3 -m pip install -r requirements.txt

snapshot:
	python3 scripts/refresh_snapshot.py

pipeline:
	python3 -m squeeze.cli run

dashboard:
	python3 -m squeeze.cli dashboard

lint:
	python3 -m ruff check src tests scripts

sqlmesh-test:
	sqlmesh test --local

test:
	python3 -m pytest -q

lakefs:
	docker compose up -d minio createbucket lakefs
	python3 -m pytest -q -m lakefs

argo:
	bash scripts/run_kind.sh

ci: lint sqlmesh-test pipeline test
