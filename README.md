# TaskFlow API

API REST para gestion de tareas con FastAPI, SQLAlchemy, SQLite y dashboard analitico en Streamlit.

## Resumen

El proyecto incluye:

- CRUD de tareas con soft delete.
- Estados operativos y metadatos utiles para analisis.
- Estadisticas agregadas para reporting.
- Dashboard en Streamlit con filtros y exportacion CSV.
- Script de seed para generar historico realista.
- Migraciones con Alembic.
- Tests automatizados y workflow de GitHub Actions.

## Stack

- Python 3.8+
- FastAPI
- SQLAlchemy 2.x
- Pydantic 2.x
- SQLite
- Streamlit
- Pytest

## Estructura

```text
.
├── .github/
│   └── workflows/
│       └── tests.yml
├── app/
│   ├── routers/
│   │   └── tasks.py
│   ├── config.py
│   ├── crud.py
│   ├── database.py
│   ├── main.py
│   ├── models.py
│   └── schemas.py
├── tests/
│   └── test_tasks_api.py
├── main.py
├── pyproject.toml
├── requirements.txt
├── seed_tasks.py
├── streamlit_app.py
└── README.md
```

## Configuracion

Variables soportadas:

- `TASKFLOW_DATABASE_URL`: URL de base de datos SQLite.
- `TASKFLOW_API_BASE_URL`: URL base que usara Streamlit para consultar la API.

Puedes partir de [.env.example](.env.example).

## Instalacion

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Comandos utiles:

```bash
make test
make api
make dashboard
make seed
make lint
```

## Ejecutar la API

```bash
uvicorn main:app --reload
```

URLs principales:

- API raiz: `http://127.0.0.1:8000/`
- Health: `http://127.0.0.1:8000/health`
- Swagger UI: `http://127.0.0.1:8000/docs`
- ReDoc: `http://127.0.0.1:8000/redoc`

## Ejecutar Streamlit

Con la API arrancada:

```bash
streamlit run streamlit_app.py
```

Dashboard en `http://127.0.0.1:8501`.

Incluye:

- Filtros por estado, responsable y fecha.
- Graficos para distribucion de estados y tiempos medios.
- Descarga CSV de los datos filtrados.

## Datos del modelo

Cada tarea puede incluir:

- `title`
- `description`
- `created_by`
- `assigned_to`
- `status`
- `completed`
- `started_at`
- `completed_at`
- `completion_time_minutes`
- `archived`

Estados permitidos:

- `pending`
- `in_progress`
- `blocked`
- `completed`
- `cancelled`

## Endpoints principales

- `GET /`
- `GET /health`
- `POST /tasks`
- `GET /tasks`
- `GET /tasks/{task_id}`
- `PUT /tasks/{task_id}`
- `DELETE /tasks/{task_id}`
- `GET /tasks/stats/summary`

Ejemplo de filtros:

```bash
curl "http://127.0.0.1:8000/tasks?completed=false&status=blocked&assigned_to=data&search=etl&limit=10&offset=0"
```

## Seed de datos historicos

Para cargar 700 tareas aleatorias con historico de 3 anos:

```bash
python seed_tasks.py
```

El seed genera:

- usuarios creadores y responsables variados
- tareas completadas, bloqueadas, canceladas y en progreso
- fechas distribuidas en el tiempo
- tiempos de resolucion para tareas completadas

## Migraciones

Migrar la base a la ultima revision:

```bash
make upgrade
```

Crear una nueva migracion autogenerada:

```bash
make migrate MSG="describe el cambio"
```

## Tests

```bash
pytest -q
```

## Preparado para GitHub

El proyecto ya incluye:

- `.gitignore` adecuado para Python, SQLite y Streamlit
- `pyproject.toml` con configuracion base de pytest y Ruff
- `Makefile` con comandos frecuentes de desarrollo
- configuracion de Alembic lista para migraciones
- workflow de CI en `.github/workflows/tests.yml`
- documentacion lista para repositorio publico

## Siguientes mejoras razonables

- Migraciones reales con Alembic
- Docker para API y dashboard
- Autenticacion y control de acceso
- Exportacion Excel o Parquet
