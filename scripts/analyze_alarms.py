#!/usr/bin/env python3
"""
Generate alarm insights, charts, and summary data from the Infineon spreadsheet.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Dict, List

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_MPL_DIR = REPO_ROOT / ".mpl_cache"
DEFAULT_MPL_DIR.mkdir(exist_ok=True)
os.environ.setdefault("MPLCONFIGDIR", str(DEFAULT_MPL_DIR))

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns

CATEGORY_RULES = [
    ("E84 handshaking & interlocks", ["e84", "u_req", "l_req", "ready", "ho-avbl", "es"]),
    ("FOUP handling & lock issues", ["foup", "flange", "lock", "loss"]),
    ("Robot hand motion/control", ["hand", "swing", "positioning", "vehicle communication connection error"]),
    ("Sensors & detection", ["sensor", "detect", "detection", "sag", "presence", "look down"]),
    ("Communication & power", ["communication", "connection", "voltage"]),
]


def categorize(alarm_text: str) -> str:
    lower = str(alarm_text).lower()
    for name, keywords in CATEGORY_RULES:
        if any(keyword in lower for keyword in keywords):
            return name
    return "Other / misc"


def load_alarm_data(workbook: Path, sheet_name: str = "AlarmData") -> pd.DataFrame:
    df = pd.read_excel(workbook, sheet_name=sheet_name, header=1, engine="openpyxl")
    df = df[["Month", "Alarm_ID", "Count", "AlarmText"]].dropna(subset=["Month", "Alarm_ID", "Count"])
    df["Count"] = pd.to_numeric(df["Count"], errors="coerce")
    df = df.dropna(subset=["Count"])
    df["Count"] = df["Count"].astype(int)
    df["Month"] = pd.to_datetime(df["Month"].astype(int).astype(str), format="%Y%m")
    df["Category"] = df["AlarmText"].apply(categorize)
    return df


def build_summary(df: pd.DataFrame) -> Dict:
    top_alarms = (
        df.groupby(["Alarm_ID", "AlarmText"])["Count"].sum().sort_values(ascending=False).head(10).reset_index()
    )
    monthly = df.groupby("Month").agg(total_count=("Count", "sum"), unique_alarms=("Alarm_ID", "nunique")).reset_index()
    category_totals = df.groupby("Category")["Count"].sum().sort_values(ascending=False).reset_index()

    return {
        "records": int(len(df)),
        "period_start": monthly["Month"].min().strftime("%Y-%m"),
        "period_end": monthly["Month"].max().strftime("%Y-%m"),
        "total_alarms_logged": int(df["Count"].sum()),
        "top_alarm_share": round(top_alarms["Count"].sum() / df["Count"].sum(), 4),
        "top_alarms": top_alarms.to_dict(orient="records"),
        "top_month": monthly.loc[monthly["total_count"].idxmax()].to_dict(),
        "lowest_month": monthly.loc[monthly["total_count"].idxmin()].to_dict(),
        "monthly_totals": monthly.to_dict(orient="records"),
        "category_totals": category_totals.to_dict(orient="records"),
    }


def plot_top_alarms(df: pd.DataFrame, charts_dir: Path) -> Path:
    sns.set_theme(style="whitegrid")
    top_alarms = (
        df.groupby(["Alarm_ID", "AlarmText"])["Count"].sum().sort_values(ascending=False).head(10).reset_index()
    )
    plt.figure(figsize=(10, 6))
    sns.barplot(data=top_alarms, y="AlarmText", x="Count", color="#2563eb")
    plt.title("Top 10 Alarm Types by Total Count")
    plt.xlabel("Total occurrences (Jan 2024 – Oct 2025)")
    plt.ylabel("Alarm")
    plt.tight_layout()
    out_path = charts_dir / "top_alarms.png"
    plt.savefig(out_path, dpi=150)
    plt.close()
    return out_path


def plot_monthly_totals(df: pd.DataFrame, charts_dir: Path) -> Path:
    monthly = df.groupby("Month")["Count"].sum().reset_index()
    plt.figure(figsize=(11, 5))
    sns.lineplot(data=monthly, x="Month", y="Count", marker="o", color="#16a34a")
    plt.title("Monthly Alarm Totals")
    plt.xlabel("Month")
    plt.ylabel("Alarm occurrences")
    plt.tight_layout()
    out_path = charts_dir / "monthly_totals.png"
    plt.savefig(out_path, dpi=150)
    plt.close()
    return out_path


def plot_category_totals(df: pd.DataFrame, charts_dir: Path) -> Path:
    category_totals = df.groupby("Category")["Count"].sum().sort_values(ascending=False).reset_index()
    plt.figure(figsize=(9, 5))
    sns.barplot(data=category_totals, x="Count", y="Category", hue="Category", palette="viridis", legend=False)
    plt.title("Alarm Volume by Cause Category")
    plt.xlabel("Total occurrences")
    plt.ylabel("Category")
    plt.tight_layout()
    out_path = charts_dir / "category_totals.png"
    plt.savefig(out_path, dpi=150)
    plt.close()
    return out_path


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate alarm insights, charts, and JSON summary.")
    parser.add_argument("--workbook", type=Path, default=Path("infineon.xlsx"), help="Path to the Excel workbook.")
    parser.add_argument("--sheet", default="AlarmData", help="Sheet name containing aggregated alarm data.")
    parser.add_argument("--analysis-dir", type=Path, default=Path("analysis"), help="Directory for summary output.")
    parser.add_argument("--charts-dir", type=Path, default=Path("charts"), help="Directory for generated charts.")
    args = parser.parse_args()

    df = load_alarm_data(args.workbook, args.sheet)

    args.analysis_dir.mkdir(exist_ok=True)
    args.charts_dir.mkdir(exist_ok=True)

    summary = build_summary(df)
    (args.analysis_dir / "summary.json").write_text(json.dumps(summary, indent=2, default=str))

    generated_charts: List[Path] = [
        plot_top_alarms(df, args.charts_dir),
        plot_monthly_totals(df, args.charts_dir),
        plot_category_totals(df, args.charts_dir),
    ]

    print(f"Wrote analysis summary to {args.analysis_dir / 'summary.json'}")
    for chart in generated_charts:
        print(f"Saved {chart}")


if __name__ == "__main__":
    main()

