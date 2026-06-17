"""
Reusable data-cleaning utilities extracted from the CustomsCleaner GUI.

Every public function is pure (no Qt dependency) and operates on
pandas Series / DataFrames or plain Python objects.
"""

import os
from typing import List, Optional, Tuple

import chardet
import pandas as pd

# ── currency / unit look-ups ────────────────────────────────────────

EXCHANGE_RATES = {"美元": "0.14", "欧元": "0.13", "英镑": "0.11"}

QTY_FACTORS = {"千克": 1, "吨": 0.001, "克": 1000, "磅": 2.20462}

REDUNDANT_KEYWORDS = ["计量单位", "第二数量", "第二计", "Unnamed"]


def get_exchange_rate(currency: str) -> str:
    """Return the default exchange-rate string for *currency*, or '1'."""
    return EXCHANGE_RATES.get(currency, "1")


def get_qty_factor(unit: str) -> float:
    """Return the multiplication factor for the given weight *unit*."""
    return QTY_FACTORS[unit]


# ── file I/O ────────────────────────────────────────────────────────

def detect_encoding(path: str, sample_bytes: int = 50000) -> str:
    """Detect the character encoding of *path* (falls back to ``'gbk'``)."""
    with open(path, "rb") as fh:
        result = chardet.detect(fh.read(sample_bytes))
    return result["encoding"] or "gbk"


def read_csv_auto(path: str) -> pd.DataFrame:
    """Read a CSV with automatic encoding detection; all columns as ``str``."""
    enc = detect_encoding(path)
    return pd.read_csv(path, dtype=str, encoding=enc)


def collect_csv_paths(folder: str) -> List[str]:
    """Recursively collect all ``*.csv`` file paths under *folder*."""
    paths: List[str] = []
    for root, _dirs, files in os.walk(folder):
        for f in files:
            if f.lower().endswith(".csv"):
                paths.append(os.path.join(root, f))
    return paths


# ── column cleaning ─────────────────────────────────────────────────

def clean_numeric_series(series: pd.Series) -> pd.Series:
    """Strip commas and surrounding quotes, then cast to ``float``."""
    return series.str.replace(",", "").str.strip('"').astype(float)


def apply_unit_conversion(values: pd.Series, factor: float) -> pd.Series:
    """Multiply *values* by *factor* (unit conversion)."""
    return values * factor


def apply_currency_conversion(
    values: pd.Series,
    rate: float,
    is_local_currency: bool,
) -> pd.Series:
    """If not local currency, multiply by *rate*; otherwise pass through."""
    if is_local_currency:
        return values
    return values * rate


# ── filtering ───────────────────────────────────────────────────────

def filter_by_codes(
    df: pd.DataFrame,
    code_col: str,
    include: Optional[List[str]] = None,
    exclude: Optional[List[str]] = None,
) -> pd.DataFrame:
    """Keep / drop rows whose *code_col* contains any include/exclude pattern."""
    if code_col not in df.columns:
        return df
    if not include and not exclude:
        return df

    mask = pd.Series([True] * len(df), index=df.index)
    if include:
        mask &= df[code_col].astype(str).str.contains(
            "|".join(include), na=False
        )
    if exclude:
        mask &= ~df[code_col].astype(str).str.contains(
            "|".join(exclude), na=False
        )
    return df[mask]


# ── missing-value handling ──────────────────────────────────────────

def handle_missing(
    df: pd.DataFrame,
    columns: List[str],
    method: str = "fill_zero",
) -> pd.DataFrame:
    """Handle missing values in *columns*.

    *method*:
      - ``'fill_zero'``: fill NaN with 0
      - ``'drop'``: drop rows where any of *columns* is NaN
    """
    df = df.copy()
    if method == "fill_zero":
        for col in columns:
            df[col] = df[col].fillna(0)
    else:
        df = df.dropna(subset=columns)
    return df


# ── redundant-column removal ───────────────────────────────────────

def drop_redundant_columns(
    df: pd.DataFrame,
    keywords: Optional[List[str]] = None,
) -> pd.DataFrame:
    """Drop columns whose name contains any of the given *keywords*."""
    if keywords is None:
        keywords = REDUNDANT_KEYWORDS
    to_drop = [
        col
        for col in df.columns
        if any(kw in col for kw in keywords)
    ]
    return df.drop(columns=to_drop) if to_drop else df


# ── sorting ─────────────────────────────────────────────────────────

def sort_by_date(
    df: pd.DataFrame,
    date_col: str,
    date_format: str = "%Y%m",
) -> pd.DataFrame:
    """Sort *df* by *date_col* parsed with *date_format*."""
    if date_col not in df.columns:
        return df
    df = df.copy()
    df["__sort_date"] = pd.to_datetime(
        df[date_col], format=date_format, errors="coerce"
    )
    df = df.sort_values("__sort_date").reset_index(drop=True)
    df = df.drop(columns=["__sort_date"])
    return df


def multi_sort(
    df: pd.DataFrame,
    sort_spec: List[Tuple[str, bool]],
) -> pd.DataFrame:
    """Sort *df* by multiple columns.

    *sort_spec* is a list of ``(column, ascending)`` tuples.
    """
    if not sort_spec:
        return df
    by = [col for col, _ in sort_spec]
    ascending = [asc for _, asc in sort_spec]
    return df.sort_values(by=by, ascending=ascending).reset_index(drop=True)
