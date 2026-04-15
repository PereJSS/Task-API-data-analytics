import random
from datetime import datetime, timedelta
from typing import Dict, List

import pandas as pd
import plotly.express as px
import requests
import streamlit as st

from app.config import settings

API_BASE_URL = settings.streamlit_api_base_url
STATUS_ORDER = ["pending", "in_progress", "blocked", "completed", "cancelled"]
PALETTE = {
    "pending": "#e9c46a",
    "in_progress": "#3a86ff",
    "blocked": "#e76f51",
    "completed": "#2a9d8f",
    "cancelled": "#6c757d",
}


def inject_styles() -> None:
    st.markdown(
        """
        <style>
        .stApp {
            background:
                radial-gradient(circle at top left, rgba(42,157,143,0.14), transparent 32%),
                radial-gradient(circle at top right, rgba(58,134,255,0.14), transparent 28%),
                linear-gradient(180deg, #f5f1e8 0%, #f8fafc 42%, #eef5f3 100%);
        }
        .hero-card {
            background: rgba(255, 255, 255, 0.72);
            border: 1px solid rgba(27, 67, 50, 0.08);
            border-radius: 22px;
            padding: 1.4rem 1.6rem;
            box-shadow: 0 18px 50px rgba(39, 76, 119, 0.08);
            backdrop-filter: blur(10px);
            margin-bottom: 1rem;
        }
        .insight-grid {
            display: grid;
            grid-template-columns: repeat(3, minmax(0, 1fr));
            gap: 0.8rem;
            margin: 0.8rem 0 1rem 0;
        }
        .insight-card {
            background: rgba(255,255,255,0.78);
            border-radius: 18px;
            padding: 0.9rem 1rem;
            border: 1px solid rgba(20, 33, 61, 0.06);
        }
        .insight-label {
            font-size: 0.8rem;
            color: #5c677d;
            text-transform: uppercase;
            letter-spacing: 0.06em;
        }
        .insight-value {
            font-size: 1.15rem;
            color: #14213d;
            font-weight: 700;
            margin-top: 0.25rem;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def _to_dataframe(tasks: List[Dict]) -> pd.DataFrame:
    if not tasks:
        return pd.DataFrame()

    df = pd.DataFrame(tasks)
    for col in ["created_at", "updated_at", "started_at", "completed_at"]:
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], errors="coerce")
    df["completion_time_minutes"] = pd.to_numeric(
        df.get("completion_time_minutes"), errors="coerce"
    )
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
    assignees = [
        "Equipo BI",
        "DataOps",
        "Analista 1",
        "Analista 2",
        "Product",
        "QA",
        "Infra",
        "Growth",
    ]
    prefixes = ["Implementar", "Revisar", "Automatizar", "Corregir", "Validar", "Optimizar"]
    subjects = ["pipeline", "informe", "dashboard", "ETL", "migracion", "alertas"]

    rows = []
    for index in range(task_count):
        created_at = period_start + timedelta(
            seconds=random.randint(0, int((now - period_start).total_seconds()))
        )
        status = random.choices(
            population=STATUS_ORDER,
            weights=[16, 18, 7, 55, 4],
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
            started_at = started_at or created_at
            completion_time_minutes = random.randint(30, 40 * 24 * 60)
            completed_at = started_at + timedelta(minutes=completion_time_minutes)
            if completed_at > now:
                completed_at = now - timedelta(minutes=random.randint(1, 120))
                completion_time_minutes = max(
                    int((completed_at - started_at).total_seconds() // 60),
                    1,
                )

        updated_at = max([date for date in [created_at, started_at, completed_at] if date is not None])
        rows.append(
            {
                "id": f"demo-{index + 1}",
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


def enrich_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    enriched = df.copy()
    enriched["status"] = pd.Categorical(
        enriched["status"], categories=STATUS_ORDER, ordered=True
    )
    enriched["created_month"] = enriched["created_at"].dt.to_period("M").astype(str)
    enriched["created_quarter"] = enriched["created_at"].dt.to_period("Q").astype(str)
    enriched["created_weekday"] = enriched["created_at"].dt.day_name()
    enriched["completion_bucket"] = pd.cut(
        enriched["completion_time_minutes"],
        bins=[0, 240, 1440, 4320, 10080, 100000],
        labels=["<4h", "4h-1d", "1d-3d", "3d-7d", ">7d"],
        include_lowest=True,
    )
    return enriched


def filter_dataframe(
    df: pd.DataFrame,
    statuses: List[str],
    assignees: List[str],
    creators: List[str],
    title_query: str,
    start_date,
    end_date,
    resolution_range: List[int],
) -> pd.DataFrame:
    filtered = df.copy()
    if statuses:
        filtered = filtered[filtered["status"].isin(statuses)]
    if assignees:
        filtered = filtered[filtered["assigned_to"].isin(assignees)]
    if creators:
        filtered = filtered[filtered["created_by"].isin(creators)]
    if title_query:
        filtered = filtered[
            filtered["title"].str.contains(title_query, case=False, na=False)
            | filtered["description"].str.contains(title_query, case=False, na=False)
        ]
    if start_date is not None and end_date is not None:
        created_dates = filtered["created_at"].dt.date
        filtered = filtered[(created_dates >= start_date) & (created_dates <= end_date)]
    if resolution_range:
        min_minutes, max_minutes = resolution_range
        time_series = filtered["completion_time_minutes"].fillna(-1)
        filtered = filtered[
            time_series.eq(-1) | ((time_series >= min_minutes) & (time_series <= max_minutes))
        ]
    return filtered


def stats_from_df(df: pd.DataFrame) -> Dict[str, float]:
    avg_minutes = df["completion_time_minutes"].dropna().mean()
    completion_rate = 0 if df.empty else round(float((df["status"] == "completed").mean() * 100), 1)
    return {
        "total": int(df.shape[0]),
        "completed": int((df["status"] == "completed").sum()),
        "pending": int((df["status"] == "pending").sum()),
        "avg_completion_minutes": 0 if pd.isna(avg_minutes) else round(float(avg_minutes), 2),
        "completion_rate": completion_rate,
    }


def render_insights(df: pd.DataFrame) -> None:
    blocked_share = 0 if df.empty else round(float((df["status"] == "blocked").mean() * 100), 1)
    busiest_assignee = (
        df["assigned_to"].value_counts().index[0] if not df["assigned_to"].dropna().empty else "N/A"
    )
    completed_df = df.dropna(subset=["completion_time_minutes", "assigned_to"])
    slowest_assignee = "N/A"
    if not completed_df.empty:
        slowest_assignee = (
            completed_df.groupby("assigned_to")["completion_time_minutes"].mean().sort_values(ascending=False).index[0]
        )

    st.markdown(
        f"""
        <div class="insight-grid">
          <div class="insight-card">
            <div class="insight-label">Responsable con mas carga</div>
            <div class="insight-value">{busiest_assignee}</div>
          </div>
          <div class="insight-card">
            <div class="insight-label">Responsable mas lento</div>
            <div class="insight-value">{slowest_assignee}</div>
          </div>
          <div class="insight-card">
            <div class="insight-label">Peso de bloqueos</div>
            <div class="insight-value">{blocked_share}%</div>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


inject_styles()
st.set_page_config(page_title="TaskFlow Analytics", layout="wide")
st.markdown(
    """
    <div class="hero-card">
      <div style="font-size:0.8rem; letter-spacing:0.08em; color:#5c677d; text-transform:uppercase;">Operations Intelligence</div>
      <div style="font-size:2.2rem; font-weight:800; color:#1d3557; margin-top:0.2rem;">TaskFlow Analytics</div>
      <div style="font-size:1rem; color:#4a5568; max-width:760px; margin-top:0.4rem;">
        Dashboard orientado a portfolio para analizar carga operativa, tiempos de resolucion y cuellos de botella.
        Funciona gratis en modo demo o conectado a una API real.
      </div>
    </div>
    """,
    unsafe_allow_html=True,
)

with st.sidebar:
    st.header("Fuente")
    data_source = st.radio("Origen de datos", ["Demo local (gratis)", "API remota"], index=0)
    include_archived = st.checkbox("Incluir archivadas", value=True)
    api_url = st.text_input("API base URL", value=API_BASE_URL)
    st.header("Visualizacion")
    timeline_granularity = st.selectbox("Agrupar serie temporal por", ["Mes", "Trimestre"], index=0)
    heatmap_metric = st.selectbox(
        "Metricas del heatmap",
        ["Conteo de tareas", "Tiempo medio de cierre"],
        index=0,
    )
    top_n_assignees = st.slider("Top responsables en comparativas", min_value=3, max_value=12, value=7)

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

df = enrich_dataframe(df)
stats = stats_from_df(df)

col1, col2, col3, col4, col5 = st.columns(5)
col1.metric("Total", stats["total"])
col2.metric("Completadas", stats["completed"])
col3.metric("Pendientes", stats["pending"])
col4.metric("% cierre", f"{stats['completion_rate']}%")
col5.metric("Promedio min cierre", stats["avg_completion_minutes"])

with st.sidebar:
    st.header("Filtros globales")
    status_options = [status for status in STATUS_ORDER if status in df["status"].astype(str).unique()]
    assignee_options = sorted([value for value in df["assigned_to"].dropna().unique().tolist() if value])
    creator_options = sorted([value for value in df["created_by"].dropna().unique().tolist() if value])
    selected_status = st.multiselect("Estado", options=status_options, default=status_options)
    selected_assignees = st.multiselect("Responsable", options=assignee_options, default=[])
    selected_creators = st.multiselect("Creador", options=creator_options, default=[])
    title_query = st.text_input("Buscar por titulo o descripcion", value="")

    min_date = df["created_at"].min()
    max_date = df["created_at"].max()
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

    completion_series = df["completion_time_minutes"].dropna()
    resolution_max = int(completion_series.max()) if not completion_series.empty else 10080
    resolution_range = st.slider(
        "Tiempo de cierre (min)",
        min_value=0,
        max_value=max(resolution_max, 1),
        value=(0, max(resolution_max, 1)),
    )

filtered_df = filter_dataframe(
    df=df,
    statuses=selected_status,
    assignees=selected_assignees,
    creators=selected_creators,
    title_query=title_query,
    start_date=start_date,
    end_date=end_date,
    resolution_range=list(resolution_range),
)

if filtered_df.empty:
    st.warning("Los filtros actuales no devuelven registros. Ajusta criterios en la barra lateral.")
    st.stop()

render_insights(filtered_df)

csv_bytes = filtered_df.to_csv(index=False).encode("utf-8")
st.download_button(
    label="Descargar CSV filtrado",
    data=csv_bytes,
    file_name="taskflow_filtered_tasks.csv",
    mime="text/csv",
)

overview_tab, timeline_tab, heatmap_tab, detail_tab = st.tabs(
    ["Resumen", "Evolucion", "Mapa de calor", "Detalle"]
)

with overview_tab:
    overview_left, overview_right = st.columns(2)
    with overview_left:
        st.subheader("Distribucion por estado")
        status_counts = (
            filtered_df["status"].astype(str).value_counts().reindex(STATUS_ORDER, fill_value=0).reset_index()
        )
        status_counts.columns = ["status", "count"]
        fig_status = px.bar(
            status_counts,
            x="status",
            y="count",
            color="status",
            color_discrete_map=PALETTE,
        )
        fig_status.update_layout(margin=dict(l=10, r=10, t=30, b=10), height=380)
        st.plotly_chart(fig_status, use_container_width=True)

    with overview_right:
        st.subheader("Tiempo medio de cierre por responsable")
        close_times = filtered_df.dropna(subset=["assigned_to", "completion_time_minutes"])
        if close_times.empty:
            st.info("Aun no hay tiempos de cierre para analizar")
        else:
            agg = (
                close_times.groupby("assigned_to", as_index=False)["completion_time_minutes"]
                .mean()
                .sort_values("completion_time_minutes", ascending=False)
                .head(top_n_assignees)
            )
            fig_time = px.bar(
                agg,
                x="assigned_to",
                y="completion_time_minutes",
                color="completion_time_minutes",
                color_continuous_scale="Tealgrn",
            )
            fig_time.update_layout(margin=dict(l=10, r=10, t=30, b=10), height=380)
            st.plotly_chart(fig_time, use_container_width=True)

    st.subheader("Distribucion de tiempos de resolucion")
    completed_only = filtered_df.dropna(subset=["completion_time_minutes", "status", "assigned_to"])
    if completed_only.empty:
        st.info("No hay tareas completadas dentro del filtro actual.")
    else:
        fig_box = px.box(
            completed_only,
            x="status",
            y="completion_time_minutes",
            color="status",
            color_discrete_map=PALETTE,
            points="outliers",
        )
        fig_box.update_layout(margin=dict(l=10, r=10, t=30, b=10), height=360)
        st.plotly_chart(fig_box, use_container_width=True)

with timeline_tab:
    st.subheader("Evolucion operativa")
    period_column = "created_month" if timeline_granularity == "Mes" else "created_quarter"
    timeline = (
        filtered_df.groupby([period_column, "status"], as_index=False)
        .size()
        .rename(columns={"size": "count"})
    )
    fig_timeline = px.area(
        timeline,
        x=period_column,
        y="count",
        color="status",
        color_discrete_map=PALETTE,
        category_orders={"status": STATUS_ORDER},
    )
    fig_timeline.update_layout(margin=dict(l=10, r=10, t=30, b=10), height=420)
    st.plotly_chart(fig_timeline, use_container_width=True)

    st.subheader("Carga por creador")
    creators_chart = (
        filtered_df.groupby("created_by", as_index=False)
        .size()
        .rename(columns={"size": "count"})
        .sort_values("count", ascending=False)
        .head(top_n_assignees)
    )
    fig_creators = px.line(
        creators_chart,
        x="created_by",
        y="count",
        markers=True,
        color_discrete_sequence=["#1d3557"],
    )
    fig_creators.update_layout(margin=dict(l=10, r=10, t=30, b=10), height=320)
    st.plotly_chart(fig_creators, use_container_width=True)

with heatmap_tab:
    st.subheader("Mapa de calor de carga operativa")
    heatmap_source = filtered_df.copy()
    top_assignees = heatmap_source["assigned_to"].value_counts().head(top_n_assignees).index.tolist()
    heatmap_source = heatmap_source[heatmap_source["assigned_to"].isin(top_assignees)]

    if heatmap_metric == "Conteo de tareas":
        heatmap = (
            heatmap_source.groupby(["assigned_to", "status"], as_index=False)
            .size()
            .rename(columns={"size": "value"})
        )
        fig_heatmap = px.density_heatmap(
            heatmap,
            x="assigned_to",
            y="status",
            z="value",
            histfunc="avg",
            color_continuous_scale="YlGnBu",
        )
    else:
        heatmap = (
            heatmap_source.dropna(subset=["completion_time_minutes"])
            .groupby(["assigned_to", "status"], as_index=False)["completion_time_minutes"]
            .mean()
            .rename(columns={"completion_time_minutes": "value"})
        )
        fig_heatmap = px.density_heatmap(
            heatmap,
            x="assigned_to",
            y="status",
            z="value",
            histfunc="avg",
            color_continuous_scale="Sunsetdark",
        )
    fig_heatmap.update_layout(margin=dict(l=10, r=10, t=30, b=10), height=430)
    st.plotly_chart(fig_heatmap, use_container_width=True)

    st.subheader("Matriz de duracion por tramos")
    duration_matrix = (
        filtered_df.dropna(subset=["completion_bucket", "assigned_to"])
        .groupby(["assigned_to", "completion_bucket"], as_index=False)
        .size()
        .rename(columns={"size": "count"})
    )
    if duration_matrix.empty:
        st.info("No hay suficientes cierres para construir la matriz de duracion.")
    else:
        fig_duration = px.density_heatmap(
            duration_matrix,
            x="assigned_to",
            y="completion_bucket",
            z="count",
            histfunc="avg",
            color_continuous_scale="Mint",
        )
        fig_duration.update_layout(margin=dict(l=10, r=10, t=30, b=10), height=350)
        st.plotly_chart(fig_duration, use_container_width=True)

with detail_tab:
    st.subheader("Resumen filtrado")
    dcol1, dcol2, dcol3, dcol4 = st.columns(4)
    dcol1.metric("Tareas filtradas", int(filtered_df.shape[0]))
    dcol2.metric("Completadas", int((filtered_df["status"] == "completed").sum()))
    dcol3.metric("Bloqueadas", int((filtered_df["status"] == "blocked").sum()))
    dcol4.metric("Canceladas", int((filtered_df["status"] == "cancelled").sum()))
    st.dataframe(
        filtered_df.sort_values("created_at", ascending=False),
        use_container_width=True,
        hide_index=True,
    )
