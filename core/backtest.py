# -*- coding: utf-8 -*-
"""策略回测引擎
- rotation_backtest：移植自 fund_rotation_tool_v4.py（多基金动量轮动，前N名等权，周/月调仓，开盘成交，含滑点/手续费/100份整手）
- dual_momentum   ：移植自 donglianglhcv2.py（两只标的每周一按上周五收盘动量择强，开盘换仓）
"""
from datetime import timedelta

import numpy as np
import pandas as pd

BUY_SLIPPAGE = 0.0005
SELL_SLIPPAGE = 0.0005
LOT_SIZE = 100


def _merge(series_map: dict) -> tuple[pd.DataFrame, list]:
    """outer join 合并 + 前值填充（避免停牌导致价格归零/幸存者偏差）"""
    merged, syms = None, []
    for sym, df in series_map.items():
        d = pd.DataFrame({"date": df["date"], sym: df["price"],
                          f"{sym}__open": df["open"] if "open" in df else df["price"]})
        merged = d if merged is None else merged.merge(d, on="date", how="outer")
        syms.append(sym)
    merged = merged.sort_values("date").reset_index(drop=True)
    for s in syms:
        merged[s] = merged[s].ffill()
        merged[f"{s}__open"] = merged[f"{s}__open"].ffill()
    return merged, syms


def _rebalance_dates(trade_dates: pd.Series, start, end, frequency: str) -> list:
    td = pd.DatetimeIndex(trade_dates)
    if frequency == "week":
        anchors = pd.date_range(start, end, freq="W-MON")
    else:
        anchors = pd.date_range(start.replace(day=1), end, freq="MS")
        anchors = anchors[anchors >= start] if len(anchors) else anchors
    out = []
    for a in anchors:
        pos = td.searchsorted(a)
        if pos < len(td):
            d = td[pos]
            if not out or d != out[-1]:
                out.append(d)
    return out


def perf_metrics(nav: pd.Series, dates: pd.Series, trades_count: int = 0, rf: float = 0.02,
                 base: float | None = None) -> dict:
    """base：计算累计收益的基数（默认用首日净值；轮动策略传入初始资金，与原脚本口径一致）"""
    nav = pd.Series(nav.values, index=pd.DatetimeIndex(dates))
    total = nav.iloc[-1] / (base if base else nav.iloc[0]) - 1
    days = (nav.index[-1] - nav.index[0]).days
    ann = (1 + total) ** (365 / days) - 1 if days > 0 and total > -1 else 0
    r = nav.pct_change().replace([np.inf, -np.inf], np.nan).dropna()
    r = r[r.abs() < 1]
    dd = nav / nav.cummax() - 1
    mdd = dd.min()
    sd = r.std()
    sharpe = (r.mean() * 252 - rf) / (sd * np.sqrt(252)) if sd and sd > 0 else 0
    down = r[r < 0].std()
    sortino = (r.mean() * 252 - rf) / (down * np.sqrt(252)) if down and down > 0 else 0
    calmar = (r.mean() * 252) / abs(mdd) if mdd else 0
    mret = nav.resample("ME").last().pct_change().dropna()
    years = days / 365 if days else 0
    return {"累计收益": total, "年化收益": ann, "最大回撤": mdd, "年化波动": sd * np.sqrt(252) if sd else 0,
            "夏普比率": round(float(sharpe), 2), "索提诺比率": round(float(sortino), 2),
            "卡玛比率": round(float(calmar), 2), "月度胜率": float((mret > 0).mean()) if len(mret) else 0,
            "年化换手次数": round(trades_count / years, 1) if years else 0}


def rotation_backtest(series_map: dict, names: dict | None = None, frequency: str = "week",
                      lookback: int = 22, num_positions: int = 1, initial_capital: float = 100000,
                      fee: float = 0.00006, start_date=None, end_date=None) -> dict:
    names = names or {s: s for s in series_map}
    if len(series_map) < 2:
        raise ValueError("至少需要 2 只基金进行轮动")
    if not 1 <= num_positions <= len(series_map):
        raise ValueError(f"持仓数量必须在 1 到 {len(series_map)} 之间")
    merged, syms = _merge(series_map)
    if start_date is not None:
        merged = merged[merged["date"] >= pd.Timestamp(start_date) - pd.Timedelta(days=lookback * 3)]
    if end_date is not None:
        merged = merged[merged["date"] <= pd.Timestamp(end_date)]
    merged = merged.reset_index(drop=True)

    # 每只基金满足完整动量窗口的日期 -> 取最晚者作为可开始日
    eligible = []
    for s in syms:
        valid = merged.loc[merged[s].notna(), "date"].reset_index(drop=True)
        if len(valid) <= lookback:
            raise ValueError(f"{names.get(s, s)} 数据长度不足 {lookback + 1} 个交易日")
        eligible.append(valid.iloc[lookback])
    start = max(eligible)
    if start_date is not None:
        start = max(start, pd.Timestamp(start_date))
    if frequency == "week":
        start = start + timedelta(days=(7 - start.weekday()) % 7)
    elif start.day != 1:
        start = (start + pd.offsets.MonthBegin(1)).normalize()
    end = merged["date"].max()

    # 动量：调仓日前一交易日收盘 / 往前 lookback 个交易日收盘 - 1（与 v4 口径一致）
    mom = pd.DataFrame({s: (merged[s].shift(1) / merged[s].shift(lookback) - 1) for s in syms})
    mom = mom.replace([np.inf, -np.inf], np.nan).fillna(0)
    mom.index = merged["date"]

    bt = merged[merged["date"] >= start].reset_index(drop=True)
    if bt.empty:
        raise ValueError("回测区间内没有数据")
    rebals = _rebalance_dates(bt["date"], start, end, frequency)
    bt_idx = bt.set_index("date")

    cash, shares = float(initial_capital), {}
    trades, nav_rows = [], []
    tot_buy = tot_sell = 0.0

    def px(row, s):
        v = row.get(s)
        return 0.0 if pd.isna(v) else float(v)

    def trade_px(row, s, side):
        o = row.get(f"{s}__open")
        base = px(row, s) if pd.isna(o) else float(o)
        return base * (1 + BUY_SLIPPAGE) if side == "buy" else base * (1 - SELL_SLIPPAGE)

    def value(sh, row):
        return sum(q * px(row, s) for s, q in sh.items())

    for i, d in enumerate(rebals):
        row = bt_idx.loc[d]
        m = mom.loc[d].to_dict()
        selected = [s for s, _ in sorted(m.items(), key=lambda x: x[1], reverse=True)[:num_positions]]
        changed = set(selected) != set(shares)
        before = value(shares, row) + cash
        b_cost = s_cost = 0.0
        sell_txt, buy_txt = [], []
        if changed and shares:
            for s, q in shares.items():
                p = trade_px(row, s, "sell")
                gross = q * p
                c = gross * fee
                cash += gross - c
                s_cost += c
                sell_txt.append(f"{names.get(s, s)} {q:.0f}份@{p:.4f}")
        new = {}
        if changed:
            alloc = cash / len(selected)
            for s in selected:
                p = trade_px(row, s, "buy")
                q = float(int((alloc * (1 - fee) / p) // LOT_SIZE) * LOT_SIZE) if p > 0 else 0.0
                amt = q * p
                c = amt * fee
                cash -= amt + c
                b_cost += c
                new[s] = q
                buy_txt.append(f"{names.get(s, s)} {q:.0f}份@{p:.4f}")
        else:
            new = dict(shares)
        shares = new
        tot_buy += b_cost
        tot_sell += s_cost
        trades.append({"日期": d.date(), "操作": "调仓" if changed else "持有",
                       "持仓": "、".join(names.get(s, s) for s in selected),
                       **{f"动量·{names.get(s, s)}(%)": round(m.get(s, 0) * 100, 2) for s in syms},
                       "调仓前资产": round(before, 2), "卖出": "；".join(sell_txt), "买入": "；".join(buy_txt),
                       "手续费": round(b_cost + s_cost, 2), "现金余额": round(cash, 2)})
        nxt = rebals[i + 1] if i + 1 < len(rebals) else end + timedelta(days=1)
        seg = bt[(bt["date"] >= d) & (bt["date"] < nxt)]
        for _, r in seg.iterrows():
            nav_rows.append({"date": r["date"], "value": value(shares, r) + cash,
                             "holdings": "、".join(names.get(s, s) for s in shares)})

    nav = pd.DataFrame(nav_rows)
    if nav.empty:
        raise ValueError("回测没有产生净值数据，请检查区间与参数")
    nav["drawdown"] = nav["value"] / nav["value"].cummax() - 1
    n_trades = sum(1 for t in trades if t["操作"] == "调仓")
    metrics = perf_metrics(nav["value"], nav["date"], n_trades, base=initial_capital)
    metrics.update({"期末资产": nav["value"].iloc[-1], "调仓次数": n_trades,
                    "累计手续费": tot_buy + tot_sell})

    bench, bench_metrics = {}, []
    first_day = nav["date"].iloc[0]
    for s in syms:
        seg = bt[["date", s]].dropna()
        seg = seg[seg["date"] >= first_day]
        if len(seg) < 2:
            continue
        curve = seg[s] / seg[s].iloc[0] * initial_capital
        bench[names.get(s, s)] = pd.Series(curve.values, index=seg["date"].values)
        bm = perf_metrics(curve, seg["date"])
        bench_metrics.append({"标的": names.get(s, s), "累计收益": bm["累计收益"], "年化收益": bm["年化收益"],
                              "最大回撤": bm["最大回撤"], "夏普比率": bm["夏普比率"]})

    hold = nav.groupby("holdings").size().reset_index(name="天数")
    return {"nav": nav, "trades": pd.DataFrame(trades), "metrics": metrics, "bench": bench,
            "bench_metrics": pd.DataFrame(bench_metrics), "holding_days": hold,
            "start": first_day, "end": nav["date"].iloc[-1]}


def dual_momentum(df1: pd.DataFrame, df2: pd.DataFrame, name1: str, name2: str, lookback: int = 22,
                  init_capital: float = 1_000_000, commission: float = 0.00006, slippage: float = 0.0005,
                  start_date=None, end_date=None) -> dict:
    """双标的周度动量轮动（donglianglhcv2.py 口径）：
    周一开盘前用上周五收盘计算 lookback 日涨幅择强，周一开盘换仓；单边成本 = 佣金 + 滑点。"""
    cost = commission + slippage

    def prep(df):
        d = df.set_index("date").sort_index()
        o = d["open"] if "open" in d else d["price"]
        return o, d["price"]

    o1, c1 = prep(df1)
    o2, c2 = prep(df2)
    po = pd.concat([o1.rename("a"), o2.rename("b")], axis=1).sort_index().ffill().dropna()
    pc = pd.concat([c1.rename("a"), c2.rename("b")], axis=1).sort_index().ffill().dropna()
    idx = po.index.intersection(pc.index)
    if start_date is not None:
        idx = idx[idx >= pd.Timestamp(start_date)]
    if end_date is not None:
        idx = idx[idx <= pd.Timestamp(end_date)]
    po, pc = po.loc[idx], pc.loc[idx]
    if len(pc) < lookback + 2:
        raise ValueError(f"共同数据不足，至少需要 {lookback + 2} 个交易日")
    dates = pc.index
    rebal = dates[(dates.dayofweek == 0) & (dates > dates[lookback])]
    if len(rebal) == 0:
        raise ValueError("区间内没有可调仓的周一")
    sig = {}
    for d in rebal:
        k = dates.get_loc(d)
        prev, st = dates[k - 1], dates[k - 1 - lookback] if k - 1 - lookback >= 0 else None
        if st is None:
            sig[d] = "a"
            continue
        m1 = pc.at[prev, "a"] / pc.at[st, "a"] - 1
        m2 = pc.at[prev, "b"] / pc.at[st, "b"] - 1
        sig[d] = "a" if m1 >= m2 else "b"
    sig = pd.Series(sig)
    pos = sig.reindex(dates, method="ffill").dropna()
    lbl = {"a": name1, "b": name2}
    rets, trades, prev_h = [], [], None
    prev_close = pc.shift(1)
    for d, h in pos.items():
        o, c = po.at[d, h], pc.at[d, h]
        if prev_h is None:
            # 首次建仓：开盘买入，当日收益 = 收盘/开盘，扣单边成本
            r = c / o - 1 - cost
            trades.append({"日期": d.date(), "操作": "建仓", "卖出": "", "买入": lbl[h], "成本": cost})
        elif h != prev_h:
            # 换仓：旧持仓 昨收->今开 的隔夜涨跌 + 新持仓 今开->今收，扣双边成本
            # （原脚本忽略了旧持仓的隔夜跳空，这里补上）
            gap = po.at[d, prev_h] / prev_close.at[d, prev_h]
            r = gap * (c / o) - 1 - 2 * cost
            trades.append({"日期": d.date(), "操作": "调仓", "卖出": lbl[prev_h], "买入": lbl[h], "成本": 2 * cost})
        else:
            pcv = prev_close.at[d, h]
            r = c / pcv - 1 if not pd.isna(pcv) else c / o - 1
        rets.append(r)
        prev_h = h
    ret = pd.Series(rets, index=pos.index)
    nav = (1 + ret).cumprod() * init_capital
    b1 = pc["a"].loc[nav.index] / pc["a"].loc[nav.index].iloc[0] * init_capital
    b2 = pc["b"].loc[nav.index] / pc["b"].loc[nav.index].iloc[0] * init_capital
    navdf = pd.DataFrame({"date": nav.index, "value": nav.values, "holdings": pos.map(lbl).values})
    navdf["drawdown"] = navdf["value"] / navdf["value"].cummax() - 1
    metrics = perf_metrics(navdf["value"], navdf["date"], sum(1 for t in trades if t["操作"] == "调仓"),
                           base=init_capital)
    metrics["期末资产"] = nav.iloc[-1]
    metrics["调仓次数"] = sum(1 for t in trades if t["操作"] == "调仓")

    yearly = []
    frame = pd.DataFrame({"策略": nav, name1: b1, name2: b2})
    for y, g in frame.groupby(frame.index.year):
        row = {"年份": int(y)}
        for col in frame.columns:
            row[f"{col}收益"] = g[col].iloc[-1] / g[col].iloc[0] - 1
            row[f"{col}回撤"] = (g[col] / g[col].cummax() - 1).min()
        yearly.append(row)
    bench = {name1: b1, name2: b2}
    bm = []
    for k, v in bench.items():
        m = perf_metrics(v, v.index.to_series())
        bm.append({"标的": k, "累计收益": m["累计收益"], "年化收益": m["年化收益"], "最大回撤": m["最大回撤"],
                   "夏普比率": m["夏普比率"]})
    return {"nav": navdf, "trades": pd.DataFrame(trades), "metrics": metrics, "bench": bench,
            "bench_metrics": pd.DataFrame(bm), "yearly": pd.DataFrame(yearly),
            "holding_days": navdf.groupby("holdings").size().reset_index(name="天数"),
            "start": navdf["date"].iloc[0], "end": navdf["date"].iloc[-1]}
