.PHONY: install backend frontend test lint up down

install:        ## Install backend (venv) and frontend deps
	cd backend && python3 -m venv .venv && . .venv/bin/activate && pip install -e ".[dev]"
	cd frontend && npm install

backend:        ## Run the FastAPI backend (http://localhost:8000)
	cd backend && . .venv/bin/activate && uvicorn app.main:app --reload --port 8000

frontend:       ## Run the Vite dev server (http://localhost:5173)
	cd frontend && npm run dev

test:           ## Run backend tests
	cd backend && . .venv/bin/activate && pytest

lint:           ## Lint backend
	cd backend && . .venv/bin/activate && ruff check app tests

up:             ## Build & run the full stack in Docker (http://localhost:8080)
	docker compose up --build

down:
	docker compose down -v
