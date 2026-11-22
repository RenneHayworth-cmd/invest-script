# -*- coding: utf-8 -*-
"""总览：数据文件夹里所有品种的快照 + 功能入口"""
from pathlib import Path

import pandas as pd
import streamlit as st

from core import analytics as an
from core import charts, ui
from core import io as dio

ui.header("📈", "A股投资工具箱", "把 26 个脚本整合在一处：数据下载 · 单品种分析 · 指数期货 · 轮动回测 · SPMO 选基")

data_dir = Path(st.session_state["data_dir"])
files = dio.list_data_files(data_dir)


@st.cache_data(show_spinner=False)
def snapshot(paths_mtimes: tuple):
    rows, curves = [], {}
    for p, _ in paths_mtimes:
        try:
            s = dio.load_price(p)
        except Exception:  # noqa: BLE001
            continue
        df = s["df"]
        px = df["price"]

        def ret(k):
            return px.iloc[-1] / px.iloc[-(k + 1)] - 1 if len(px) > k else None

        ytd_base = df[df["date"].dt.year == df["date"].iloc[-1].year]["price"].iloc[0]
        r = an.rsi(px).iloc[-1]
        rows.append({
            "品种": s["name"], "最新日期": df["date"].iloc[-1].date(), "最新价": round(px.iloc[-1], 4),
            "近1月": ret(21), "近3月": ret(63), "今年以来": px.iloc[-1] / ytd_base - 1, "近1年": ret(252),
            "距高点": px.iloc[-1] / px.max() - 1, "RSI(14)": round(r, 1) if pd.notna(r) else None,
            "近一年走势": px.tail(250).round(4).tolist(), "_file": Path(p).name,
        })
        tail = df[df["date"] >= df["date"].iloc[-1] - pd.Timedelta(days=365)]
        curves[s["name"]] = pd.Series((tail["price"] / tail["price"].iloc[0] - 1).values * 100,
                                      index=tail["date"].values)
    return pd.DataFrame(rows), curves


if files:
    snap, curves = snapshot(tuple((str(f), f.stat().st_mtime) for f in files))
else:
    snap, curves = pd.DataFrame(), {}

if snap.empty:
    st.info(f"数据文件夹 `{data_dir}` 里还没有可识别的行情文件。先去 **数据中心** 下载 ETF / 基金数据吧。")
else:
    latest = max(snap["最新日期"])
    best = snap.loc[snap["近1月"].astype(float).idxmax()] if snap["近1月"].notna().any() else None
    worst_rsi = snap.dropna(subset=["RSI(14)"])
    ui.kpi_row([
        ("跟踪品种", f"{len(snap)}", "", f"数据最新到 {latest}"),
        ("近1月最强", best["品种"] if best is not None else "—", "",
         ui.pct(best["近1月"]) if best is not None else ""),
        ("超买 (RSI>70)", f"{(worst_rsi['RSI(14)'] > 70).sum()} 只", "up" if (worst_rsi['RSI(14)'] > 70).any() else "",
         "、".join(worst_rsi.loc[worst_rsi['RSI(14)'] > 70, '品种'].head(3)) or "无"),
        ("超卖 (RSI<30)", f"{(worst_rsi['RSI(14)'] < 30).sum()} 只", "down" if (worst_rsi['RSI(14)'] < 30).any() else "",
         "、".join(worst_rsi.loc[worst_rsi['RSI(14)'] < 30, '品种'].head(3)) or "无"),
    ])
    st.write("")
    left, right = st.columns([1.35, 1])
    with left:
        st.markdown("##### 📋 品种快照")
        show = snap.drop(columns=["_file"]).copy()
        for c in ("近1月", "近3月", "今年以来", "近1年", "距高点"):
            show[c] = show[c].astype(float) * 100
        pct_cfg = {c: st.column_config.NumberColumn(c, format="%.2f%%") for c in
                   ("近1月", "近3月", "今年以来", "近1年", "距高点")}
        st.dataframe(
            show, hide_index=True, height=min(460, 38 * len(show) + 40), **ui.STRETCH,
            column_config={
                **pct_cfg,
                "最新价": st.column_config.NumberColumn(format="%.4f"),
                "RSI(14)": st.column_config.ProgressColumn("RSI(14)", min_value=0, max_value=100, format="%.1f"),
                "近一年走势": st.column_config.LineChartColumn("近一年走势", width="medium"),
            })
    with right:
        st.markdown("##### 📊 近一年收益对比")
        ui.plot(charts.multi_line(curves, pct=True, height=max(320, min(460, 38 * len(snap) + 40))))

st.divider()
st.markdown("##### 🧭 功能模块")
cards = [
    ("views/data_center.py", "📥 数据中心", "TickFlow 下载 ETF / A股 / 美股日线（前、后复权），东财场外基金全部历史净值，微盘股 BK1158 市值最小名单。",
     ["ETFdataget", "tickflow_US", "jjjz", "wpg30"]),
    ("views/single.py", "🔍 单品种分析", "滚动年化收益、年度涨幅与回撤、全部回撤波段、20/60/120/250 日均线、RSI 与价格百分位。",
     ["3年滚动年化", "均线工具", "RSI百分位"]),
    ("views/market.py", "🌐 指数与期货", "主要指数 MA20 偏离率横向对比；股指 / 商品期货不同合约价差走势与统计。",
     ["指数MA20", "期货价差"]),
    ("views/backtest.py", "🔁 轮动回测", "多基金动量轮动 v4（前N名、周/月、含滑点与手续费）和双标的周度动量轮动。",
     ["rotation_v4", "dongliang"]),
    ("views/spmo.py", "🏆 SPMO 选基", "标准 / 三周期等权 / 40-35-25 加权三种评分，附 RSI 状态与建议权重。",
     ["SPMO", "多周期", "+RSI"]),
]
cols = st.columns(3)
for i, (page, title, desc, tags) in enumerate(cards):
    with cols[i % 3]:
        st.markdown(f'<div class="card"><h4>{title}</h4><p>{desc}</p>'
                    + "".join(f'<span class="tag">{t}</span>' for t in tags) + "</div>", unsafe_allow_html=True)
        st.page_link(page, label="打开 →")
        st.write("")
