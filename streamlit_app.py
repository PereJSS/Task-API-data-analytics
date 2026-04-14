import random
from datetime import datetime, timedelta
from typing import Dict, List

import pandas as pd
import plotly.express as px
import requests
import streamlit as st

from app.config import settings

API_BASE_URL = settings.streamlit_api_base_url


def _to_dataframe(tasks: List[Dict]) -> pd.DataFrame:
    if not tasks:
        return pd.DataFrame()

    df = pd.DataFrame(tasks)
    for col in ["created_at", "updated_at", "started_at", "completed_at"]:
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], errors="coerce")
    return df


def fetch_tasks_from_api(api_base_url: str, include_archived: bool = True) -> pd.DataFrame:
    all_tasks = []
    limit = 100
    offset = 0

    while True:
        response = requests.get(
            f"{api_base_url}/tasks",
            params={
                "include_archived": str(include_archived).lower(),
                "limit": limit,
                "offset": offset,
            },
            timeout=10,
        )
        response.raise_for_status()
        batch = response.json()
        all_tasks.extend(batch)

        if len(batch) < limit:
            break
        offset += limit

    return _to_dataframe(all_tasks)


@st.cache_data
def build_demo_dataframe(task_count: int = 1200, seed: int = 42) -> pd.DataFrame:
    random.seed(seed)
    now = datetime.utcnow()
    period_start = now - timedelta(days=365 * 3)

    creators = ["Ana", "Luis", "Marta", "Pere", "Carlos", "Nuria", "Elena", "Javier"]
    assignees = ["Equipo BI", "DataOps", "Analista 1", "Analista 2", "Product", "QA", "Infra"]
    prefixes = ["Implementar", "Revisar", "Automatizar", "Corregir", "Validar", "Optimizar"]
    subjects = ["pipeline", "informe", "dashboard", "ETL", "migracion", "alertas"]

    rows = []
    for i in range(task_count):
        created_at = period_start + timedelta(
            seconds=random.randint(0, int((now - period_start).total_seconds()))
        )
        status = random.choices(
            population=["completed", "in_progress", "pending", "blocked", "cancelled"],
            weights=[55, 18, 16, 7, 4],
            k=1,
        )[0]
        completed = status == "completed"
        archived = random.random() < 0.08

        started_at = None
        completed_at = None
        completion_time_minutes = None

        if status in {"completed", "in_progress", "blocked"}:
            started_at = created_at + timedelta(hours=random.randint(0, 72))

        if completed:
            if started_at is None:
                started_at = created_at
            completion_time_minutes = random.randint(30, 40 * 24 * 60)
            completed_at = started_at + timedelta(minutes=completion_time_minutes)
            if completed_at > now:
                completed_at = now - timedelta(minutes=random.randint(1, 120))
                completion_time_minutes = int((completed_at - started_at).total_seconds() // 60)
            if completion_time_minutes < 1:
                completion_time_minutes = 1

        updated_at = max(
            d
            for d in [created_at, started_at, completed_at]
            if d is not None
        )

        rows.append(
            {
                "id": f"demo-{i + 1}",
                "title": f"{random.choice(prefixes)} {random.choice(subjects)}",
                "description": "Tarea generada en modo demo para analitica",
                "created_by": random.choice(creators),
                "assigned_to": random.choice(assignees),
                "status": status,
                "completed": completed,
                "started_at": started_at,
                "completed_at": completed_at,
                "completion_time_minutes": completion_time_minutes,
                "archived": archived,
                "created_at": created_at,
                "updated_at": updated_at,
            }
        )

    return _to_dataframe(rows)


def filter_dataframe(
    df: pd.DataFrame,
    statuses: List[str],
    assignees: List[str],
    start_date,
    end_date,
) -> pd.DataFrame:
    filtered = df.copy()
    if statuses:
        filtered = filtered[filtered["status"].isin(statuses)]
    if assignees:
        filtered = filtered[filtered["assigned_to"].isin(assignees)]
    if start_date is not None and end_date is not None:
        created_dates = filtered["created_at"].dt.date
        filtered = filtered[(created_dates >= start_date) & (created_dates <= end_date)]
    return filtered


def stats_from_df(df: pd.DataFrame) -> Dict[str, float]:
    avg_minutes = df["completion_time_minutes"].dropna().mean()
    return {
        "total": int(df.shape[0]),
        "completed": int((df["status"] == "completed").sum()),
        "pending": int((df["status"] == "pending").sum()),
        "avg_completion_minutes": 0 if pd.isna(avg_minutes) else round(float(avg_minutes), 2),
    }


st.set_page_config(page_title="TaskFlow Analytics", layout="wide")
st.title("TaskFlow Analytics")
st.caption("Dashboard Streamlit con modo demo gratuito o conexion a API")

with st.sidebar:
    st.header("Configuracion")
    data_source = st.radio(
        "Fuente de datos",
        options=["Demo local (gratis)", "API remota"],
        index=0,
    )
    include_archived = st.checkbox("Incluir archivadas", value=True)
    api_url = st.text_input("API base URL", value=API_BASE_URL)

if data_source == "Demo local (gratis)":
    df = build_demo_dataframe()
    if not include_archived:
        df = df[df["archived"] == False]  # noqa: E712
else:
    try:
        df = fetch_tasks_from_api(api_url.rstrip("/"), include_archived=include_archived)
    except requests.RequestException as exc:
        st.error(f"No se pudo conectar con la API: {exc}")
        st.stop()

if df.empty:
    st.info("No hay tareas para mostrar")
    st.stop()

stats = stats_from_df(df)

col1, col2, col3, col4 = st.columns(4)
col1.metric("Total", stats.get("total", 0))
col2.metric("Completadas", stats.get("completed", 0))
col3.metric("Pendientes", stats.get("pending", 0))
col4.metric("Promedio min cierre", stats.get("avg_completion_minutes") or 0)

with st.sidebar:
    st.header("Filtros")
    status_options = sorted([s for s in df["status"].dropna().unique().tolist() if s])
    assignee_options = sorted([a for a in df["assigned_to"].dropna().unique().tolist() if a])
    selected_status = st.multiselect("Estado", options=status_options, default=[])
    selected_assignees = st.multiselect("Responsable", options=assignee_options, default=[])

    min_date = df["created_at"].min()
    max_date = df["created_at"].max()
    if pd.isna(min_date) or pd.isna(max_date):
        start_date = None
        end_date = None
    else:
        date_range = st.date_input(
            "Fecha de creacion",
            value=(min_date.date(), max_date.date()),
            min_value=min_date.date(),
            max_value=max_date.date(),
        )
        if isinstance(date_range, tuple) and len(date_range) == 2:
            start_date, end_date = date_range
        else:
            start_date = date_range
            end_date = date_range

filtered_df = filter_dataframe(
    df=df,
    statuses=selected_status,
    assignees=selected_assignees,
    start_date=start_date,
    end_date=end_date,
)

st.subheader("Resumen filtrado")
fcol1, fcol2, fcol3, fcol4 = st.columns(4)
fcol1.metric("Tareas filtradas", int(filtered_df.shape[0]))
fcol2.metric("Completadas", int((filtered_df["status"] == "completed").sum()))
fcol3.metric("Bloqueadas", int((filtered_df["status"] == "blocked").sum()))
fcol4.metric("Canceladas", int((filtered_df["status"] == "cancelled").sum()))

csv_bytes = filtered_df.to_csv(index=False).encode("utf-8")
st.download_button(
    label="Descargar CSV filtrado",
    data=csv_bytes,
    file_name="taskflow_filtered_tasks.csv",
    mime="text/csv",
)

left, right = st.columns(2)
with left:
    st.subheader("Tareas por estado")
    status_counts = filtered_df["status"].fillna("unknown").value_counts().reset_index()
    status_counts.columns = ["status", "count"]
    fig_status = px.bar(status_counts, x="status", y="count", color="status")
    st.plotly_chart(fig_status, use_container_width=True)

with right:
    st.subheader("Tiempo de cierre por responsable")
    close_times = filtered_df.dropna(subset=["assigned_to", "completion_time_minutes"])
    if close_times.empty:
        st.info("Aun no hay tiempos de cierre para analizar")
    else:
        agg = (
            close_times.groupby("assigned_to", as_index=False)["completion_time_minutes"]
            .mean()
            .sort_values("completion_time_minutes", ascending=False)
        )
        fig_time = px.bar(
            agg,
            x="assigned_to",
            y="completion_time_minutes",
            color="completion_time_minutes",
        )
        st.plotly_chart(fig_time, use_container_width=True)

st.subheader("Detalle de tareas")
st.dataframe(filtered_df, use_container_width=True)
