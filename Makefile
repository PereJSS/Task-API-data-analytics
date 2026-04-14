PYTHON=.venv/bin/python
PIP=.venv/bin/pip

.PHONY: install api dashboard test lint seed migrate upgrade downgrade compose-up compose-down

install:
	$(PIP) install -r requirements.txt

api:
	$(PYTHON) -m uvicorn main:app --reload

dashboard:
	$(PYTHON) -m streamlit run streamlit_app.py

test:
	$(PYTHON) -m pytest -q

lint:
	$(PYTHON) -m ruff check .

seed:
	$(PYTHON) seed_tasks.py

migrate:
	$(PYTHON) -m alembic revision --autogenerate -m "$(MSG)"

upgrade:
	$(PYTHON) -m alembic upgrade head

downgrade:
	$(PYTHON) -m alembic downgrade -1

compose-up:
	docker compose up --build

compose-down:
	docker compose down