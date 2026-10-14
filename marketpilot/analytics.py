"""Deterministic campaign metrics: Python calculates; the LLM interprets."""

import csv
import math
from pathlib import Path

import pandas as pd

CAMPAIGN_DIRECTORY = Path(__file__).resolve().parent.parent / "data" / "campaigns"
REQUIRED_COLUMNS = ["channel", "impressions", "clicks", "conversions", "spend"]
COUNT_COLUMNS = ["impressions", "clicks", "conversions"]


def resolve_csv(filename: str, directory: Path = CAMPAIGN_DIRECTORY) -> Path:
    """Only analyze local CSVs under the campaign directory, never URLs or arbitrary files."""
    root = directory.resolve()
    path = (root / filename).resolve()
    if not path.is_relative_to(root) or path.suffix.lower() != ".csv":
        raise ValueError("Use a CSV filename inside data/campaigns/.")
    if not path.is_file():
        raise ValueError(f"Campaign CSV not found: {path.name}. Place it in data/campaigns/.")
    if path.stat().st_size > 5_000_000:
        raise ValueError("Campaign CSV must be smaller than 5 MB.")
    return path


def load_campaign(path: Path) -> pd.DataFrame:
    """Reject ambiguous input rather than silently dropping or guessing values."""
    try:
        with path.open(encoding="utf-8-sig", newline="") as handle:
            header = next(csv.reader(handle), [])
        if len(header) != len(set(header)):
            raise ValueError("CSV has duplicate column names.")
        frame = pd.read_csv(path, encoding="utf-8-sig", nrows=10_001)
    except (pd.errors.ParserError, pd.errors.EmptyDataError, UnicodeError) as exc:
        raise ValueError("CSV must be valid UTF-8 with a header and data rows.") from exc
    missing = sorted(set(REQUIRED_COLUMNS) - set(frame.columns))
    if missing:
        raise ValueError(f"CSV is missing required columns: {', '.join(missing)}.")
    if frame.empty or len(frame) > 10_000:
        raise ValueError("CSV must contain 1–10,000 data rows.")
    if frame["channel"].isna().any() or frame["channel"].astype(str).str.strip().eq("").any():
        raise ValueError("Every row needs a nonempty channel.")
    frame["channel"] = frame["channel"].astype(str).str.strip()
    numeric_columns = COUNT_COLUMNS + ["spend"] + (["revenue"] if "revenue" in frame else [])
    for column in numeric_columns:
        try:
            frame[column] = pd.to_numeric(frame[column], errors="raise")
        except (ValueError, TypeError) as exc:
            raise ValueError(f"Column {column} must contain numeric values.") from exc
        if frame[column].isna().any() or not frame[column].map(math.isfinite).all() or (frame[column] < 0).any():
            raise ValueError(f"Column {column} must contain finite, nonnegative values with no blanks.")
        if column in COUNT_COLUMNS and (frame[column] % 1 != 0).any():
            raise ValueError(f"Column {column} must contain whole-number counts.")
    # This simple schema assumes at most one conversion per click.
    if (frame["clicks"] > frame["impressions"]).any() or (frame["conversions"] > frame["clicks"]).any():
        raise ValueError("This schema requires conversions <= clicks <= impressions for every row.")
    if "currency" in frame:
        if frame["currency"].isna().any():
            raise ValueError("Currency must be present on every row when the column is supplied.")
        frame["currency"] = frame["currency"].astype(str).str.strip().str.upper()
        if frame["currency"].eq("").any() or frame["currency"].nunique() != 1:
            raise ValueError("Use one nonempty currency for the entire CSV; no currency conversion is performed.")
    return frame


def safe_ratio(numerator: float, denominator: float, multiplier: float = 1) -> float | None:
    """Zero denominators mean unavailable, not a misleading zero rate or cost."""
    return round(numerator / denominator * multiplier, 4) if denominator else None


def calculate_metrics(totals: dict) -> dict:
    if not all(math.isfinite(value) and value >= 0 for value in totals.values()):
        raise ValueError("Aggregated campaign totals exceed the supported numeric range.")
    impressions, clicks, conversions = (int(totals[column]) for column in COUNT_COLUMNS)
    spend = float(totals["spend"])
    revenue = float(totals["revenue"]) if "revenue" in totals else None
    return {
        "impressions": impressions, "clicks": clicks, "conversions": conversions,
        "spend": round(spend, 4), "revenue": round(revenue, 4) if revenue is not None else None,
        "ctr_percent": safe_ratio(clicks, impressions, 100),
        "conversion_rate_percent": safe_ratio(conversions, clicks, 100),
        "cost_per_click": safe_ratio(spend, clicks),
        "cost_per_conversion": safe_ratio(spend, conversions),
        "roas": safe_ratio(revenue, spend) if revenue is not None else None,
    }


def analyze_csv(filename: str, directory: Path = CAMPAIGN_DIRECTORY) -> dict:
    """Aggregate counts first, then calculate rates; never average row percentages."""
    path = resolve_csv(filename, directory)
    frame = load_campaign(path)
    columns = COUNT_COLUMNS + ["spend"] + (["revenue"] if "revenue" in frame else [])
    totals = calculate_metrics(frame[columns].sum().to_dict())
    grouped = frame.groupby("channel", sort=True)[columns].sum()
    channels = [{"channel": name, **calculate_metrics(row.to_dict())} for name, row in grouped.iterrows()]
    warnings = ["Observational totals do not establish causality or statistical significance."]
    if "revenue" not in frame:
        warnings.append("Revenue was not provided; ROAS is unavailable.")
    currency = frame["currency"].iloc[0] if "currency" in frame else None
    if currency is None:
        warnings.append("Currency was not provided; all monetary values are assumed to use one currency.")
    if any(item["cost_per_conversion"] is None for item in channels):
        warnings.append("Some channels have zero conversions; their cost per conversion is unavailable.")
    return {
        "source": f"data/campaigns/{path.relative_to(directory.resolve()).as_posix()}",
        "data_status": "fictional_demo" if path.name == "sample_campaign.csv" else "user_supplied_unverified",
        "rows": len(frame), "currency": currency, "totals": totals, "channels": channels,
        "definitions": {"ctr_percent": "clicks / impressions * 100",
                        "conversion_rate_percent": "conversions / clicks * 100",
                        "cost_per_click": "spend / clicks", "cost_per_conversion": "spend / conversions",
                        "roas": "revenue / spend; a ratio, not a percentage"},
        "warnings": warnings,
    }
