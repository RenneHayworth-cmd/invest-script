# -*- coding: utf-8 -*-
"""单品种分析算法（移植自 fund_analysis_gui_fixed / ETF-3-Year / 均线 / RSI / SPMO 系列脚本）
所有函数输入标准化 DataFrame：列 date, price, [open, high, low]
"""
import numpy as np
import pandas as pd


# ---------------------------------------------------------------- 滚动年化收益
def rolling_annualized(df: pd.DataFrame, years: int = 3) -> pd.Series:
    """N 年滚动年化收益率（与原脚本口径一致：取 N*365 天前最近一个交易日，按实际天数年化）。
    原脚本为逐行循环，这里改为 merge_asof 向量化，结果相同、速度快很多。"""
    d = df[["date", "price"]].copy()
    d["target"] = d["date"] - pd.Timedelta(days=years * 365)
    past = d[["date", "price"]].rename(columns={"date": "past_date", "price": "past_price"})
    m = pd.merge_asof(d.sort_values("target"), past.sort_values("past_date"),
                      left_on="target", right_on="past_date", direction="backward")
    m = m.sort_values("date")
    days = (m["date"] - m["past_date"]).dt.days
    total = m["price"] / m["past_price"] - 1
    ann = (1 + total) ** (365 / days) - 1
    ann[days <= 0] = np.nan
    return pd.Series(ann.values, index=df.index, name=f"{years}年滚动年化")


# ---------------------------------------------------------------- 回撤
def drawdown_series(price: pd.Series) -> pd.Series:
    peak = price.cummax()
    return (price - peak) / peak


def _drawdown_one(sub: pd.DataFrame) -> dict:
    nav = sub["price"].values
    dates = sub["date"].values
    if len(nav) < 2:
        return {"年度最大回撤(%)": np.nan, "最大回撤日期": None, "修复天数": np.nan, "是否已修复": False}
    rm = np.maximum.accumulate(nav)
    dd = (nav - rm) / rm * 100
    i = int(np.argmin(dd))
    peak_nav = rm[i]
    rec = None
    for j in range(i + 1, len(nav)):
        if nav[j] >= peak_nav:
            rec = j
            break
    return {
        "年度最大回撤(%)": round(float(dd[i]), 2),
        "最大回撤日期": pd.Timestamp(dates[i]).date(),
        "修复天数": int((dates[rec] - dates[i]) / np.timedelta64(1, "D")) if rec is not None else np.nan,
        "是否已修复": rec is not None,
    }


def yearly_table(df: pd.DataFrame) -> pd.DataFrame:
    """年度涨幅 + 年内最大回撤 + 修复时间"""
    d = df.copy()
    d["年份"] = d["date"].dt.year
    rows = []
    for y, g in d.groupby("年份"):
        if len(g) < 2:
            continue
        s, e = g["price"].iloc[0], g["price"].iloc[-1]
        row = {"年份": int(y), "年初": round(s, 4), "年末": round(e, 4),
               "年度涨幅(%)": round((e / s - 1) * 100, 2),
               "年内最高": round(g["price"].max(), 4), "年内最低": round(g["price"].min(), 4)}
        row.update(_drawdown_one(g))
        rows.append(row)
    return pd.DataFrame(rows)


def drawdown_periods(df: pd.DataFrame, use_high_low: bool = False) -> pd.DataFrame:
    """提取所有回撤波段。
    use_high_low=False：基于收盘/净值 running max（场外基金脚本口径）
    use_high_low=True ：基于 K 线最高/最低价识别波段（ETF 脚本口径）"""
    d = df.sort_values("date").reset_index(drop=True)
    dates = d["date"].values
    hl = use_high_low and {"high", "low"}.issubset(d.columns) and d[["high", "low"]].notna().all().all()
    highs = d["high"].values if hl else d["price"].values
    lows = d["low"].values if hl else d["price"].values
    out = []
    peak_v, peak_d = highs[0], dates[0]
    in_dd, t_idx, t_v = False, -1, 0.0

    def _days(a, b):
        return int((b - a) / np.timedelta64(1, "D"))

    for i in range(len(d)):
        h, l = highs[i], lows[i]
        if not in_dd:
            if h < peak_v:
                in_dd, t_v, t_idx = True, l, i
            elif h > peak_v:
                peak_v, peak_d = h, dates[i]
        else:
            if h >= peak_v:
                out.append({"开始": peak_d, "谷底": dates[t_idx], "修复完成": dates[i],
                            "回撤深度(%)": round((t_v - peak_v) / peak_v * 100, 2),
                            "下跌天数": _days(peak_d, dates[t_idx]), "修复天数": _days(dates[t_idx], dates[i]),
                            "是否已修复": True})
                in_dd, peak_v, peak_d = False, h, dates[i]
            elif l < t_v:
                t_v, t_idx = l, i
    if in_dd:
        out.append({"开始": peak_d, "谷底": dates[t_idx], "修复完成": pd.NaT,
                    "回撤深度(%)": round((t_v - peak_v) / peak_v * 100, 2),
                    "下跌天数": _days(peak_d, dates[t_idx]), "修复天数": _days(dates[t_idx], dates[-1]),
                    "是否已修复": False})
    res = pd.DataFrame(out)
    if not res.empty:
        for c in ("开始", "谷底", "修复完成"):
            res[c] = pd.to_datetime(res[c]).dt.date
    return res


def summary_stats(df: pd.DataFrame) -> dict:
    p = df["price"]
    days = (df["date"].iloc[-1] - df["date"].iloc[0]).days
    total = p.iloc[-1] / p.iloc[0] - 1
    ann = (1 + total) ** (365 / days) - 1 if days > 0 else np.nan
    vol = p.pct_change().std() * np.sqrt(252)
    dd = drawdown_series(p)
    return {"起始日": df["date"].iloc[0].date(), "最新日": df["date"].iloc[-1].date(), "最新价": p.iloc[-1],
            "区间涨幅": total, "年化收益": ann, "年化波动": vol, "最大回撤": dd.min(),
            "当前回撤": dd.iloc[-1], "交易日数": len(df)}


# ---------------------------------------------------------------- 均线
def moving_averages(df: pd.DataFrame, periods=(20, 60, 120, 250)) -> pd.DataFrame:
    d = df[["date", "price"]].copy()
    for n in periods:
        d[f"MA{n}"] = d["price"].rolling(n).mean()
        d[f"MA{n}偏离(%)"] = (d["price"] - d[f"MA{n}"]) / d[f"MA{n}"] * 100
    return d


# ---------------------------------------------------------------- RSI & 百分位
def rsi(price: pd.Series, n: int = 14) -> pd.Series:
    delta = price.diff()
    gain = delta.where(delta > 0, 0).rolling(n).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(n).mean()
    return 100 - 100 / (1 + gain / loss)


def rsi_status(v) -> str:
    if pd.isna(v):
        return "数据不足"
    return "超买" if v > 70 else ("超卖" if v < 30 else "正常")


def indicator_table(df: pd.DataFrame, base_date: str = "2024-09-30") -> pd.DataFrame:
    """逐日指标（移植自 fund_RSI&percentile_analyzer.py）"""
    p = df["price"]
    d = pd.DataFrame({"日期": df["date"], "价格": p})
    d["日涨跌(%)"] = p.pct_change() * 100
    d["20日涨幅(%)"] = (p / p.shift(20) - 1) * 100
    d["60日涨幅(%)"] = (p / p.shift(60) - 1) * 100
    d["20日波动率(%)"] = p.pct_change().rolling(20).std() * 100
    vol = d["20日波动率(%)"] / 100
    d["动量/波动(20日)"] = np.where(vol > 0, (d["20日涨幅(%)"] / 100) / vol, 0)
    d["RSI(14)"] = rsi(p)
    d["状态"] = d["RSI(14)"].apply(rsi_status)
    d["价格百分位"] = p.expanding().rank(pct=True) * 100
    first = d.groupby(d["日期"].dt.year)["价格"].transform("first")
    d["YTD涨幅(%)"] = (p / first - 1) * 100
    bd = pd.Timestamp(base_date)
    mask = d["日期"] >= bd
    if mask.any():
        base_price = p[mask].iloc[0]
        d[f"自{bd:%Y%m%d}涨幅(%)"] = np.where(mask, (p / base_price - 1) * 100, np.nan)
    num_cols = d.select_dtypes("number").columns
    d[num_cols] = d[num_cols].round(4)
    return d


# ---------------------------------------------------------------- SPMO 评分
def _ann_vol(prices: pd.Series, window: int = 250) -> float:
    r = prices.pct_change().dropna()
    if len(r) < 5:
        return np.nan
    v = r.tail(min(window, len(r))).std() * np.sqrt(252)
    return v if v and not np.isnan(v) else 0.0001


def _period_score(prices, lag, back, ann_days, vol, fallback):
    """剔除最近 lag 天，回看 back 天的风险调整动量"""
    n = len(prices)
    if n >= back + 1:
        p_end, p_start = prices.iloc[-(lag + 1)], prices.iloc[-(back + 1)]
        if p_start:
            return ((p_end / p_start) - 1) * (252 / ann_days) / vol, "标准"
    return fallback, "成立以来"


def spmo_score(prices: pd.Series, method: str = "weighted") -> dict:
    """method:
      standard  -> 标准 SPMO：12-1 月动量 / 年化波动（数据不足 1 年用成立以来）      (SPMO.py)
      equal     -> 1年/6月/3月 三周期等权平均                                     (SPMO多周期.py)
      weighted  -> 三周期 40%/35%/25% 加权                                          (SPMO多周期403525加权.py / SPMO+RSI.py)
    """
    prices = prices.dropna().reset_index(drop=True)
    n = len(prices)
    vol = _ann_vol(prices)
    total = prices.iloc[-1] / prices.iloc[0] - 1
    s_inc = total * (252 / n) / vol
    res = {"年化波动(%)": round(vol * 100, 2), "数据天数": n}
    if method == "standard":
        if n >= 253:
            vol1 = prices.pct_change().rolling(250).std().iloc[-1] * np.sqrt(252)
            sc = ((prices.iloc[-22] / prices.iloc[-253]) - 1) * (252 / 231) / vol1
            res.update({"综合评分": sc, "口径": "标准(12-1月)", "年化波动(%)": round(vol1 * 100, 2)})
        else:
            vol0 = prices.pct_change().std() * np.sqrt(252)
            res.update({"综合评分": total * (252 / n) / vol0, "口径": f"新基金({n}天)"})
        return res
    s1, b1 = _period_score(prices, 21, 252, 231, vol, s_inc)
    # ann_days 必须等于实际区间长度 back - lag：1年 252-21=231，6月 137-11=126，3月 68-5=63
    s6, b6 = _period_score(prices, 11, 137, 126, vol, s_inc)
    s3, b3 = _period_score(prices, 5, 68, 63, vol, s_inc)
    final = (s1 + s6 + s3) / 3 if method == "equal" else s1 * 0.4 + s6 * 0.35 + s3 * 0.25
    res.update({"SPMO(近1年)": s1, "SPMO(近6月)": s6, "SPMO(近3月)": s3, "综合评分": final,
                "口径": "/".join("标" if b == "标准" else "成" for b in (b1, b6, b3))})
    return res


def spmo_rank(series_map: dict, method: str = "weighted", top_n: int = 10, with_rsi: bool = True) -> tuple:
    """series_map: {名称: 标准化df}。返回 (全部排名, 前N组合及建议权重)"""
    rows = []
    for name, df in series_map.items():
        p = df["price"].dropna()
        if len(p) < 30:
            continue
        r = {"名称": name, "最新日期": df["date"].iloc[-1].date(), "最新价": round(p.iloc[-1], 4)}
        r.update(spmo_score(p, method))
        for lbl, k in (("近1月", 21), ("近3月", 63), ("近6月", 126), ("近1年", 252)):
            r[f"涨幅{lbl}(%)"] = round((p.iloc[-1] / p.iloc[-(k + 1)] - 1) * 100, 2) if len(p) > k else np.nan
        if with_rsi:
            v = rsi(p).iloc[-1]
            r["RSI(14)"] = round(v, 2) if not pd.isna(v) else np.nan
            r["RSI状态"] = rsi_status(v)
        rows.append(r)
    if not rows:
        return pd.DataFrame(), pd.DataFrame()
    allr = pd.DataFrame(rows).sort_values("综合评分", ascending=False).reset_index(drop=True)
    for c in ("综合评分", "SPMO(近1年)", "SPMO(近6月)", "SPMO(近3月)"):
        if c in allr:
            allr[c] = allr[c].astype(float).round(3)
    allr.insert(0, "排名", range(1, len(allr) + 1))
    top = allr.head(top_n).copy()
    pos = top["综合评分"].clip(lower=0)
    top["建议权重(%)"] = (pos / pos.sum() * 100).round(2) if pos.sum() > 0 else round(100 / len(top), 2)
    return allr, top
