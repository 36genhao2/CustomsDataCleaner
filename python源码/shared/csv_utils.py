import chardet
import pandas as pd


def read_csv_auto_encoding(path, sample_bytes=50000):
    """Read a CSV file with automatic encoding detection.

    Returns the DataFrame (all columns as str) and the detected encoding.
    """
    with open(path, 'rb') as f:
        enc = chardet.detect(f.read(sample_bytes))['encoding'] or 'gbk'
    df = pd.read_csv(path, dtype=str, encoding=enc)
    return df, enc


def save_csv_bom(df, path):
    """Save a DataFrame to CSV with UTF-8 BOM encoding."""
    df.to_csv(path, index=False, encoding='utf-8-sig')
