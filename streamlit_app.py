import pandas as pd
import plotly.express as px
import requests
import streamlit as st

from app.config import settings

API_BASE_URL = settings.streamlit_api_base_url


def fetch_tasks(include_archived: bool = True) -> list:
    all_tasks = []
    limit = 100
    offset = 0

    while True:
        response = requests.get(
            f"{API_BASE_URL}/tasks",
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

    return all_tasks


def fetch_stats() -> dict:
    response = requests.get(f"{API_BASE_URL}/tasks/stats/summary", timeout=10)
    response.raise_for_status()
    return response.json()


def to_dataframe(tasks: list) -> pd.DataFrame:
    if not tasks:
        return pd.DataFrame()

    df = pd.DataFrame(tasks)
    for col in ["created_at", "updated_at", "started_at", "completed_at"]:
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], errors="coerce")

    return df


def filter_dataframe(
    df: pd.DataFrame,
    statuses: list,
    assignees: list,
    start_date,
    end_date,
) -> pd.DataFrame:
    filtered = df.copy()

    if statuses:
        filtered = filtered[filtered["status"].isin(statuses)]

    if assignees:
        filtered = filtered[filtered["assigned_to"].isin(assignees)]

    if start_date is not None and end_date is not None and "created_at" in filtered.columns:
        created_dates = filtered["created_at"].dt.date
        filtered = filtered[(created_dates >= start_date) & (created_dates <= end_date)]

    return filtered


st.set_page_config(page_title="TaskFlow Analytics", layout="wide")
st.title("TaskFlow Analytics")
st.caption("Dashboard Streamlit sobre la API de tareas")

with st.sidebar:
    st.header("Configuracion")
    api_url = st.text_input("API base URL", value=API_BASE_URL)
    include_archived = st.checkbox("Incluir archivadas", value=True)

if api_url != API_BASE_URL:
    API_BASE_URL = api_url.rstrip("/")

try:
    tasks = fetch_tasks(include_archived=include_archived)
    stats = fetch_stats()
except requests.RequestException as exc:
    st.error(f"No se pudo conectar con la API: {exc}")
    st.stop()

col1, col2, col3, col4 = st.columns(4)
col1.metric("Total", stats.get("total", 0))
col2.metric("Completadas", stats.get("completed", 0))
col3.metric("Pendientes", stats.get("pending", 0))
col4.metric("Promedio min cierre", stats.get("avg_completion_minutes") or 0)

df = to_dataframe(tasks)

if df.empty:
    st.info("No hay tareas para mostrar")
    st.stop()

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
