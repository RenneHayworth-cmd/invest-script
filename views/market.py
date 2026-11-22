# -*- coding: utf-8 -*-
"""指数与期货：指数 MA20 偏离率 / 期货合约价差"""
import re

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from core import charts, fetchers, ui
from core.config import CONTRACT_PREFIXES, INDEX_CONFIG, PALETTE

ui.header("🌐", "指数与期货", "需要联网：指数数据来自 TickFlow + AkShare，期货来自 AkShare（新浪）")
t1, t2 = st.tabs(["📐 指数 MA 偏离率", "⚖️ 期货合约价差"])


@st.cache_data(ttl=1800, show_spinner=False)
def _index_panel(names: tuple, days: int, ma: int):
    cfg = {n: INDEX_CONFIG[n] for n in names}
    return fetchers.index_ma20_panel(cfg, days=days, ma=ma)


@st.cache_data(ttl=1800, show_spinner=False)
def _spread(contracts: tuple, base: str):
    return fetchers.futures_spread(list(contracts), base)


def cname(c: str) -> str:
    m = re.match(r"([A-Za-z]+)", c)
    n = CONTRACT_PREFIXES.get(m.group(1).upper(), "") if m else ""
    return f"{c.upper()}（{n}）" if n else c.upper()


# ------------------------------------------------------------------ 指数
with t1:
    st.caption("来源：指数MA20分析工具_分列版.py · 偏离率 = (收盘 - MA) / MA")
    c1, c2, c3 = st.columns([3, 1, 1])
    names = c1.multiselect("指数", list(INDEX_CONFIG), default=list(INDEX_CONFIG))
    ma = c2.number_input("均线天数", 5, 250, 20)
    days = c3.selectbox("展示最近", [30, 60, 120, 250], index=1, format_func=lambda d: f"{d} 个交易日")
    if st.button("获取 / 刷新", type="primary", key="idx_go") or "idx_res" in st.session_state:
        if st.session_state.get("idx_key") != (tuple(names), days, ma):
            with st.spinner("正在获取指数数据…"):
                st.session_state["idx_res"] = _index_panel(tuple(names), int(days * 1.6 + ma * 2 + 10), int(ma))
                st.session_state["idx_key"] = (tuple(names), days, ma)
        data, errs = st.session_state["idx_res"]
        for n, e in errs.items():
            st.warning(f"{n}：{e}")
        if data:
            latest = pd.DataFrame([{"指数": n, "日期": d["date"].iloc[-1].date(), "收盘": d["close"].iloc[-1],
                                    f"MA{ma}": d["MA"].iloc[-1], "偏离率(%)": d["偏离率(%)"].iloc[-1]}
                                   for n, d in data.items()])
            hot = latest.loc[latest["偏离率(%)"].idxmax()]
            cold = latest.loc[latest["偏离率(%)"].idxmin()]
            ui.kpi_row([("指数数量", f"{len(latest)}", "", f"最新 {max(latest['日期'])}"),
                        ("站上均线", f"{(latest['偏离率(%)'] > 0).sum()} / {len(latest)}", "", ""),
                        ("偏离最高", hot["指数"], "up", f"{hot['偏离率(%)']:+.2f}%"),
                        ("偏离最低", cold["指数"], "down", f"{cold['偏离率(%)']:+.2f}%")])
            st.write("")
            c1, c2 = st.columns([1, 1.5])
            with c1:
                st.markdown(f"###### 最新偏离率（MA{ma}）")
                ui.plot(charts.bias_bars(latest))
            with c2:
                st.markdown("###### 偏离率走势")
                fig = go.Figure()
                for i, (n, d) in enumerate(data.items()):
                    d = d.tail(days)
                    fig.add_trace(go.Scatter(x=d["date"], y=d["偏离率(%)"], name=n,
                                             line=dict(width=1.6, color=PALETTE[i % len(PALETTE)])))
                fig.add_hline(y=0, line=dict(color="#CBD5E1", width=1))
                fig.update_yaxes(ticksuffix="%")
                ui.plot(charts.style(fig, 400))
            # 小图矩阵：价格 vs MA
            st.markdown("###### 收盘价与均线")
            cols = st.columns(4)
            for i, (n, d) in enumerate(data.items()):
                d = d.tail(days)
                f = go.Figure()
                f.add_trace(go.Scatter(x=d["date"], y=d["close"], name="收盘", line=dict(color="#111827", width=1.4)))
                f.add_trace(go.Scatter(x=d["date"], y=d["MA"], name=f"MA{ma}", line=dict(color="#2563EB", width=1.2, dash="dot")))
                v = d["偏离率(%)"].iloc[-1]
                f.update_layout(title=dict(text=f"{n}  <span style='color:{'#E5484D' if v > 0 else '#12A150'}'>{v:+.2f}%</span>",
                                           x=0, font=dict(size=13)), showlegend=False)
                with cols[i % 4]:
                    st.plotly_chart(charts.style(f, 220, legend_top=False), config={"displayModeBar": False},
                                    **ui.STRETCH)
            # 分列导出（与原脚本格式一致）
            wide = None
            for n, d in data.items():
                part = d.tail(days)[["date", "close", "MA", "偏离率(%)"]].round(2)
                part.columns = ["日期", f"{n}_收盘价", f"{n}_MA{ma}", f"{n}_偏离率(%)"]
                wide = part if wide is None else wide.merge(part, on="日期", how="outer")
            wide = wide.sort_values("日期")
            wide["日期"] = wide["日期"].dt.strftime("%Y-%m-%d")
            with st.expander("分列数据表"):
                ui.table(wide, height=380)
            ui.download_csv(wide, f"指数MA{ma}分析_分列版_{ui.stamp()}.csv", key="dl_idx")

# ------------------------------------------------------------------ 期货
with t2:
    st.caption("来源：Futures_Spread_Analysis.py · 价差 = 基准合约 - 其他合约（共同交易日对齐）")
    c1, c2 = st.columns([3, 1])
    txt = c1.text_input("合约（空格/逗号分隔，第一个默认为基准）", "IM2612 IM2703 IM2706",
                        help="如 IC2603、IM2606、I2605、RB2605。备注里提到的常用：IC260x、IM260x、I260x")
    contracts = [c.strip().upper() for c in re.split(r"[\s,，]+", txt) if c.strip()]
    base = c2.selectbox("基准合约", contracts, index=0) if contracts else None
    if st.button("计算价差", type="primary", key="fut_go") and len(contracts) >= 2:
        with st.spinner("正在获取期货数据…"):
            try:
                st.session_state["fut_res"] = (_spread(tuple(contracts), base), base, contracts)
            except Exception as e:  # noqa: BLE001
                st.error(str(e))
    if "fut_res" in st.session_state:
        (res, info), b, cs = st.session_state["fut_res"]
        for c, e in info["errors"].items():
            st.warning(f"{c}：{e}")
        others = [c for c in cs if c != b and c in res.columns]
        if res.empty or not others:
            st.info("没有可对齐的共同交易日")
        else:
            items = [("基准", cname(b), "", f"最新 {res[b].iloc[-1]:.2f}")]
            for c in others[:4]:
                s = res[f"价差 {b}-{c}"]
                p = res[f"价差% {b}-{c}"]
                items.append((f"{b} - {c}", f"{s.iloc[-1]:+.2f}", ui.tone_of(s.iloc[-1]),
                              f"{p.iloc[-1]:+.2f}% · 均值 {s.mean():+.2f}"))
            ui.kpi_row(items)
            st.write("")
            c1, c2 = st.columns(2)
            with c1:
                st.markdown("###### 合约收盘价")
                ui.plot(charts.multi_line({cname(c): pd.Series(res[c].values, index=res["date"]) for c in cs if c in res},
                                          height=380, highlight=cname(b)))
            with c2:
                st.markdown("###### 价差走势")
                fig = go.Figure()
                for i, c in enumerate(others):
                    s = res[f"价差 {b}-{c}"]
                    fig.add_trace(go.Scatter(x=res["date"], y=s, name=f"{b}-{c}",
                                             line=dict(width=1.8, color=PALETTE[i % len(PALETTE)])))
                    fig.add_hline(y=s.mean(), line=dict(color=PALETTE[i % len(PALETTE)], width=1, dash="dot"))
                fig.add_hline(y=0, line=dict(color="#CBD5E1", width=1))
                ui.plot(charts.style(fig, 380))
            stat_rows = []
            for c in others:
                s = res[f"价差 {b}-{c}"]
                p = res[f"价差% {b}-{c}"]
                z = (s.iloc[-1] - s.mean()) / s.std() if s.std() else 0
                stat_rows.append({"价差": f"{cname(b)} - {cname(c)}", "最新": s.iloc[-1], "最新%": p.iloc[-1],
                                  "均值": s.mean(), "均值%": p.mean(), "最大": s.max(), "最小": s.min(),
                                  "当前分位": (s.rank(pct=True).iloc[-1]) * 100, "Z值": z})
            st.markdown("###### 统计")
            ui.table(pd.DataFrame(stat_rows).round(2), column_config={
                "当前分位": st.column_config.ProgressColumn(min_value=0, max_value=100, format="%.0f%%")})
            st.caption("各合约数据范围：" + "；".join(f"{cname(c)} {a} ~ {z}" for c, (a, z) in info["ranges"].items()))
            ui.download_csv(res, f"期货价差_{'_'.join(cs)}_{ui.stamp()}.csv", key="dl_fut")
