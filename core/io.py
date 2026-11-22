# -*- coding: utf-8 -*-
"""统一的数据读取：自动识别 TickFlow K线 CSV、东财基金净值 CSV、Excel 等格式"""
import io
import os
import re
from pathlib import Path

import pandas as pd

from .config import FUND_MAPPING

DATE_KEYS = ["trade_date", "日期", "date", "datetime", "交易日期", "净值日期", "time"]
# 价格列优先级：累计净值 > 收盘 > 单位净值 > 其他
PRICE_KEYS = ["累计净值", "close", "收盘价", "收盘", "单位净值", "净值", "nav", "price", "Close"]


def _read_any(src, name: str) -> pd.DataFrame:
    """src 可以是路径或上传的文件对象（bytes）"""
    lower = name.lower()
    if lower.endswith((".xlsx", ".xls")):
        return pd.read_excel(src)
    raw = src.read() if hasattr(src, "read") else Path(src).read_bytes()
    for enc in ("utf-8-sig", "utf-8", "gbk", "gb18030"):
        try:
            return pd.read_csv(io.BytesIO(raw), encoding=enc)
        except (UnicodeDecodeError, pd.errors.ParserError):
            continue
    raise ValueError(f"无法识别文件编码：{name}")


def _find_col(columns, keys):
    cols = [str(c).strip() for c in columns]
    for k in keys:
        for c in cols:
            if c == k or c.lower() == k.lower():
                return c
    for k in keys:
        for c in cols:
            if k.lower() in c.lower():
                return c
    return None


def guess_name(filename: str, df: pd.DataFrame | None = None) -> str:
    stem = Path(filename).stem
    if df is not None and "name" in df.columns and df["name"].notna().any():
        nm = str(df["name"].dropna().iloc[0])
        code = guess_code(filename, df)
        return f"{nm}" if not code else f"{nm}({code})"
    m = re.search(r"(\d{6})", stem)
    if m and m.group(1) in FUND_MAPPING:
        return f"{FUND_MAPPING[m.group(1)]}({m.group(1)})"
    return stem


def guess_code(filename: str, df: pd.DataFrame | None = None) -> str:
    if df is not None and "symbol" in df.columns and df["symbol"].notna().any():
        return str(df["symbol"].dropna().iloc[0])
    m = re.search(r"(\d{6})", Path(filename).stem)
    return m.group(1) if m else Path(filename).stem


def load_price(src, name: str | None = None) -> dict:
    """读取任意行情/净值文件，返回标准化结果：
    {'df': DataFrame[date, price, (open, high, low)], 'name', 'code', 'price_label'}
    """
    name = name or (getattr(src, "name", None) or str(src))
    return standardize(_read_any(src, name), name)


def standardize(raw: pd.DataFrame, name: str = "data") -> dict:
    """把任意 DataFrame（如在线下载的 K 线）转成标准格式"""
    raw = raw.copy()
    raw.columns = [str(c).strip() for c in raw.columns]
    dcol = _find_col(raw.columns, DATE_KEYS)
    pcol = _find_col([c for c in raw.columns if c != dcol], PRICE_KEYS)
    if dcol is None or pcol is None:
        raise ValueError(f"{os.path.basename(name)}：无法识别日期列或价格列，现有列：{list(raw.columns)}")
    out = pd.DataFrame({
        "date": pd.to_datetime(raw[dcol], errors="coerce"),
        "price": pd.to_numeric(raw[pcol], errors="coerce"),
    })
    for k in ("open", "high", "low"):
        c = _find_col(raw.columns, [k, {"open": "开盘", "high": "最高", "low": "最低"}[k]])
        if c is not None and c != pcol:
            out[k] = pd.to_numeric(raw[c], errors="coerce")
    out = (out.dropna(subset=["date", "price"]).sort_values("date")
              .drop_duplicates("date", keep="last").reset_index(drop=True))
    if out.empty:
        raise ValueError(f"{os.path.basename(name)}：没有有效数据")
    return {"df": out, "name": guess_name(name, raw), "code": guess_code(name, raw), "price_label": pcol}


def is_price_file(path) -> bool:
    """只读表头，判断是否像行情/净值文件（有日期列 + 价格列）"""
    p = Path(path)
    try:
        if p.suffix.lower() == ".csv":
            head = None
            for enc in ("utf-8-sig", "gbk"):
                try:
                    head = pd.read_csv(p, nrows=0, encoding=enc)
                    break
                except UnicodeDecodeError:
                    continue
        else:
            head = pd.read_excel(p, nrows=0)
        if head is None:
            return False
        cols = [str(c).strip() for c in head.columns]
        d = _find_col(cols, DATE_KEYS)
        return d is not None and _find_col([c for c in cols if c != d], PRICE_KEYS) is not None
    except Exception:  # noqa: BLE001
        return False


def list_data_files(folder, price_only: bool = True) -> list[Path]:
    folder = Path(folder)
    if not folder.exists():
        return []
    files = [p for p in folder.iterdir() if p.is_file() and p.suffix.lower() in (".csv", ".xlsx", ".xls")
             and not p.name.startswith("~$")]
    if price_only:
        files = [p for p in files if is_price_file(p)]
    return sorted(files, key=lambda p: p.name)


def save_df(df: pd.DataFrame, folder, filename: str) -> Path:
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / filename
    df.to_csv(path, index=False, encoding="utf-8-sig")
    return path


def to_excel_bytes(sheets: dict) -> bytes:
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as w:
        for sheet, d in sheets.items():
            d.to_excel(w, sheet_name=sheet[:31], index=False)
    return buf.getvalue()
