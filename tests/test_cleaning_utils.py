"""Unit tests for cleaning_utils – the extracted data-processing logic."""

import os
import tempfile

import pandas as pd
import pytest

from cleaning_utils import (
    EXCHANGE_RATES,
    QTY_FACTORS,
    REDUNDANT_KEYWORDS,
    apply_currency_conversion,
    apply_unit_conversion,
    clean_numeric_series,
    collect_csv_paths,
    detect_encoding,
    drop_redundant_columns,
    filter_by_codes,
    get_exchange_rate,
    get_qty_factor,
    handle_missing,
    multi_sort,
    read_csv_auto,
    sort_by_date,
)


# ── helpers ─────────────────────────────────────────────────────────

def _write_csv(path: str, content: str, encoding: str = "utf-8") -> None:
    with open(path, "w", encoding=encoding) as f:
        f.write(content)


# ── get_exchange_rate ───────────────────────────────────────────────

class TestGetExchangeRate:
    def test_usd(self):
        assert get_exchange_rate("美元") == "0.14"

    def test_eur(self):
        assert get_exchange_rate("欧元") == "0.13"

    def test_gbp(self):
        assert get_exchange_rate("英镑") == "0.11"

    def test_rmb_returns_default(self):
        assert get_exchange_rate("人民币") == "1"

    def test_unknown_currency(self):
        assert get_exchange_rate("日元") == "1"


# ── get_qty_factor ──────────────────────────────────────────────────

class TestGetQtyFactor:
    def test_kg(self):
        assert get_qty_factor("千克") == 1

    def test_ton(self):
        assert get_qty_factor("吨") == pytest.approx(0.001)

    def test_gram(self):
        assert get_qty_factor("克") == 1000

    def test_pound(self):
        assert get_qty_factor("磅") == pytest.approx(2.20462)

    def test_unknown_unit_raises(self):
        with pytest.raises(KeyError):
            get_qty_factor("盎司")


# ── detect_encoding ─────────────────────────────────────────────────

class TestDetectEncoding:
    def test_utf8_file(self, tmp_path):
        p = tmp_path / "utf8.csv"
        p.write_text("col1,col2\na,b\n", encoding="utf-8")
        enc = detect_encoding(str(p))
        assert enc.lower().replace("-", "") in ("utf8", "ascii", "utf8sig")

    def test_gbk_file(self, tmp_path):
        p = tmp_path / "gbk.csv"
        p.write_text("商品编码,金额\n12345,100\n", encoding="gbk")
        enc = detect_encoding(str(p))
        assert enc is not None

    def test_empty_file_falls_back(self, tmp_path):
        p = tmp_path / "empty.csv"
        p.write_bytes(b"")
        enc = detect_encoding(str(p))
        # chardet may return 'utf-8' or None for empty input; fallback is 'gbk'
        assert isinstance(enc, str)


# ── read_csv_auto ───────────────────────────────────────────────────

class TestReadCsvAuto:
    def test_reads_utf8(self, tmp_path):
        p = tmp_path / "data.csv"
        p.write_text("a,b\n1,2\n3,4\n", encoding="utf-8")
        df = read_csv_auto(str(p))
        assert list(df.columns) == ["a", "b"]
        assert len(df) == 2
        assert pd.api.types.is_string_dtype(df["a"])

    def test_reads_gbk(self, tmp_path):
        p = tmp_path / "data_gbk.csv"
        p.write_text("名称,数量\n苹果,10\n", encoding="gbk")
        df = read_csv_auto(str(p))
        assert "名称" in df.columns


# ── collect_csv_paths ───────────────────────────────────────────────

class TestCollectCsvPaths:
    def test_finds_csvs_recursively(self, tmp_path):
        (tmp_path / "a.csv").write_text("x")
        sub = tmp_path / "sub"
        sub.mkdir()
        (sub / "b.CSV").write_text("x")
        (sub / "c.txt").write_text("x")
        result = collect_csv_paths(str(tmp_path))
        basenames = sorted(os.path.basename(p) for p in result)
        assert basenames == ["a.csv", "b.CSV"]

    def test_empty_folder(self, tmp_path):
        assert collect_csv_paths(str(tmp_path)) == []


# ── clean_numeric_series ────────────────────────────────────────────

class TestCleanNumericSeries:
    def test_strips_commas(self):
        s = pd.Series(["1,000", "2,500.5", "300"])
        result = clean_numeric_series(s)
        assert list(result) == pytest.approx([1000.0, 2500.5, 300.0])

    def test_strips_quotes(self):
        s = pd.Series(['"100"', '"200"'])
        result = clean_numeric_series(s)
        assert list(result) == pytest.approx([100.0, 200.0])

    def test_combined(self):
        s = pd.Series(['"1,234.56"'])
        result = clean_numeric_series(s)
        assert result.iloc[0] == pytest.approx(1234.56)


# ── apply_unit_conversion ──────────────────────────────────────────

class TestApplyUnitConversion:
    def test_identity(self):
        s = pd.Series([10.0, 20.0])
        result = apply_unit_conversion(s, 1.0)
        assert list(result) == pytest.approx([10.0, 20.0])

    def test_to_tons(self):
        s = pd.Series([1000.0])
        result = apply_unit_conversion(s, 0.001)
        assert result.iloc[0] == pytest.approx(1.0)

    def test_to_grams(self):
        s = pd.Series([1.0])
        result = apply_unit_conversion(s, 1000)
        assert result.iloc[0] == pytest.approx(1000.0)


# ── apply_currency_conversion ──────────────────────────────────────

class TestApplyCurrencyConversion:
    def test_local_currency_passthrough(self):
        s = pd.Series([100.0, 200.0])
        result = apply_currency_conversion(s, 0.14, is_local_currency=True)
        assert list(result) == pytest.approx([100.0, 200.0])

    def test_foreign_currency(self):
        s = pd.Series([100.0])
        result = apply_currency_conversion(s, 0.14, is_local_currency=False)
        assert result.iloc[0] == pytest.approx(14.0)

    def test_rate_one(self):
        s = pd.Series([50.0])
        result = apply_currency_conversion(s, 1.0, is_local_currency=False)
        assert result.iloc[0] == pytest.approx(50.0)


# ── filter_by_codes ─────────────────────────────────────────────────

class TestFilterByCodes:
    @pytest.fixture()
    def df(self):
        return pd.DataFrame({
            "code": ["ABC123", "DEF456", "ABC789", "GHI000"],
            "val": [1, 2, 3, 4],
        })

    def test_include_only(self, df):
        result = filter_by_codes(df, "code", include=["ABC"])
        assert list(result["val"]) == [1, 3]

    def test_exclude_only(self, df):
        result = filter_by_codes(df, "code", exclude=["ABC"])
        assert list(result["val"]) == [2, 4]

    def test_include_and_exclude(self, df):
        result = filter_by_codes(df, "code", include=["ABC", "DEF"], exclude=["789"])
        assert list(result["val"]) == [1, 2]

    def test_no_filters_returns_same(self, df):
        result = filter_by_codes(df, "code")
        assert len(result) == 4

    def test_missing_column_returns_same(self, df):
        result = filter_by_codes(df, "nonexistent", include=["ABC"])
        assert len(result) == 4

    def test_empty_dataframe(self):
        df = pd.DataFrame({"code": pd.Series([], dtype=str), "val": pd.Series([], dtype=int)})
        result = filter_by_codes(df, "code", include=["ABC"])
        assert len(result) == 0


# ── handle_missing ──────────────────────────────────────────────────

class TestHandleMissing:
    def test_fill_zero(self):
        df = pd.DataFrame({"a": [1.0, None, 3.0], "b": [None, 2.0, None]})
        result = handle_missing(df, ["a", "b"], method="fill_zero")
        assert result["a"].tolist() == pytest.approx([1.0, 0.0, 3.0])
        assert result["b"].tolist() == pytest.approx([0.0, 2.0, 0.0])

    def test_drop(self):
        df = pd.DataFrame({"a": [1.0, None, 3.0], "b": [10.0, 20.0, None]})
        result = handle_missing(df, ["a", "b"], method="drop")
        assert len(result) == 1
        assert result.iloc[0]["a"] == pytest.approx(1.0)

    def test_does_not_mutate_original(self):
        df = pd.DataFrame({"a": [1.0, None]})
        handle_missing(df, ["a"], method="fill_zero")
        assert pd.isna(df.iloc[1]["a"])


# ── drop_redundant_columns ──────────────────────────────────────────

class TestDropRedundantColumns:
    def test_removes_matching(self):
        df = pd.DataFrame({
            "商品编码": [1],
            "计量单位": [2],
            "Unnamed: 0": [3],
            "金额": [4],
        })
        result = drop_redundant_columns(df)
        assert list(result.columns) == ["商品编码", "金额"]

    def test_custom_keywords(self):
        df = pd.DataFrame({"keep": [1], "drop_me": [2], "also_drop": [3]})
        result = drop_redundant_columns(df, keywords=["drop_me", "also_drop"])
        assert list(result.columns) == ["keep"]

    def test_no_matches(self):
        df = pd.DataFrame({"a": [1], "b": [2]})
        result = drop_redundant_columns(df)
        assert list(result.columns) == ["a", "b"]


# ── sort_by_date ────────────────────────────────────────────────────

class TestSortByDate:
    def test_sorts_yyyymm(self):
        df = pd.DataFrame({"date": ["202303", "202301", "202302"], "v": [3, 1, 2]})
        result = sort_by_date(df, "date")
        assert list(result["v"]) == [1, 2, 3]

    def test_missing_column_noop(self):
        df = pd.DataFrame({"v": [1, 2]})
        result = sort_by_date(df, "date")
        assert list(result["v"]) == [1, 2]

    def test_invalid_dates_coerced(self):
        df = pd.DataFrame({"date": ["202301", "INVALID", "202302"], "v": [1, 2, 3]})
        result = sort_by_date(df, "date")
        assert len(result) == 3

    def test_does_not_leave_helper_column(self):
        df = pd.DataFrame({"date": ["202301"], "v": [1]})
        result = sort_by_date(df, "date")
        assert "__sort_date" not in result.columns


# ── multi_sort ──────────────────────────────────────────────────────

class TestMultiSort:
    def test_single_column_asc(self):
        df = pd.DataFrame({"a": [3, 1, 2]})
        result = multi_sort(df, [("a", True)])
        assert list(result["a"]) == [1, 2, 3]

    def test_single_column_desc(self):
        df = pd.DataFrame({"a": [1, 3, 2]})
        result = multi_sort(df, [("a", False)])
        assert list(result["a"]) == [3, 2, 1]

    def test_multi_column(self):
        df = pd.DataFrame({"a": [1, 1, 2], "b": [20, 10, 30]})
        result = multi_sort(df, [("a", True), ("b", True)])
        assert list(result["b"]) == [10, 20, 30]

    def test_empty_spec(self):
        df = pd.DataFrame({"a": [3, 1, 2]})
        result = multi_sort(df, [])
        assert list(result["a"]) == [3, 1, 2]

    def test_resets_index(self):
        df = pd.DataFrame({"a": [3, 1, 2]})
        result = multi_sort(df, [("a", True)])
        assert list(result.index) == [0, 1, 2]


# ── integration: end-to-end cleaning pipeline ──────────────────────

class TestEndToEndPipeline:
    """Simulate the cleaning steps that CustomsCleaner.cleanAndMerge performs."""

    @pytest.fixture()
    def csv_file(self, tmp_path):
        content = (
            "数据年月,商品编码,商品名称,贸易伙伴名称,第一数量,人民币元\n"
            "202301,ABC001,Widget,Partner A,\"1,000\",\"5,000\"\n"
            "202302,ABC002,Gadget,Partner B,\"2,000\",\"10,000\"\n"
            "202301,DEF003,Thingamajig,Partner C,500,\"2,500\"\n"
            "202301,ABC001,Widget,Partner A,\"1,000\",\"5,000\"\n"  # duplicate
        )
        p = tmp_path / "trade.csv"
        p.write_text(content, encoding="utf-8")
        return str(p)

    def test_full_pipeline(self, csv_file):
        df = read_csv_auto(csv_file)
        assert len(df) == 4

        col_qty = "第一数量"
        col_amt = "人民币元"

        df[col_qty] = clean_numeric_series(df[col_qty])
        df[col_amt] = clean_numeric_series(df[col_amt])

        df["数量_cleaned"] = apply_unit_conversion(df[col_qty], get_qty_factor("千克"))
        df["金额_cleaned"] = apply_currency_conversion(
            df[col_amt], float(get_exchange_rate("美元")), is_local_currency=False
        )

        df = handle_missing(df, ["数量_cleaned", "金额_cleaned"], method="fill_zero")
        df = filter_by_codes(df, "商品编码", include=["ABC"])
        df = df.drop_duplicates()

        assert len(df) == 2  # ABC001 (deduped) + ABC002
        assert df["数量_cleaned"].iloc[0] == pytest.approx(1000.0)
        assert df["金额_cleaned"].iloc[0] == pytest.approx(700.0)  # 5000 * 0.14

    def test_pipeline_with_exclusion(self, csv_file):
        df = read_csv_auto(csv_file)
        df["第一数量"] = clean_numeric_series(df["第一数量"])
        df["人民币元"] = clean_numeric_series(df["人民币元"])
        df = filter_by_codes(df, "商品编码", exclude=["DEF"])
        df = df.drop_duplicates()
        assert len(df) == 2

    def test_pipeline_drop_missing(self, tmp_path):
        content = (
            "数据年月,第一数量,人民币元\n"
            "202301,100,200\n"
            "202302,,300\n"
            "202303,400,\n"
        )
        p = tmp_path / "missing.csv"
        p.write_text(content, encoding="utf-8")
        df = read_csv_auto(str(p))
        df["第一数量"] = pd.to_numeric(df["第一数量"], errors="coerce")
        df["人民币元"] = pd.to_numeric(df["人民币元"], errors="coerce")
        result = handle_missing(df, ["第一数量", "人民币元"], method="drop")
        assert len(result) == 1

    def test_pipeline_sort_and_drop_redundant(self, csv_file):
        df = read_csv_auto(csv_file)
        df["Unnamed: 0"] = range(len(df))
        df = drop_redundant_columns(df)
        assert "Unnamed: 0" not in df.columns
        df = sort_by_date(df, "数据年月")
        assert df.iloc[0]["数据年月"] == "202301"
