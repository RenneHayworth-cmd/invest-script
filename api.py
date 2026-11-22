# -*- coding: utf-8 -*-
"""面板业务逻辑层（与 Web 框架无关）。
每个公开函数接收普通参数，返回可 JSON 序列化的 dict；
带 _sheets=True 调用时返回用于导出 Excel 的 {类别: {工作表名: DataFrame}}。
"""
import base64
import json
import math
import re
import time
from datetime import date, datetime
from pathlib import Path

import numpy as np
import pandas as pd

from core import analytics as an
from core import backtest as bt
from core import fetchers as fe
from core import io as dio
from core.config import (CONTRACT_PREFIXES, DASHBOARD_DIR, DEFAULT_DATA_DIR, DEFAULT_OUTPUT_DIR,
                         FUND_MAPPING, INDEX_CONFIG, get_tickflow_key)

VERSION = "2.0"


# ================================================================ JSON 序列化
def J(v):
    """递归转换为 JSON 安全的 Python 对象：NaN/Inf -> None，日期 -> 'YYYY-MM-DD'，DataFrame -> 表格"""
    if v is None or v is pd.NaT:
        return None
    if isinstance(v, dict):
        return {str(k): J(x) for k, x in v.items()}
    if isinstance(v, (list, tuple, set)):
        return [J(x) for x in v]
    if isinstance(v, pd.DataFrame):
        return table(v)
    if isinstance(v, pd.Series):
        return [J(x) for x in v.tolist()]
    if isinstance(v, np.ndarray):
        return [J(x) for x in v.tolist()]
    if isinstance(v, (bool, np.bool_)):
        return bool(v)
    if isinstance(v, (int, np.integer)):
        return int(v)
    if isinstance(v, (float, np.floating)):
        f = float(v)
        return None if (math.isnan(f) or math.isinf(f)) else round(f, 6)
    if isinstance(v, np.datetime64):
        return None if np.isnat(v) else pd.Timestamp(v).strftime("%Y-%m-%d")
    if isinstance(v, (pd.Timestamp, datetime)):
        return None if pd.isna(v) else v.strftime("%Y-%m-%d")
    if isinstance(v, date):
        return v.isoformat()
    if isinstance(v, Path):
        return str(v)
    return v


def table(df: pd.DataFrame) -> dict:
    """DataFrame -> {'columns': [...], 'rows': [[...], ...]}（紧凑的列式表格）"""
    if df is None:
        return {"columns": [], "rows": []}
    return {"columns": [str(c) for c in df.columns],
            "rows": [[J(x) for x in row] for row in df.itertuples(index=False, name=None)]}


def _ser(s) -> list:
    return [J(x) for x in (s.tolist() if hasattr(s, "tolist") else list(s))]


def _dates(s) -> list:
    return pd.to_datetime(pd.Series(s)).dt.strftime("%Y-%m-%d").tolist()


def _stamp() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


# ================================================================ 设置
SETTINGS_FILE = DASHBOARD_DIR / "settings.json"
_settings = {"data_dir": str(DEFAULT_DATA_DIR), "output_dir": str(DEFAULT_OUTPUT_DIR)}
try:
    if SETTINGS_FILE.exists():
        _settings.update({k: v for k, v in json.loads(SETTINGS_FILE.read_text("utf-8")).items() if v})
except Exception:  # noqa: BLE001
    pass


def _data_dir() -> Path:
    return Path(_settings["data_dir"])


def _out_dir() -> Path:
    return Path(_settings["output_dir"])


def status() -> dict:
    d = _data_dir()
    return {"version": VERSION, "tickflow_key": bool(get_tickflow_key()), "data_dir": str(d),
            "data_dir_exists": d.exists(), "output_dir": str(_out_dir()),
            "file_count": len(dio.list_data_files(d)) if d.exists() else 0,
            "index_names": list(INDEX_CONFIG), "contract_prefixes": CONTRACT_PREFIXES}


def update_settings(data_dir: str | None = None, output_dir: str | None = None) -> dict:
    if data_dir:
        p = Path(data_dir.strip().strip('"'))
        if not p.exists():
            raise ValueError(f"数据文件夹不存在：{p}")
        _settings["data_dir"] = str(p)
    if output_dir:
        _settings["output_dir"] = str(Path(output_dir.strip().strip('"')))
    SETTINGS_FILE.write_text(json.dumps(_settings, ensure_ascii=False, indent=2), "utf-8")
    _cache.clear()
    return status()


# ================================================================ 文件
_cache: dict = {}


def _label(filename: str) -> str:
    lab = dio.guess_name(filename)
    for tag in ("后复权", "不复权"):
        if tag in filename and tag not in lab:
            lab += f"·{tag}"
    return lab


def files() -> dict:
    d = _data_dir()
    out, seen = [], {}
    for p in dio.list_data_files(d):
        st = p.stat()
        lab = _label(p.name)
        if lab in seen:
            lab = p.stem
        seen[lab] = 1
        out.append({"name": p.name, "label": lab, "size": st.st_size,
                    "mtime": datetime.fromtimestamp(st.st_mtime).strftime("%Y-%m-%d %H:%M")})
    return {"dir": str(d), "files": out}


def upload(name: str, content: str) -> dict:
    name = Path(str(name)).name
    if not name.lower().endswith((".csv", ".xlsx", ".xls")):
        raise ValueError("只支持 CSV / Excel 文件")
    raw = base64.b64decode(str(content).split(",")[-1])
    if len(raw) > 50 * 1024 * 1024:
        raise ValueError("文件超过 50MB")
    d = _data_dir()
    d.mkdir(parents=True, exist_ok=True)
    p = d / name
    existed = p.exists()
    p.write_bytes(raw)
    if not dio.is_price_file(p):
        p.unlink(missing_ok=True)
        raise ValueError(f"{name}：没有识别到日期列和价格列（收盘 / 净值），未保存")
    return {"name": name, "overwritten": existed}


def _load(name: str) -> dict:
    nm = Path(str(name)).name
    p = _data_dir() / nm
    if not p.is_file():
        raise ValueError(f"找不到文件：{nm}")
    key = (str(p), p.stat().st_mtime)
    if key not in _cache:
        if len(_cache) > 64:
            _cache.clear()
        _cache[key] = dio.load_price(p)
    return _cache[key]


def _load_many(names: list) -> list:
    """加载多个文件，保证显示名称唯一"""
    out, used = [], set()
    for i, n in enumerate(names or []):
        S = dict(_load(n))
        label = S["name"]
        for tag in ("后复权", "不复权"):
            if tag in n and tag not in label:
                label += f"·{tag}"
        if label in used:
            label = f"{label}·{Path(n).stem}"
        used.add(label)
        S["label"], S["file"] = label, n
        key = S["code"]
        S["key"] = key if all(o["key"] != key for o in out) else f"{key}#{i}"
        out.append(S)
    return out


def _filter(df: pd.DataFrame, start=None, end=None) -> pd.DataFrame:
    if start:
        df = df[df["date"] >= pd.Timestamp(start)]
    if end:
        df = df[df["date"] <= pd.Timestamp(end)]
    return df.reset_index(drop=True)


# ================================================================ 缓存（在线数据）
_ttl: dict = {}


def _cached(key, fn, ttl=1800, refresh=False):
    now = time.time()
    hit = _ttl.get(key)
    if hit and not refresh and now - hit[0] < ttl:
        return hit[1]
    v = fn()
    _ttl[key] = (now, v)
    return v


# ================================================================ 总览
def overview() -> dict:
    rows, curves = [], {}
    d = _data_dir()
    for f in (dio.list_data_files(d) if d.exists() else []):
        try:
            S = _load(f.name)
        except Exception:  # noqa: BLE001
            continue
        df = S["df"]
        px = df["price"]

        def ret(k):
            return px.iloc[-1] / px.iloc[-(k + 1)] - 1 if len(px) > k else None

        last_year = df["date"].iloc[-1].year
        prev = df.loc[df["date"].dt.year < last_year, "price"]
        ytd_base = prev.iloc[-1] if len(prev) else df.loc[df["date"].dt.year == last_year, "price"].iloc[0]
        r = an.rsi(px).iloc[-1]
        tail = df[df["date"] >= df["date"].iloc[-1] - pd.Timedelta(days=365)]
        step = max(1, len(tail) // 60)
        label = _label(f.name) if S["name"] == f.stem else S["name"]
        if any(x["name"] == label for x in rows):
            label = f"{label}·{f.stem}"
        rows.append({"file": f.name, "name": label, "code": S["code"], "last_date": df["date"].iloc[-1],
                     "last": px.iloc[-1], "r1m": ret(21), "r3m": ret(63), "ytd": px.iloc[-1] / ytd_base - 1,
                     "r1y": ret(252), "from_high": px.iloc[-1] / px.max() - 1, "rsi": r,
                     "spark": _ser(tail["price"].iloc[::step])})
        curves[label] = {"dates": _dates(tail["date"]),
                         "values": _ser((tail["price"] / tail["price"].iloc[0] - 1) * 100)}
    return {"rows": rows, "curves": curves, "data_dir": str(d)}


# ================================================================ 单品种分析
def single(file: str, start=None, end=None, years: int = 3, high_low: bool = True,
           ma=(20, 60, 120, 250), base_date: str = "2024-09-30", _sheets: bool = False):
    S = _load(file)
    full = S["df"]
    df = _filter(full, start, end)
    if len(df) < 30:
        raise ValueError("区间内数据不足 30 个交易日")
    years = int(years)
    ma = sorted({int(x) for x in (ma or []) if int(x) > 1}) or [20]
    has_hl = {"high", "low"}.issubset(df.columns) and bool(df[["high", "low"]].notna().all().all())
    roll = an.rolling_annualized(df, years)
    periods = an.drawdown_periods(df, use_high_low=bool(high_low) and has_hl)
    ytab = an.yearly_table(df)
    mad = an.moving_averages(df, ma)
    ind = an.indicator_table(df, base_date or "2024-09-30")

    if _sheets:
        roll_df = pd.DataFrame({"日期": df["date"].dt.date, "价格": df["price"],
                                f"{years}年滚动年化(%)": (roll * 100).round(4)})
        return {"roll": {"滚动年化": roll_df, "年度统计": ytab, "回撤波段": periods},
                "ma": {"均线数据": mad.assign(date=mad["date"].dt.date)},
                "rsi": {"每日完整数据": ind.assign(日期=ind["日期"].dt.date),
                        "最新一日摘要": ind.tail(1).assign(日期=ind["日期"].tail(1).dt.date)}}

    valid = roll.dropna()
    roll_stats = None
    if len(valid):
        roll_stats = {"latest": valid.iloc[-1], "max": valid.max(), "max_date": df["date"][valid.idxmax()],
                      "min": valid.min(), "min_date": df["date"][valid.idxmin()], "mean": valid.mean(),
                      "pos_ratio": (valid > 0).mean()}

    last = mad.iloc[-1]
    ma_latest = [{"n": n, "ma": last.get(f"MA{n}"), "dev": last.get(f"MA{n}偏离(%)")} for n in ma]
    vals = [x["ma"] for x in ma_latest]
    pattern = None
    if len(vals) >= 2 and all(pd.notna(v) for v in vals):
        if all(a > b for a, b in zip(vals, vals[1:])) and last["price"] > vals[0]:
            pattern = "多头排列"
        elif all(a < b for a, b in zip(vals, vals[1:])) and last["price"] < vals[0]:
            pattern = "空头排列"
        else:
            pattern = "交织震荡"

    li = ind.iloc[-1]
    base_col = next((c for c in ind.columns if str(c).startswith("自")), None)
    cur = None
    if not periods.empty:
        un = periods[~periods["是否已修复"]]
        if len(un):
            r = un.iloc[-1]
            cur = {"start": r["开始"], "trough": r["谷底"], "depth": r["回撤深度(%)"], "days": r["修复天数"]}

    return {
        "name": S["name"], "code": S["code"], "price_label": S["price_label"], "has_hl": has_hl,
        "range": {"min": full["date"].iloc[0], "max": full["date"].iloc[-1]},
        "start": df["date"].iloc[0], "end": df["date"].iloc[-1], "years": years,
        "stats": an.summary_stats(df),
        "series": {"dates": _dates(df["date"]), "price": _ser(df["price"]),
                   "drawdown": _ser(an.drawdown_series(df["price"]) * 100), "rolling": _ser(roll * 100)},
        "roll_stats": roll_stats,
        "yearly": ytab,
        "periods": periods.sort_values("回撤深度(%)").head(60) if len(periods) else periods,
        "top_periods": periods.nsmallest(5, "回撤深度(%)") if len(periods) else periods,
        "current_dd": cur,
        "ma": {"periods": ma, "lines": {f"MA{n}": _ser(mad[f"MA{n}"]) for n in ma},
               "latest": ma_latest, "pattern": pattern},
        "indicator": {
            "rsi": _ser(ind["RSI(14)"]), "pct": _ser(ind["价格百分位"]),
            "base_col": base_col,
            "latest": {"rsi": li["RSI(14)"], "status": li["状态"], "pct": li["价格百分位"],
                       "r20": li["20日涨幅(%)"], "r60": li["60日涨幅(%)"], "ytd": li["YTD涨幅(%)"],
                       "base": li[base_col] if base_col else None, "mv": li["动量/波动(20日)"],
                       "vol20": li["20日波动率(%)"]},
        },
        "indicator_table": ind.sort_values("日期", ascending=False).head(250),
    }


# ================================================================ SPMO
SPMO_METHODS = ("weighted", "equal", "standard")


def spmo(files: list, method: str = "weighted", top_n: int = 10, with_rsi: bool = True, _sheets: bool = False):
    if not files:
        raise ValueError("请至少选择一个品种")
    if method not in SPMO_METHODS:
        raise ValueError(f"未知评分方法：{method}")
    loaded = _load_many(files)
    allr, top = an.spmo_rank({S["label"]: S["df"] for S in loaded}, method, int(top_n), bool(with_rsi))
    if allr.empty:
        raise ValueError("没有可评分的品种（每个品种至少需要 30 个交易日）")
    if _sheets:
        return {"xlsx": {"最佳组合": top, "全部排名": allr}}
    show = allr.merge(top[["名称", "建议权重(%)"]], on="名称", how="left")
    scores = {"names": allr["名称"].tolist(), "total": _ser(allr["综合评分"])}
    if method != "standard":
        for k, c in (("s1", "SPMO(近1年)"), ("s6", "SPMO(近6月)"), ("s3", "SPMO(近3月)")):
            scores[k] = _ser(allr[c])
    hot = show.loc[show.get("RSI状态", pd.Series(dtype=str)) == "超买", "名称"].tolist() if with_rsi else []
    return {"method": method, "table": show, "scores": scores,
            "top": {"names": top["名称"].tolist(), "weights": _ser(top["建议权重(%)"])},
            "latest_date": max(allr["最新日期"]), "hot": hot}


# ================================================================ 回测
def _monthly(nav: pd.DataFrame) -> dict:
    s = nav.set_index("date")["value"]
    me = bt.month_end(s).dropna()
    r = me.pct_change() * 100
    if len(me):
        r.iloc[0] = (me.iloc[0] / s.iloc[0] - 1) * 100
    years = sorted(set(int(y) for y in me.index.year))
    data = [[int(ts.month) - 1, years.index(int(ts.year)), J(v)] for ts, v in r.items()]
    ye = s.groupby(s.index.year).last()
    prev = ye.shift(1)
    prev.iloc[0] = s.iloc[0]
    for y, v in ((ye / prev - 1) * 100).items():
        data.append([12, years.index(int(y)), J(v)])
    return {"years": [str(y) for y in years], "data": data}


def _bt_payload(R: dict, init: float, sheets: bool):
    m = R["metrics"]
    comp = pd.concat([pd.DataFrame([{"标的": "⭐ 轮动策略", "累计收益": m["累计收益"], "年化收益": m["年化收益"],
                                     "最大回撤": m["最大回撤"], "夏普比率": m["夏普比率"]}]),
                      R["bench_metrics"]], ignore_index=True)
    nav = R["nav"]
    if sheets:
        out = {"净值": nav.assign(date=nav["date"].dt.date), "调仓记录": R["trades"], "对比": comp}
        if R.get("yearly") is not None:
            out["年度表现"] = R["yearly"]
        return {"xlsx": out}
    return {
        "metrics": m, "init": init, "start": R["start"], "end": R["end"],
        "nav": {"dates": _dates(nav["date"]), "value": _ser(nav["value"] / init),
                "drawdown": _ser(nav["drawdown"] * 100), "holdings": nav["holdings"].tolist()},
        "bench": {k: {"dates": _dates(pd.Series(s.index)), "values": _ser(pd.Series(s.values) / init)}
                  for k, s in R["bench"].items()},
        "comparison": comp, "monthly": _monthly(nav),
        "holding": {"labels": R["holding_days"]["holdings"].tolist(), "values": _ser(R["holding_days"]["天数"])},
        "trades": R["trades"], "yearly": R.get("yearly"),
    }


def rotation(files: list, frequency: str = "week", lookback: int = 22, num_positions: int = 1,
             initial: float = 100000, fee_bp: float = 0.6, start=None, end=None, _sheets: bool = False):
    if not files or len(files) < 2:
        raise ValueError("至少选择 2 个品种进行轮动")
    loaded = _load_many(files)
    R = bt.rotation_backtest({S["key"]: S["df"] for S in loaded}, {S["key"]: S["label"] for S in loaded},
                             "month" if frequency == "month" else "week", int(lookback), int(num_positions),
                             float(initial), float(fee_bp) / 10000, start or None, end or None)
    return _bt_payload(R, float(initial), _sheets)


def _online(code: str, end):
    sym = fe.normalize_symbol(code)
    return _cached(("kl", sym, end), lambda: fe.tickflow_klines(sym, None, end or None, "backward"), ttl=1800)


def dual(source: str = "local", files: list | None = None, code1: str = "159915.SZ", code2: str = "510880.SH",
         lookback: int = 22, initial: float = 1_000_000, comm_bp: float = 0.6, slip_bp: float = 5,
         start=None, end=None, _sheets: bool = False):
    if source == "online":
        a, b = _online(code1, end), _online(code2, end)
        if a.empty or b.empty:
            raise RuntimeError("数据获取失败，请检查代码、网络或 TickFlow 密钥")
        A, B = dio.standardize(a, code1), dio.standardize(b, code2)
        A["label"], B["label"] = A["name"], B["name"]
    else:
        if not files or len(files) != 2:
            raise ValueError("请恰好选择两个品种")
        A, B = _load_many(files)
    n1, n2 = A["label"], B["label"]
    if n1 == n2:
        n2 = f"{n2}·2"
    R = bt.dual_momentum(A["df"], B["df"], n1, n2, int(lookback), float(initial), float(comm_bp) / 10000,
                         float(slip_bp) / 10000, start or None, end or None)
    return _bt_payload(R, float(initial), _sheets)


def save_report(kind: str, params: dict) -> dict:
    fn = {"rotation": rotation, "dual": dual}.get(kind)
    if fn is None:
        raise ValueError(f"未知报告类型：{kind}")
    sheets = fn(**{k: v for k, v in (params or {}).items() if not k.startswith("_")}, _sheets=True)["xlsx"]
    out = _out_dir() / f"轮动回测_{'多基金' if kind == 'rotation' else '双标的'}_{_stamp()}"
    out.mkdir(parents=True, exist_ok=True)
    for name, df in sheets.items():
        df.to_csv(out / f"{name}.csv", index=False, encoding="utf-8-sig")
    (out / "回测报告.xlsx").write_bytes(dio.to_excel_bytes(sheets))
    return {"path": str(out)}


# ================================================================ 数据下载
def _codes(text) -> list:
    if isinstance(text, (list, tuple)):
        text = ",".join(text)
    return [c.strip() for c in re.split(r"[\s,，;；]+", str(text or "")) if c.strip()]


def _safe_name(s: str) -> str:
    return re.sub(r'[\\/:*?"<>|\s]+', "", str(s))


def dl_tickflow(codes, market: str = "CN", adjust: str = "forward", start=None, end=None) -> dict:
    us = market == "US"
    syms = list(dict.fromkeys(fe.normalize_symbol(c, "US" if us else "auto") for c in _codes(codes)))
    if not syms:
        raise ValueError("请输入至少一个代码")
    adjust = adjust if adjust in ("forward", "backward", "none") else "forward"
    res = fe.tickflow_batch(syms, start or None, end or None, adjust)
    suffix = {"forward": "", "backward": "-后复权", "none": "-不复权"}[adjust]
    d = _data_dir()
    rows, curves = [], {}
    for s in syms:
        df, err = res.get(s, (None, "未执行"))
        if df is not None and len(df):
            code = s.split(".")[0]
            if us:
                fname = f"{code}_US{suffix}.csv"
            else:
                nm = str(df["name"].dropna().iloc[0]) if "name" in df.columns and df["name"].notna().any() \
                    else FUND_MAPPING.get(code, "")
                fname = f"{code}{_safe_name(nm)}{suffix}.csv"
            p = dio.save_df(df, d, fname)
            dd = df.sort_values("trade_date")
            rows.append({"代码": s, "状态": "成功", "条数": len(df),
                         "起止": f"{dd['trade_date'].iloc[0]:%Y-%m-%d} ~ {dd['trade_date'].iloc[-1]:%Y-%m-%d}",
                         "文件": p.name})
            curves[s] = {"dates": _dates(dd["trade_date"]), "values": _ser(dd["close"] / dd["close"].iloc[0])}
        else:
            rows.append({"代码": s, "状态": "失败", "条数": 0, "起止": "", "文件": err or ""})
    _cache.clear()
    return {"table": pd.DataFrame(rows), "curves": curves, "dir": str(d)}


def dl_fund(codes, latest_only: bool = False) -> dict:
    cs = _codes(codes)
    if not cs:
        raise ValueError("请输入至少一个基金代码")
    d = _data_dir()
    rows, previews = [], {}
    for c in cs:
        try:
            df = fe.fund_nav_history(c, latest_only=bool(latest_only))
            if df.empty:
                rows.append({"代码": c, "状态": "无数据", "条数": 0, "起止": "", "最新累计净值": None, "文件": ""})
                continue
            p = dio.save_df(df, d, f"fund_{c}.csv")
            rows.append({"代码": c, "状态": "成功", "条数": len(df),
                         "起止": f"{df['日期'].iloc[0]:%Y-%m-%d} ~ {df['日期'].iloc[-1]:%Y-%m-%d}",
                         "最新累计净值": df["累计净值"].iloc[-1], "文件": p.name})
            previews[c] = {"dates": _dates(df["日期"]), "nav": _ser(df["累计净值"]),
                           "dd": _ser(an.drawdown_series(df["累计净值"]) * 100)}
        except Exception as e:  # noqa: BLE001
            rows.append({"代码": c, "状态": "失败", "条数": 0, "起止": "", "最新累计净值": None, "文件": str(e)})
    _cache.clear()
    return {"table": pd.DataFrame(rows), "previews": previews, "dir": str(d)}


def board(board: str = "BK1158", top_n: int = 30, refresh: bool = False, _sheets: bool = False):
    b = (board or "BK1158").strip().upper()
    n = int(top_n)
    df = _cached(("board", b, n), lambda: fe.board_smallest(b, n), ttl=300, refresh=refresh and not _sheets)
    if df.empty:
        raise RuntimeError("没有返回数据，请检查板块代码或网络")
    if _sheets:
        return {"xlsx": {f"{b}_市值最小{len(df)}": df}}
    up = df["涨跌幅(%)"].dropna()
    return {"board": b, "table": df,
            "stats": {"count": len(df), "median": df["总市值(亿元)"].median(), "min": df["总市值(亿元)"].min(),
                      "min_name": df.iloc[0]["名称"], "up_ratio": (up > 0).mean() if len(up) else None}}


def board_save(board: str = "BK1158", top_n: int = 30) -> dict:
    b = (board or "BK1158").strip().upper()
    n = int(top_n)
    df = _cached(("board", b, n), lambda: fe.board_smallest(b, n), ttl=300)
    d = _data_dir()
    target = d.parent if d.name == "stock_data" else d
    p = dio.save_df(df, target, f"{b}_lowest_{len(df)}.csv")
    return {"path": str(p)}


# ================================================================ 指数 & 期货
def index_panel(names: list | None = None, ma: int = 20, days: int = 60, refresh: bool = False) -> dict:
    cfg = {n: INDEX_CONFIG[n] for n in (names or list(INDEX_CONFIG)) if n in INDEX_CONFIG}
    if not cfg:
        raise ValueError("请至少选择一个指数")
    ma, days = int(ma), int(days)
    fetch_days = int(days * 1.6 + ma * 2 + 10)
    data, errs = _cached(("idx", tuple(cfg), fetch_days, ma),
                         lambda: fe.index_ma20_panel(cfg, days=fetch_days, ma=ma), ttl=1800, refresh=refresh)
    series, latest, wide = {}, [], None
    for n, d in data.items():
        d = d.tail(days)
        series[n] = {"dates": _dates(d["date"]), "close": _ser(d["close"]), "ma": _ser(d["MA"]),
                     "bias": _ser(d["偏离率(%)"])}
        latest.append({"指数": n, "日期": d["date"].iloc[-1], "收盘": d["close"].iloc[-1],
                       f"MA{ma}": d["MA"].iloc[-1], "偏离率(%)": d["偏离率(%)"].iloc[-1]})
        part = d[["date", "close", "MA", "偏离率(%)"]].round(2)
        part.columns = ["日期", f"{n}_收盘价", f"{n}_MA{ma}", f"{n}_偏离率(%)"]
        wide = part if wide is None else wide.merge(part, on="日期", how="outer")
    if wide is not None:
        wide = wide.sort_values("日期").assign(日期=lambda x: x["日期"].dt.strftime("%Y-%m-%d"))
    return {"ma": ma, "days": days, "series": series, "latest": pd.DataFrame(latest), "errors": errs,
            "wide": wide}


def _cname(c: str) -> str:
    m = re.match(r"([A-Za-z]+)", c)
    n = CONTRACT_PREFIXES.get(m.group(1).upper(), "") if m else ""
    return f"{c.upper()}（{n}）" if n else c.upper()


def futures(contracts, base: str | None = None, refresh: bool = False) -> dict:
    cs = list(dict.fromkeys(c.upper() for c in _codes(contracts)))
    if len(cs) < 2:
        raise ValueError("至少输入两个合约")
    base = (base or cs[0]).strip().upper()
    if base not in cs:
        base = cs[0]
    res, info = _cached(("fut", tuple(cs), base), lambda: fe.futures_spread(cs, base), ttl=1800, refresh=refresh)
    others = [c for c in cs if c != base and c in res.columns]
    if res.empty or not others:
        raise ValueError("没有可对齐的共同交易日")
    stats = []
    for c in others:
        s, p = res[f"价差 {base}-{c}"], res[f"价差% {base}-{c}"]
        sd = s.std()
        stats.append({"价差": f"{_cname(base)} - {_cname(c)}", "最新": s.iloc[-1], "最新%": p.iloc[-1],
                      "均值": s.mean(), "均值%": p.mean(), "最大": s.max(), "最小": s.min(),
                      "当前分位": s.rank(pct=True).iloc[-1] * 100,
                      "Z值": (s.iloc[-1] - s.mean()) / sd if sd else 0})
    return {"base": base, "contracts": [c for c in cs if c in res.columns], "others": others,
            "names": {c: _cname(c) for c in cs}, "dates": _dates(res["date"]),
            "close": {c: _ser(res[c]) for c in cs if c in res.columns},
            "spread": {c: _ser(res[f"价差 {base}-{c}"]) for c in others},
            "spread_pct": {c: _ser(res[f"价差% {base}-{c}"]) for c in others},
            "stats": pd.DataFrame(stats).round(2), "errors": info["errors"],
            "ranges": {c: [a, z] for c, (a, z) in info["ranges"].items()},
            "table": res.assign(date=res["date"].dt.strftime("%Y-%m-%d"))}


# ================================================================ 导出
EXPORTABLE = {"single": single, "spmo": spmo, "rotation": rotation, "dual": dual, "board": board}


def export_xlsx(name: str, kind: str, params: dict) -> bytes:
    fn = EXPORTABLE.get(name)
    if fn is None:
        raise ValueError(f"不支持导出：{name}")
    sheets = fn(**{k: v for k, v in (params or {}).items() if not k.startswith("_")}, _sheets=True)
    sheets = sheets.get(kind) or sheets.get("xlsx")
    if not sheets:
        raise ValueError(f"没有可导出的内容：{kind}")
    return dio.to_excel_bytes(sheets)
