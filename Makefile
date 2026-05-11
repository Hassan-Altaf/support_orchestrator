.PHONY: install run test test-fast lint format typecheck demo demo-mock eval docker-build docker-run ci clean help

help:
	@echo "Targets:"
	@echo "  install      Install package + dev deps and pre-commit hooks"
	@echo "  run          Run FastAPI dev server on :8000 (auto-reload)"
	@echo "  test         Run pytest with coverage (HTML + terminal)"
	@echo "  test-fast    Run pytest without coverage"
	@echo "  lint         ruff lint (no fixes)"
	@echo "  format       ruff format"
	@echo "  typecheck    mypy app"
	@echo "  demo         Run scripts/demo.py against real LLM provider"
	@echo "  demo-mock    Run scripts/demo.py with MockProvider (no API key)"
	@echo "  eval         Run scripts/eval.py and write samples/eval_report.md"
	@echo "  docker-build Build local Docker image"
	@echo "  docker-run   docker compose up --build"
	@echo "  ci           lint + typecheck + test (matches GitHub Actions)"
	@echo "  clean        Remove caches and build artifacts"

install:
	pip install -e ".[dev]"
	pre-commit install

run:
	uvicorn app.main:app --reload --port 8000

test:
	pytest -v --cov=app --cov-report=term-missing --cov-report=html

test-fast:
	pytest -v

lint:
	ruff check app tests scripts

format:
	ruff format app tests scripts

typecheck:
	mypy app

demo:
	python scripts/demo.py

demo-mock:
	python scripts/demo.py --mock

eval:
	python scripts/eval.py

docker-build:
	docker build -t support-orchestrator:latest .

docker-run:
	docker compose up --build

ci: lint typecheck test

clean:
	@python -c "import pathlib, shutil, glob, os; \
[shutil.rmtree(p, ignore_errors=True) for p in pathlib.Path('.').rglob('__pycache__')]; \
[shutil.rmtree(p, ignore_errors=True) for p in ['.pytest_cache','.mypy_cache','.ruff_cache','htmlcov','build','dist']]; \
[shutil.rmtree(p, ignore_errors=True) for p in glob.glob('*.egg-info')]; \
[os.remove(p) for p in ['.coverage','coverage.xml'] if os.path.exists(p)]; \
print('cleaned caches, build artifacts, and coverage files')"
