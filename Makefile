.PHONY: install dev test lint format type-check ui demo clean

install:
	pip install -e .

dev:
	pip install -e ".[dev]"

test:
	pytest tests/ -v --tb=short

test-cov:
	pytest tests/ -v --cov=src --cov-report=term-missing --cov-report=html

lint:
	ruff check src/ tests/

format:
	ruff format src/ tests/

type-check:
	mypy src/

ui:
	streamlit run src/viz/app.py

demo:
	python -m examples.demo

swiss-demo:
	python -m src.cli swiss --teams 8 --rounds 5

rr-demo:
	python -m src.cli round-robin --teams 6

elim-demo:
	python -m src.cli elimination --teams 8

bp-demo:
	python -m src.cli bp --teams 16 --rounds 5

docker-build:
	docker build -t tournament-system .

docker-run:
	docker run -p 8501:8501 tournament-system

clean:
	rm -rf __pycache__ .pytest_cache .mypy_cache .ruff_cache htmlcov dist build *.egg-info
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
