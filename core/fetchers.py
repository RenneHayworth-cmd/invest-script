# -*- coding: utf-8 -*-
"""在线数据获取（TickFlow / 东方财富 / AkShare / Yahoo）。
移植自 ETFdataget*.py、tickflow_USdata_fetcher.py、datagetfree.py、fund_complete_data_get.py、
jjjz.py、wpg*.py、Futures_Spread_Analysis.py、指数MA20分析工具_分列版.py
"""
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta

import pandas as pd
import requests

from .config import get_tickflow_key

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Safari/537.36"


# ------------------------------------------------------------------ TickFlow
def _tickflow_client(free_ok: bool = True):
    try:
        from tickflow import TickFlow
    except ImportError as e:
        raise RuntimeError("未安装 tickflow，请运行：pip install tickflow") from e
    key = get_tickflow_key()
    if key:
        return TickFlow(api_key=key)
    if free_ok and hasattr(TickFlow, "free"):
        return TickFlow.free()
    raise RuntimeError("未设置环境变量 TICKFLOW_API_KEY")


def _date_ms(date_str: str, end_of_day: bool = False) -> int:
    """YYYY-MM-DD -> 北京时间毫秒时间戳（与原 ETFdataget 口径一致）"""
    dt = datetime.strptime(str(date_str)[:10], "%Y-%m-%d")
    dt = dt.replace(hour=23, minute=59, second=59) if end_of_day else dt
    return int((dt - datetime(1970, 1, 1)).total_seconds() * 1000) - 8 * 3600 * 1000


def tickflow_klines(symbol: str, start: str | None = None, end: str | None = None,
                    adjust: str = "forward", count: int = 10000) -> pd.DataFrame:
    """日K线。adjust: forward 前复权 / backward 后复权 / none 不复权。
    start=None 表示"成立以来"。"""
    tf = _tickflow_client()
    kw = dict(period="1d", count=count, as_dataframe=True)
    if adjust and adjust != "none":
        kw["adjust"] = adjust
    if start:
        kw["start_time"] = _date_ms(start)
    if end:
        kw["end_time"] = _date_ms(end, end_of_day=True)
    try:
        df = tf.klines.get(symbol, **kw)
    except TypeError:
        # 免费版可能不支持部分参数，退化为只取最近 count 条
        df = tf.klines.get(symbol, period="1d", count=min(count, 2500), as_dataframe=True)
    if df is None or len(df) == 0:
        return pd.DataFrame()
    if "trade_date" not in df.columns and "timestamp" in df.columns:
        df["trade_date"] = pd.to_datetime(df["timestamp"], unit="ms") + pd.Timedelta(hours=8)
    df["trade_date"] = pd.to_datetime(df["trade_date"])
    if start:
        df = df[df["trade_date"] >= pd.Timestamp(start)]
    if end:
        df = df[df["trade_date"] <= pd.Timestamp(end)]
    return df.reset_index(drop=True)


def tickflow_batch(symbols: list[str], start=None, end=None, adjust="forward", workers: int = 4,
                   on_progress=None) -> dict:
    """并发批量下载，返回 {symbol: (df 或 None, 错误信息)}"""
    out = {}
    with ThreadPoolExecutor(max_workers=max(1, min(workers, len(symbols)))) as ex:
        futs = {ex.submit(tickflow_klines, s, start, end, adjust): s for s in symbols}
        for i, f in enumerate(as_completed(futs), 1):
            s = futs[f]
            try:
                df = f.result()
                out[s] = (df, None if len(df) else "未返回数据")
            except Exception as e:  # noqa: BLE001
                out[s] = (None, str(e))
            if on_progress:
                on_progress(i, len(symbols), s)
    return out


def normalize_symbol(code: str, market: str = "auto") -> str:
    """'512890' -> '512890.SH'；'159915' -> '159915.SZ'；美股 'SPMO' -> 'SPMO.US'"""
    c = code.strip().upper()
    if not c:
        return c
    if "." in c:
        return c
    if market == "US" or not c.isdigit():
        return f"{c}.US"
    if c.startswith(("5", "6", "9")):
        return f"{c}.SH"
    if c.startswith(("8", "4")):
        return f"{c}.BJ"
    return f"{c}.SZ"


# ------------------------------------------------------------------ 东方财富 场外基金净值
_NAV_URL = "http://api.fund.eastmoney.com/f10/lsjz"


def _nav_headers(code):
    return {"User-Agent": UA, "Referer": f"https://fundf10.eastmoney.com/jjjz_{code}.html"}


def _nav_page(code: str, page: int, size: int = 20) -> list:
    r = requests.get(_NAV_URL, params={"fundCode": code, "pageIndex": page, "pageSize": size},
                     headers=_nav_headers(code), timeout=10)
    r.raise_for_status()
    data = r.json()
    if data.get("ErrCode") not in (0, None):
        return []
    return (data.get("Data") or {}).get("LSJZList") or []


def fund_nav_total(code: str) -> int:
    r = requests.get(_NAV_URL, params={"fundCode": code, "pageIndex": 1, "pageSize": 1},
                     headers=_nav_headers(code), timeout=8)
    r.raise_for_status()
    return int(r.json().get("TotalCount") or 0)


def fund_nav_history(code: str, latest_only: bool = False, workers: int = 12) -> pd.DataFrame:
    """场外基金历史净值：日期、单位净值、累计净值、日增长率"""
    code = code.strip()
    if latest_only:
        items = _nav_page(code, 1, 20)
    else:
        total = fund_nav_total(code)
        if total <= 0:
            return pd.DataFrame()
        size = 20
        pages = (total + size - 1) // size
        items = []
        with ThreadPoolExecutor(max_workers=min(workers, pages)) as ex:
            futs = [ex.submit(_nav_page, code, p, size) for p in range(1, pages + 1)]
            for f in as_completed(futs):
                try:
                    items.extend(f.result())
                except Exception:  # noqa: BLE001
                    pass
            time.sleep(0.01)
    rows = [{"日期": it.get("FSRQ"), "单位净值": it.get("DWJZ"), "累计净值": it.get("LJJZ"),
             "日增长率(%)": it.get("JZZZL")} for it in items if it.get("FSRQ")]
    df = pd.DataFrame(rows)
    if df.empty:
        return df
    df["日期"] = pd.to_datetime(df["日期"])
    for c in ("单位净值", "累计净值", "日增长率(%)"):
        df[c] = pd.to_numeric(df[c], errors="coerce")
    df = df.dropna(subset=["累计净值"]).drop_duplicates("日期").sort_values("日期").reset_index(drop=True)
    df.insert(0, "基金代码", code)
    return df


# ------------------------------------------------------------------ 东方财富 板块成分（微盘股 BK1158）
def board_smallest(board: str = "BK1158", top_n: int = 30) -> pd.DataFrame:
    params = {"pn": 1, "pz": 500, "po": 0, "np": 1, "fltt": 2, "invt": 2, "fid": "f20",
              "fs": f"b:{board}", "fields": "f12,f14,f2,f3,f20"}
    headers = {"User-Agent": UA, "Referer": "https://quote.eastmoney.com/"}
    last = None
    for _ in range(3):
        try:
            r = requests.get("https://push2.eastmoney.com/api/qt/clist/get", params=params,
                             headers=headers, timeout=15)
            r.raise_for_status()
            data = r.json()
            break
        except Exception as e:  # noqa: BLE001
            last = e
            time.sleep(1)
    else:
        raise RuntimeError(f"请求失败（已重试 3 次）：{last}")
    rows = []
    for s in (data.get("data") or {}).get("diff") or []:
        mv = pd.to_numeric(s.get("f20"), errors="coerce")
        if pd.notna(mv) and mv > 0:
            rows.append({"代码": s.get("f12"), "名称": s.get("f14"),
                         "最新价": pd.to_numeric(s.get("f2"), errors="coerce"),
                         "涨跌幅(%)": pd.to_numeric(s.get("f3"), errors="coerce"),
                         "总市值(亿元)": round(mv / 1e8, 2)})
    df = pd.DataFrame(rows)
    if df.empty:
        return df
    df = df.sort_values("总市值(亿元)").head(top_n).reset_index(drop=True)
    df.insert(0, "排名", range(1, len(df) + 1))
    return df


def _ak():
    try:
        import akshare as ak
    except ImportError as e:
        raise RuntimeError("未安装 akshare，请运行：pip install akshare") from e
    return ak


# ------------------------------------------------------------------ 期货（AkShare 新浪）
def futures_daily(contract: str) -> pd.DataFrame:
    ak = _ak()
    df = ak.futures_zh_daily_sina(symbol=contract)
    if df is None or df.empty:
        return pd.DataFrame()
    df = df[["date", "close"]].copy()
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df["close"] = pd.to_numeric(df["close"], errors="coerce")
    return df.dropna().sort_values("date").reset_index(drop=True)


def futures_spread(contracts: list[str], base: str | None = None) -> tuple[pd.DataFrame, dict]:
    """并行拉取多个合约，计算 价差 = 基准 - 其他（共同交易日对齐）"""
    base = base or contracts[0]
    data, errors = {}, {}
    with ThreadPoolExecutor(max_workers=min(6, len(contracts))) as ex:
        futs = {ex.submit(futures_daily, c): c for c in contracts}
        for f in as_completed(futs):
            c = futs[f]
            try:
                d = f.result()
                if d.empty:
                    errors[c] = "返回空数据"
                else:
                    data[c] = d
            except Exception as e:  # noqa: BLE001
                errors[c] = str(e)
    if base not in data:
        raise RuntimeError(f"基准合约 {base} 获取失败：{errors.get(base, '未知错误')}")
    res = data[base].rename(columns={"close": base})
    for c in contracts:
        if c != base and c in data:
            res = res.merge(data[c].rename(columns={"close": c}), on="date", how="inner")
    for c in contracts:
        if c != base and c in res.columns:
            res[f"价差 {base}-{c}"] = res[base] - res[c]
            res[f"价差% {base}-{c}"] = (res[f"价差 {base}-{c}"] / res[base] * 100).round(4)
    ranges = {c: (d["date"].min().date(), d["date"].max().date()) for c, d in data.items()}
    return res.sort_values("date").reset_index(drop=True), {"errors": errors, "ranges": ranges}


# ------------------------------------------------------------------ 指数（TickFlow + AkShare 兜底）
def _norm_index(df: pd.DataFrame) -> pd.DataFrame:
    ren = {}
    for c in df.columns:
        t = str(c).strip()
        if t in {"日期", "date", "trade_date", "交易日期"}:
            ren[c] = "date"
        elif t in {"收盘", "收盘价", "close", "Close"}:
            ren[c] = "close"
    d = df.rename(columns=ren)
    if "date" not in d or "close" not in d:
        raise ValueError(f"无法识别指数数据列：{list(df.columns)}")
    d = d[["date", "close"]].copy()
    d["date"] = pd.to_datetime(d["date"], errors="coerce")
    d["close"] = pd.to_numeric(d["close"], errors="coerce")
    return d.dropna().sort_values("date").reset_index(drop=True)


def _akshare_csindex(code: str) -> pd.DataFrame:
    ak = _ak()
    s = (datetime.now() - timedelta(days=400)).strftime("%Y%m%d")
    e = datetime.now().strftime("%Y%m%d")
    attempts = [
        lambda: ak.stock_zh_index_hist_csindex(symbol=code, start_date=s, end_date=e),
        lambda: ak.stock_zh_index_daily(symbol=code.lower()),
        lambda: ak.stock_zh_index_daily_em(symbol=f"csi{code}"),
    ]
    errs = []
    for fn in attempts:
        try:
            raw = fn()
            if raw is not None and not raw.empty:
                d = _norm_index(raw)
                return _append_latest(ak, d, code)
        except Exception as ex:  # noqa: BLE001
            errs.append(str(ex))
    raise RuntimeError("AkShare 未获取到数据：" + " | ".join(errs))


def _append_latest(ak, d: pd.DataFrame, code: str) -> pd.DataFrame:
    """中证历史接口有时滞后一天，用实时行情 / Yahoo 补当日价"""
    today = pd.Timestamp(datetime.now().date())
    if d["date"].max() >= today:
        return d
    price = None
    try:
        spot = ak.stock_zh_index_spot_em(symbol="中证系列指数")
        m = spot[spot["代码"].astype(str).str.upper() == code.upper()]
        if not m.empty:
            price = pd.to_numeric(m.iloc[0].get("最新价"), errors="coerce")
    except Exception:  # noqa: BLE001
        pass
    if price is not None and pd.notna(price):
        return pd.concat([d, pd.DataFrame([{"date": today, "close": float(price)}])], ignore_index=True)
    try:
        r = requests.get(f"https://query1.finance.yahoo.com/v8/finance/chart/{code}.SS",
                         params={"range": "10d", "interval": "1d"}, headers={"User-Agent": UA}, timeout=10)
        item = r.json()["chart"]["result"][0]
        pairs = [(t, c) for t, c in zip(item.get("timestamp") or [],
                                        item["indicators"]["quote"][0].get("close") or []) if c is not None]
        if pairs:
            t, c = pairs[-1]
            dt = pd.Timestamp(datetime.fromtimestamp(t).date())
            if dt > d["date"].max():
                return pd.concat([d, pd.DataFrame([{"date": dt, "close": float(c)}])], ignore_index=True)
    except Exception:  # noqa: BLE001
        pass
    return d


def index_daily(cfg) -> pd.DataFrame:
    """cfg: 'XXXXXX.SH' 或 {'source': 'akshare_csindex'|'akshare_us', 'code': ...}"""
    if isinstance(cfg, dict):
        src, code = cfg.get("source"), cfg.get("code")
        if src == "akshare_csindex":
            return _akshare_csindex(code)
        if src == "akshare_us":
            ak = _ak()
            return _norm_index(ak.index_us_stock_sina(symbol=code))
        cfg = code
    df = tickflow_klines(cfg, start=(datetime.now() - timedelta(days=500)).strftime("%Y-%m-%d"),
                         adjust="none")
    if df.empty:
        raise RuntimeError("TickFlow 未返回数据")
    return _norm_index(df.rename(columns={"trade_date": "date"}))


def index_ma20_panel(config: dict, days: int = 60, ma: int = 20) -> tuple[dict, dict]:
    """返回 ({指数名: df[date, close, MA, 偏离率]}, {指数名: 错误})"""
    out, errs = {}, {}
    with ThreadPoolExecutor(max_workers=4) as ex:
        futs = {ex.submit(index_daily, cfg): name for name, cfg in config.items()}
        for f in as_completed(futs):
            name = futs[f]
            try:
                d = f.result()
                d["MA"] = d["close"].rolling(ma).mean()
                d["偏离率(%)"] = (d["close"] - d["MA"]) / d["MA"] * 100
                d = d[d["date"] >= pd.Timestamp(datetime.now() - timedelta(days=days))]
                if d.empty:
                    errs[name] = f"最近 {days} 天无数据"
                else:
                    out[name] = d.reset_index(drop=True)
            except Exception as e:  # noqa: BLE001
                errs[name] = str(e)
    ordered = {k: out[k] for k in config if k in out}
    return ordered, errs
