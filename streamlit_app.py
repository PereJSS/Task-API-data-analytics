import random
from datetime import datetime, timedelta
from io import BytesIO
from typing import Dict, List, Tuple
from zipfile import ZIP_DEFLATED, ZipFile

import pandas as pd
import plotly.express as px
import requests
import streamlit as st
from plotly.graph_objects import Figure
from reportlab.lib.pagesizes import A4
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas

from app.config import settings

API_BASE_URL = settings.streamlit_api_base_url
WRITE_API_KEY = settings.write_api_key
STATUS_ORDER = ["pending", "in_progress", "blocked", "completed", "cancelled"]
WEEKDAY_ORDER = [
    "Monday",
    "Tuesday",
    "Wednesday",
    "Thursday",
    "Friday",
    "Saturday",
    "Sunday",
]
DATETIME_COLUMNS = ["created_at", "updated_at", "started_at", "completed_at"]
COMPLETION_BUCKET_BINS = [0, 240, 1440, 4320, 10080, 100000]
COMPLETION_BUCKET_LABELS = ["<4h", "4h-1d", "1d-3d", "3d-7d", ">7d"]
PALETTE = {
    "pending": "#e9c46a",
    "in_progress": "#3a86ff",
    "blocked": "#e76f51",
    "completed": "#2a9d8f",
    "cancelled": "#6c757d",
}

CHART_TITLES = {
    "status_distribution": "Distribucion por estado",
    "closure_time_by_assignee": "Tiempo medio de cierre por responsable",
    "resolution_boxplot": "Distribucion de tiempos de resolucion",
    "completion_rate_by_assignee": "Tasa de cierre por responsable",
    "timeline": "Evolucion operativa",
    "creator_load": "Carga por creador",
    "ageing_vs_closure": "Antiguedad vs tiempo de cierre",
    "heatmap": "Mapa de calor operativa",
    "duration_matrix": "Matriz de duracion por tramos",
}


def inject_styles() -> None:
    """Apply a small visual system so the dashboard looks intentional in portfolio mode."""
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
    """Normalize API or demo records into a dataframe ready for analysis."""
    if not tasks:
        return pd.DataFrame()

    df = pd.DataFrame(tasks)
    for col in DATETIME_COLUMNS:
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], errors="coerce")
    df["completion_time_minutes"] = pd.to_numeric(
        df.get("completion_time_minutes"), errors="coerce"
    )
    return df


@st.cache_data(ttl=120, show_spinner=False)
def fetch_tasks_from_api(api_base_url: str, include_archived: bool = True) -> pd.DataFrame:
    """Load all tasks from the backend using paginated requests."""
    all_tasks = []
    limit = 500
    offset = 0
    session = requests.Session()

    while True:
        response = session.get(
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
    """Generate a reproducible demo dataset so Streamlit can run without any backend."""
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
        # Spread task creation across three years to make trend and seasonality charts believable.
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

        updated_at = max(
            [date for date in [created_at, started_at, completed_at] if date is not None]
        )
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
    """Add derived columns used by charts and filters without mutating the original source."""
    enriched = df.copy()
    enriched["status"] = pd.Categorical(
        enriched["status"], categories=STATUS_ORDER, ordered=True
    )
    enriched["created_month"] = enriched["created_at"].dt.to_period("M").astype(str)
    enriched["created_quarter"] = enriched["created_at"].dt.to_period("Q").astype(str)
    enriched["created_weekday"] = enriched["created_at"].dt.day_name()
    enriched["created_weekday"] = pd.Categorical(
        enriched["created_weekday"], categories=WEEKDAY_ORDER, ordered=True
    )
    enriched["completion_time_days"] = (enriched["completion_time_minutes"] / 1440).round(2)
    enriched["task_age_days"] = (
        (pd.Timestamp.utcnow().tz_localize(None) - enriched["created_at"])
        .dt.total_seconds()
        .div(86400)
        .round(2)
    )
    enriched["completion_bucket"] = pd.cut(
        enriched["completion_time_minutes"],
        bins=COMPLETION_BUCKET_BINS,
        labels=COMPLETION_BUCKET_LABELS,
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
    """Apply the same filter set to every chart so the whole dashboard stays consistent."""
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
    """Build the KPI cards displayed at the top of the dashboard."""
    avg_minutes = df["completion_time_minutes"].dropna().mean()
    completion_rate = 0 if df.empty else round(float((df["status"] == "completed").mean() * 100), 1)
    return {
        "total": int(df.shape[0]),
        "completed": int((df["status"] == "completed").sum()),
        "pending": int((df["status"] == "pending").sum()),
        "avg_completion_minutes": 0 if pd.isna(avg_minutes) else round(float(avg_minutes), 2),
        "completion_rate": completion_rate,
    }


def add_duration_display_column(
    df: pd.DataFrame,
    source_column: str,
    unit: str,
    target_column: str = "duration_value",
) -> Tuple[pd.DataFrame, str, str]:
    """Create a display column in minutes, hours or days without altering the source metric."""
    result = df.copy()
    result[target_column] = result[source_column]
    label = "Tiempo de cierre (min)"

    if unit == "Horas":
        result[target_column] = (result[source_column] / 60).round(2)
        label = "Tiempo de cierre (h)"
    elif unit == "Dias":
        result[target_column] = (result[source_column] / 1440).round(2)
        label = "Tiempo de cierre (dias)"

    return result, target_column, label


def format_duration_value(minutes: float, unit: str) -> str:
    """Format a duration KPI using the requested display unit."""
    if pd.isna(minutes):
        return "N/A"

    if unit == "Horas":
        return f"{round(float(minutes) / 60, 2)} h"
    if unit == "Dias":
        return f"{round(float(minutes) / 1440, 2)} d"
    return f"{round(float(minutes), 2)} min"


def create_task_from_streamlit(api_base_url: str, payload: Dict, api_key: str) -> None:
    """Send one new task to the backend and surface the result to the user."""
    response = requests.post(
        f"{api_base_url}/tasks",
        json=payload,
        headers={"X-API-Key": api_key},
        timeout=10,
    )
    response.raise_for_status()


def build_chart_export_zip(figures: Dict[str, Figure], export_format: str) -> bytes:
    """Package the current figures as a downloadable zip in HTML or PNG format."""
    buffer = BytesIO()
    extension = "html" if export_format == "html" else "png"

    with ZipFile(buffer, mode="w", compression=ZIP_DEFLATED) as archive:
        for chart_key, fig in figures.items():
            if export_format == "html":
                content = fig.to_html(full_html=True, include_plotlyjs="cdn").encode("utf-8")
            else:
                content = fig.to_image(format="png", scale=2)
            archive.writestr(f"{chart_key}.{extension}", content)

    return buffer.getvalue()


def build_pdf_report(
    stats: Dict[str, float],
    df: pd.DataFrame,
    figures: Dict[str, Figure],
    closure_time_unit: str,
) -> bytes:
    """Generate a compact PDF report with KPIs and the most representative charts."""
    pdf_buffer = BytesIO()
    pdf = canvas.Canvas(pdf_buffer, pagesize=A4)
    width, height = A4
    margin_x = 40
    y_position = height - 50

    pdf.setTitle("TaskFlow Analytics Report")
    pdf.setFont("Helvetica-Bold", 20)
    pdf.drawString(margin_x, y_position, "TaskFlow Analytics Report")

    y_position -= 24
    pdf.setFont("Helvetica", 10)
    pdf.drawString(
        margin_x,
        y_position,
        f"Generado: {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}",
    )

    y_position -= 28
    pdf.setFont("Helvetica-Bold", 12)
    pdf.drawString(margin_x, y_position, "Resumen ejecutivo")

    y_position -= 18
    pdf.setFont("Helvetica", 10)
    summary_lines = [
        f"Total tareas: {stats['total']}",
        f"Completadas: {stats['completed']}",
        f"Pendientes: {stats['pending']}",
        f"Porcentaje de cierre: {stats['completion_rate']}%",
        "Promedio de cierre: "
        f"{format_duration_value(stats['avg_completion_minutes'], closure_time_unit)}",
    ]
    for line in summary_lines:
        pdf.drawString(margin_x, y_position, line)
        y_position -= 14

    busiest = "N/A"
    if not df["assigned_to"].dropna().empty:
        busiest = str(df["assigned_to"].value_counts().index[0])
    blocked_share = 0 if df.empty else round(float((df["status"] == "blocked").mean() * 100), 1)
    pdf.drawString(margin_x, y_position, f"Responsable con mas carga: {busiest}")
    y_position -= 14
    pdf.drawString(margin_x, y_position, f"Peso de bloqueos: {blocked_share}%")
    y_position -= 24

    for chart_key in list(figures.keys())[:3]:
        chart_title = CHART_TITLES.get(chart_key, chart_key.replace("_", " ").title())
        image_bytes = figures[chart_key].to_image(format="png", scale=2)
        image = ImageReader(BytesIO(image_bytes))
        chart_height = 180
        chart_width = width - (margin_x * 2)

        if y_position - chart_height < 60:
            pdf.showPage()
            y_position = height - 50

        pdf.setFont("Helvetica-Bold", 11)
        pdf.drawString(margin_x, y_position, chart_title)
        y_position -= 16
        pdf.drawImage(
            image,
            margin_x,
            y_position - chart_height,
            width=chart_width,
            height=chart_height,
            preserveAspectRatio=True,
            mask="auto",
        )
        y_position -= chart_height + 22

    pdf.save()
    return pdf_buffer.getvalue()


def render_insights(df: pd.DataFrame) -> None:
    """Surface three quick conclusions so the reader understands the story before the detail."""
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


def render_portfolio_summary(df: pd.DataFrame) -> None:
    """Summarize business-facing signals that help explain the operational picture quickly."""
    completed = df[df["status"].astype(str) == "completed"]
    completion_days = completed["completion_time_days"].dropna()
    median_days = round(float(completion_days.median()), 2) if not completion_days.empty else 0
    p90_days = round(float(completion_days.quantile(0.9)), 2) if not completion_days.empty else 0
    active_work = int(df["status"].astype(str).isin(["pending", "in_progress", "blocked"]).sum())

    st.markdown("### Lectura ejecutiva")
    exec_col1, exec_col2, exec_col3 = st.columns(3)
    exec_col1.metric("Trabajo activo", active_work)
    exec_col2.metric("Mediana cierre", f"{median_days} d")
    exec_col3.metric("P90 cierre", f"{p90_days} d")


st.set_page_config(page_title="TaskFlow Analytics", layout="wide")
inject_styles()
st.markdown(
    """
    <div class="hero-card">
            <div
                style="font-size:0.8rem; letter-spacing:0.08em; color:#5c677d;"
            >
                Operations Intelligence
            </div>
            <div
                style="font-size:2.2rem; font-weight:800; color:#1d3557; margin-top:0.2rem;"
            >TaskFlow Analytics</div>
      <div style="font-size:1rem; color:#4a5568; max-width:760px; margin-top:0.4rem;">
                Dashboard orientado a portfolio para analizar carga operativa,
                tiempos de resolucion y cuellos de botella.
        Funciona gratis en modo demo o conectado a una API real.
      </div>
    </div>
    """,
    unsafe_allow_html=True,
)

with st.sidebar:
    st.header("Panel de control")
    st.caption("Configura origen, filtros y comportamiento de cada bloque analitico.")

    st.subheader("Fuente de datos")
    default_source_index = 1 if settings.streamlit_default_data_source == "api" else 0
    data_source = st.radio(
        "Origen de datos",
        ["Demo local (gratis)", "API remota"],
        index=default_source_index,
    )
    include_archived = st.checkbox("Incluir archivadas", value=True)
    api_url = st.text_input("API base URL", value=API_BASE_URL)
    if data_source == "API remota" and st.button("Recargar datos API", use_container_width=True):
        fetch_tasks_from_api.clear()
        st.rerun()
    write_api_key = st.text_input(
        "Clave de escritura",
        value=WRITE_API_KEY,
        type="password",
        help="Solo necesaria para crear, editar o archivar tareas en despliegues protegidos.",
    )
    st.divider()

    with st.expander("Resumen y tiempos", expanded=True):
        status_chart_style = st.selectbox(
            "Grafico de estados",
            ["Barras", "Donut"],
            index=0,
        )
        status_chart_metric = st.selectbox(
            "Metrica de estados",
            ["Conteo", "Porcentaje"],
            index=0,
        )
        closure_time_unit = st.selectbox(
            "Unidad para tiempos medios",
            ["Minutos", "Horas", "Dias"],
            index=2,
        )
        boxplot_time_unit = st.selectbox(
            "Unidad para distribucion de tiempos",
            ["Minutos", "Horas", "Dias"],
            index=2,
        )
        top_n_assignees = st.slider(
            "Top responsables en comparativas",
            min_value=3,
            max_value=12,
            value=7,
        )

    with st.expander("Evolucion temporal", expanded=False):
        timeline_granularity = st.selectbox(
            "Agrupar serie temporal por",
            ["Mes", "Trimestre"],
            index=0,
        )
        timeline_metric = st.selectbox(
            "Metrica de serie temporal",
            ["Todas las tareas", "Solo completadas", "Solo bloqueadas"],
            index=0,
        )
        timeline_style = st.selectbox(
            "Tipo de serie temporal",
            ["Area", "Linea"],
            index=0,
        )

    with st.expander("Mapa de calor", expanded=False):
        heatmap_metric = st.selectbox(
            "Metricas del heatmap",
            ["Conteo de tareas", "Tiempo medio de cierre"],
            index=0,
        )
        heatmap_grouping = st.selectbox(
            "Cruce del heatmap",
            ["Responsable vs estado", "Responsable vs dia de la semana"],
            index=0,
        )

if data_source == "Demo local (gratis)":
    df = build_demo_dataframe()
    if not include_archived:
        df = df[df["archived"] == False]  # noqa: E712
else:
    try:
        with st.spinner("Cargando datos desde la API..."):
            df = fetch_tasks_from_api(api_url.rstrip("/"), include_archived=include_archived)
    except requests.RequestException as exc:
        st.error(f"No se pudo conectar con la API: {exc}")
        st.stop()

if df.empty:
    st.info("No hay tareas para mostrar")
    st.stop()

df = enrich_dataframe(df)
stats = stats_from_df(df)
avg_completion_label = "Promedio cierre"
avg_completion_value = format_duration_value(
    stats["avg_completion_minutes"],
    closure_time_unit,
)

col1, col2, col3, col4, col5 = st.columns(5)
col1.metric("Total", stats["total"])
col2.metric("Completadas", stats["completed"])
col3.metric("Pendientes", stats["pending"])
col4.metric("% cierre", f"{stats['completion_rate']}%")
col5.metric(avg_completion_label, avg_completion_value)

with st.sidebar:
    st.divider()
    st.subheader("Filtros globales")
    status_options = [
        status for status in STATUS_ORDER if status in df["status"].astype(str).unique()
    ]
    assignee_options = sorted(
        [value for value in df["assigned_to"].dropna().unique().tolist() if value]
    )
    creator_options = sorted(
        [value for value in df["created_by"].dropna().unique().tolist() if value]
    )
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
render_portfolio_summary(filtered_df)

csv_bytes = filtered_df.to_csv(index=False).encode("utf-8")
st.download_button(
    label="Descargar CSV filtrado",
    data=csv_bytes,
    file_name="taskflow_filtered_tasks.csv",
    mime="text/csv",
)

export_figures: Dict[str, Figure] = {}

overview_tab, timeline_tab, heatmap_tab, detail_tab = st.tabs(
    ["Resumen", "Evolucion", "Mapa de calor", "Detalle"]
)

with overview_tab:
    overview_left, overview_right = st.columns(2)
    with overview_left:
        st.subheader("Distribucion por estado")
        status_counts = (
            filtered_df["status"]
            .astype(str)
            .value_counts()
            .reindex(STATUS_ORDER, fill_value=0)
            .reset_index()
        )
        status_counts.columns = ["status", "count"]
        status_counts["percentage"] = (
            (status_counts["count"] / max(status_counts["count"].sum(), 1)) * 100
        ).round(2)
        status_value_column = "count" if status_chart_metric == "Conteo" else "percentage"
        status_label = "Tareas" if status_chart_metric == "Conteo" else "% del total"
        if status_chart_style == "Barras":
            fig_status = px.bar(
                status_counts,
                x="status",
                y=status_value_column,
                color="status",
                color_discrete_map=PALETTE,
                labels={status_value_column: status_label, "status": "Estado"},
            )
        else:
            fig_status = px.pie(
                status_counts,
                names="status",
                values=status_value_column,
                color="status",
                color_discrete_map=PALETTE,
                hole=0.55,
            )
        fig_status.update_layout(margin=dict(l=10, r=10, t=30, b=10), height=380)
        export_figures["status_distribution"] = fig_status
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
            agg, value_column, value_label = add_duration_display_column(
                agg,
                source_column="completion_time_minutes",
                unit=closure_time_unit,
                target_column="completion_time_value",
            )
            fig_time = px.bar(
                agg,
                x="assigned_to",
                y=value_column,
                color=value_column,
                color_continuous_scale="Tealgrn",
                labels={value_column: value_label, "assigned_to": "Responsable"},
            )
            fig_time.update_layout(margin=dict(l=10, r=10, t=30, b=10), height=380)
            export_figures["closure_time_by_assignee"] = fig_time
            st.plotly_chart(fig_time, use_container_width=True)

    st.subheader("Distribucion de tiempos de resolucion")
    completed_only = filtered_df.dropna(subset=["completion_time_minutes", "status", "assigned_to"])
    if completed_only.empty:
        st.info("No hay tareas completadas dentro del filtro actual.")
    else:
        completed_only, boxplot_value_column, boxplot_label = add_duration_display_column(
            completed_only,
            source_column="completion_time_minutes",
            unit=boxplot_time_unit,
            target_column="completion_time_value",
        )
        fig_box = px.box(
            completed_only,
            x="status",
            y=boxplot_value_column,
            color="status",
            color_discrete_map=PALETTE,
            points="outliers",
            labels={boxplot_value_column: boxplot_label, "status": "Estado"},
        )
        fig_box.update_layout(margin=dict(l=10, r=10, t=30, b=10), height=360)
        export_figures["resolution_boxplot"] = fig_box
        st.plotly_chart(fig_box, use_container_width=True)

    st.subheader("Tasa de cierre por responsable")
    assignee_status = filtered_df.dropna(subset=["assigned_to"]).copy()
    if assignee_status.empty:
        st.info("No hay responsables suficientes para comparar tasa de cierre.")
    else:
        assignee_kpis = (
            assignee_status.groupby("assigned_to")
            .agg(
                total=("id", "count"),
                completed=("completed", "sum"),
            )
            .reset_index()
        )
        assignee_kpis["completion_rate"] = (
            assignee_kpis["completed"] / assignee_kpis["total"] * 100
        ).round(1)
        assignee_kpis = assignee_kpis.sort_values("completion_rate", ascending=False).head(
            top_n_assignees
        )
        fig_completion_rate = px.bar(
            assignee_kpis,
            x="assigned_to",
            y="completion_rate",
            color="completion_rate",
            color_continuous_scale="Blues",
            labels={
                "assigned_to": "Responsable",
                "completion_rate": "% de cierre",
            },
        )
        fig_completion_rate.update_layout(
            margin=dict(l=10, r=10, t=30, b=10),
            height=340,
        )
        export_figures["completion_rate_by_assignee"] = fig_completion_rate
        st.plotly_chart(fig_completion_rate, use_container_width=True)

with timeline_tab:
    st.subheader("Evolucion operativa")
    period_column = "created_month" if timeline_granularity == "Mes" else "created_quarter"
    timeline_source = filtered_df.copy()
    if timeline_metric == "Solo completadas":
        timeline_source = timeline_source[timeline_source["status"].astype(str) == "completed"]
    elif timeline_metric == "Solo bloqueadas":
        timeline_source = timeline_source[timeline_source["status"].astype(str) == "blocked"]
    timeline = (
        timeline_source.groupby([period_column, "status"], as_index=False)
        .size()
        .rename(columns={"size": "count"})
    )
    if timeline_style == "Area":
        fig_timeline = px.area(
            timeline,
            x=period_column,
            y="count",
            color="status",
            color_discrete_map=PALETTE,
            category_orders={"status": STATUS_ORDER},
        )
    else:
        fig_timeline = px.line(
            timeline,
            x=period_column,
            y="count",
            color="status",
            color_discrete_map=PALETTE,
            category_orders={"status": STATUS_ORDER},
            markers=True,
        )
    fig_timeline.update_layout(margin=dict(l=10, r=10, t=30, b=10), height=420)
    export_figures["timeline"] = fig_timeline
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
    export_figures["creator_load"] = fig_creators
    st.plotly_chart(fig_creators, use_container_width=True)

    st.subheader("Antiguedad vs tiempo de cierre")
    ageing_source = filtered_df.dropna(
        subset=["completion_time_minutes", "assigned_to", "task_age_days"]
    )
    if ageing_source.empty:
        st.info("No hay datos suficientes para comparar antiguedad y tiempo de cierre.")
    else:
        fig_ageing = px.scatter(
            ageing_source,
            x="task_age_days",
            y="completion_time_days",
            color="status",
            size="completion_time_days",
            hover_data=["title", "assigned_to", "created_by"],
            color_discrete_map=PALETTE,
            labels={
                "task_age_days": "Antiguedad de la tarea (dias)",
                "completion_time_days": "Tiempo de cierre (dias)",
            },
        )
        fig_ageing.update_layout(margin=dict(l=10, r=10, t=30, b=10), height=380)
        export_figures["ageing_vs_closure"] = fig_ageing
        st.plotly_chart(fig_ageing, use_container_width=True)

with heatmap_tab:
    st.subheader("Mapa de calor de carga operativa")
    heatmap_source = filtered_df.copy()
    top_assignees = (
        heatmap_source["assigned_to"].value_counts().head(top_n_assignees).index.tolist()
    )
    heatmap_source = heatmap_source[heatmap_source["assigned_to"].isin(top_assignees)]
    heatmap_y = "status"
    heatmap_y_label = "Estado"
    if heatmap_grouping == "Responsable vs dia de la semana":
        heatmap_y = "created_weekday"
        heatmap_y_label = "Dia de la semana"

    if heatmap_metric == "Conteo de tareas":
        heatmap = (
            heatmap_source.groupby(["assigned_to", heatmap_y], as_index=False)
            .size()
            .rename(columns={"size": "value"})
        )
        fig_heatmap = px.density_heatmap(
            heatmap,
            x="assigned_to",
            y=heatmap_y,
            z="value",
            histfunc="avg",
            color_continuous_scale="YlGnBu",
            category_orders={"created_weekday": WEEKDAY_ORDER},
            labels={"assigned_to": "Responsable", heatmap_y: heatmap_y_label, "value": "Valor"},
        )
    else:
        heatmap = (
            heatmap_source.dropna(subset=["completion_time_minutes"])
            .groupby(["assigned_to", heatmap_y], as_index=False)["completion_time_minutes"]
            .mean()
            .rename(columns={"completion_time_minutes": "value"})
        )
        fig_heatmap = px.density_heatmap(
            heatmap,
            x="assigned_to",
            y=heatmap_y,
            z="value",
            histfunc="avg",
            color_continuous_scale="Sunsetdark",
            category_orders={"created_weekday": WEEKDAY_ORDER},
            labels={"assigned_to": "Responsable", heatmap_y: heatmap_y_label, "value": "Valor"},
        )
    fig_heatmap.update_layout(margin=dict(l=10, r=10, t=30, b=10), height=430)
    export_figures["heatmap"] = fig_heatmap
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
        export_figures["duration_matrix"] = fig_duration
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

    st.divider()
    st.subheader("Exportacion")
    pdf_report = build_pdf_report(
        stats=stats,
        df=filtered_df,
        figures=export_figures,
        closure_time_unit=closure_time_unit,
    )
    html_zip = build_chart_export_zip(export_figures, export_format="html")
    png_zip = build_chart_export_zip(export_figures, export_format="png")

    export_col1, export_col2, export_col3 = st.columns(3)
    export_col1.download_button(
        label="Descargar reporte PDF",
        data=pdf_report,
        file_name="taskflow_report.pdf",
        mime="application/pdf",
    )
    export_col2.download_button(
        label="Descargar graficos HTML",
        data=html_zip,
        file_name="taskflow_charts_html.zip",
        mime="application/zip",
    )
    export_col3.download_button(
        label="Descargar graficos PNG",
        data=png_zip,
        file_name="taskflow_charts_png.zip",
        mime="application/zip",
    )

    if data_source == "API remota":
        st.divider()
        st.subheader("Crear tarea en la API")
        if not write_api_key:
            st.info("Modo solo lectura: configura una clave de escritura para crear tareas.")
        else:
            with st.form("create_task_form"):
                form_col1, form_col2 = st.columns(2)
                with form_col1:
                    new_title = st.text_input("Titulo")
                    new_description = st.text_area("Descripcion")
                    new_created_by = st.text_input("Creado por")
                with form_col2:
                    new_assigned_to = st.text_input("Responsable")
                    new_status = st.selectbox("Estado inicial", STATUS_ORDER, index=0)
                    new_archived = st.checkbox("Crear como archivada", value=False)

                submitted = st.form_submit_button("Crear tarea")

            if submitted:
                if not new_title.strip():
                    st.error("El titulo es obligatorio.")
                    st.stop()
                payload = {
                    "title": new_title.strip(),
                    "description": new_description or None,
                    "created_by": new_created_by or None,
                    "assigned_to": new_assigned_to or None,
                    "status": new_status,
                    "completed": new_status == "completed",
                    "archived": new_archived,
                }
                try:
                    create_task_from_streamlit(
                        api_url.rstrip("/"),
                        payload,
                        write_api_key,
                    )
                    st.success(
                        "Tarea creada correctamente. Recarga la pagina para verla en las graficas."
                    )
                    st.rerun()
                except requests.RequestException as exc:
                    st.error(f"No se pudo crear la tarea: {exc}")
