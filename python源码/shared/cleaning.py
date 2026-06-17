import pandas as pd

from .constants import REDUNDANT_COLUMN_KEYWORDS


def parse_numeric_column(series):
    """Strip commas and quotes, then convert to float."""
    return series.str.replace(',', '').str.strip('"').astype(float)


def apply_unit_conversion(df, col_qty, col_amt, qty_factor, rate, money_label):
    """Create cleaned quantity/amount columns with unit conversion applied."""
    df["数量_清洗后"] = parse_numeric_column(df[col_qty]) * qty_factor
    raw_amt = parse_numeric_column(df[col_amt])
    df["金额_清洗后"] = raw_amt * rate if money_label != "人民币" else raw_amt
    return df


def handle_missing_values(df, missing_opt):
    """Fill missing values with 0 or drop rows with missing values."""
    if missing_opt == "填充0":
        df["数量_清洗后"] = df["数量_清洗后"].fillna(0)
        df["金额_清洗后"] = df["金额_清洗后"].fillna(0)
    else:
        df = df.dropna(subset=["数量_清洗后", "金额_清洗后"])
    return df


def filter_by_product_code(df, col_code, inc_list, exc_list):
    """Filter rows by product code include/exclude lists."""
    if not (inc_list or exc_list):
        return df
    if col_code not in df.columns:
        return df
    mask = pd.Series([True] * len(df), index=df.index)
    if inc_list:
        mask &= df[col_code].astype(str).str.contains('|'.join(inc_list), na=False)
    if exc_list:
        mask &= ~df[col_code].astype(str).str.contains('|'.join(exc_list), na=False)
    return df[mask]


def rename_cleaned_columns(df, qty_label, money_label):
    """Rename intermediate cleaned columns to final display names."""
    return df.rename(columns={
        "数量_清洗后": f"数量({qty_label})",
        "金额_清洗后": f"金额({money_label})",
    })


def drop_redundant_columns(df, extra_cols=None):
    """Drop columns matching redundant keyword patterns, plus any extra named columns."""
    cols_to_drop = []
    for col in df.columns:
        for kw in REDUNDANT_COLUMN_KEYWORDS:
            if kw in col:
                cols_to_drop.append(col)
                break
    if extra_cols:
        for c in extra_cols:
            if c in df.columns and c not in cols_to_drop:
                cols_to_drop.append(c)
    if cols_to_drop:
        df = df.drop(columns=cols_to_drop)
    return df


def clean_single_file(df, col_qty, col_amt, qty_factor, rate, money_label,
                       missing_opt, col_code, inc_list, exc_list, dedup,
                       qty_dec=None, amt_dec=None):
    """Run the full cleaning pipeline on a single DataFrame.

    Returns the cleaned DataFrame, or None if required columns are missing.
    """
    if col_qty not in df.columns or col_amt not in df.columns:
        return None

    df = apply_unit_conversion(df, col_qty, col_amt, qty_factor, rate, money_label)

    if qty_dec is not None:
        df["数量_清洗后"] = df["数量_清洗后"].round(qty_dec)
    if amt_dec is not None:
        df["金额_清洗后"] = df["金额_清洗后"].round(amt_dec)

    df = handle_missing_values(df, missing_opt)
    df = filter_by_product_code(df, col_code, inc_list, exc_list)

    if dedup:
        df = df.drop_duplicates()

    return df
