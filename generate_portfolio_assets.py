import random
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd
import plotly.express as px

from seed_tasks import build_task

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
PALETTE = {
    "pending": "#e9c46a",
    "in_progress": "#3a86ff",
    "blocked": "#e76f51",
    "completed": "#2a9d8f",
    "cancelled": "#6c757d",
}


def build_demo_dataset(task_count: int = 700) -> pd.DataFrame:
    random.seed(42)
    now = datetime.utcnow()
    period_start = now - timedelta(days=365 * 3)
    rows = []
    for _ in range(task_count):
        task = build_task(now=now, period_start=period_start)
        rows.append(
            {
                "title": task.title,
                "assigned_to": task.assigned_to,
                "status": task.status,
                "created_at": task.created_at,
                "completion_time_minutes": task.completion_time_minutes,
            }
        )

    df = pd.DataFrame(rows)
    df["created_at"] = pd.to_datetime(df["created_at"], errors="coerce")
    df["created_month"] = df["created_at"].dt.to_period("M").astype(str)
    df["created_weekday"] = pd.Categorical(
        df["created_at"].dt.day_name(),
        categories=WEEKDAY_ORDER,
        ordered=True,
    )
    return df


def generate_assets() -> None:
    df = build_demo_dataset()
    assets_dir = Path("assets")
    assets_dir.mkdir(exist_ok=True)

    status_counts = (
        df["status"].astype(str).value_counts().reindex(STATUS_ORDER, fill_value=0).reset_index()
    )
    status_counts.columns = ["status", "count"]
    status_fig = px.bar(
        status_counts,
        x="status",
        y="count",
        color="status",
        color_discrete_map=PALETTE,
        title="Distribucion por estado",
    )
    status_fig.update_layout(template="plotly_white", height=420, width=900)
    status_fig.write_image(assets_dir / "capture-status.png")

    timeline = (
        df.groupby(["created_month", "status"], as_index=False)
        .size()
        .rename(columns={"size": "count"})
    )
    timeline_fig = px.area(
        timeline,
        x="created_month",
        y="count",
        color="status",
        color_discrete_map=PALETTE,
        category_orders={"status": STATUS_ORDER},
        title="Evolucion operativa",
    )
    timeline_fig.update_layout(template="plotly_white", height=420, width=900)
    timeline_fig.write_image(assets_dir / "capture-timeline.png")

    heatmap = (
        df.dropna(subset=["assigned_to"])
        .groupby(["assigned_to", "created_weekday"], as_index=False)
        .size()
        .rename(columns={"size": "value"})
    )
    heatmap_fig = px.density_heatmap(
        heatmap,
        x="assigned_to",
        y="created_weekday",
        z="value",
        histfunc="avg",
        title="Mapa de calor por responsable y dia",
        color_continuous_scale="YlGnBu",
        category_orders={"created_weekday": WEEKDAY_ORDER},
    )
    heatmap_fig.update_layout(template="plotly_white", height=420, width=900)
    heatmap_fig.write_image(assets_dir / "capture-heatmap.png")


if __name__ == "__main__":
    generate_assets()