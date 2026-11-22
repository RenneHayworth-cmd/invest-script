# -*- coding: utf-8 -*-
"""SPMO 选基：风险调整动量评分 + 建议权重"""
import plotly.graph_objects as go
import streamlit as st

from core import analytics as an
from core import charts, ui
from core.config import PALETTE

ui.header("🏆", "SPMO 选基", "评分 = 年化动量 ÷ 年化波动率（剔除最近一段避免短期反转），按得分分配权重")

METHODS = {
    "三周期加权 40/35/25": ("weighted", "近1年 40% + 近6月 35% + 近3月 25%（SPMO多周期403525加权.py / SPMO+RSI.py）"),
    "三周期等权": ("equal", "近1年、近6月、近3月三个评分简单平均（SPMO多周期.py）"),
    "标准 SPMO（12-1月）": ("standard", "过去 12 个月剔除最近 1 个月的动量，不足一年用成立以来（SPMO.py / SPMO近一年.py）"),
}

with st.container(border=True):
    picked = ui.pick_series("spmo", multi=True, label="基金池（可多选）", default_all=True)
    c1, c2, c3 = st.columns([1.4, 1, 1])
    mname = c1.selectbox("评分方法", list(METHODS))
    topn = c2.number_input("组合入选数量", 1, 30, 10)
    show_rsi = c3.toggle("显示 RSI 状态", value=True)
    st.caption("ℹ️ " + METHODS[mname][1] + "。波动率统一用最近 250 日（不足则用全部）。")

if len(picked) < 1:
    st.stop()

series = {p["name"]: p["df"] for p in picked}
allr, top = an.spmo_rank(series, METHODS[mname][0], int(topn), show_rsi)
if allr.empty:
    st.warning("没有可评分的品种（每个品种至少需要 30 个交易日）")
    st.stop()

lead = allr.iloc[0]
pos_cnt = (allr["综合评分"] > 0).sum()
ui.kpi_row([
    ("参与评分", f"{len(allr)} 只", "", f"数据最新 {max(allr['最新日期'])}"),
    ("第一名", lead["名称"], "up", f"评分 {lead['综合评分']:.3f}"),
    ("正动量", f"{pos_cnt} / {len(allr)}", "up" if pos_cnt > len(allr) / 2 else "down", "评分 > 0 的数量"),
    ("组合集中度", f"{top['建议权重(%)'].max():.1f}%", "", "最大单只权重"),
])
st.write("")

c1, c2 = st.columns([1.3, 1])
with c1:
    st.markdown("###### 综合评分排名")
    ui.plot(charts.score_bar(allr, "综合评分", "名称"))
with c2:
    st.markdown(f"###### 建议组合（前 {len(top)} 名，按正分比例）")
    ui.plot(charts.donut(top["名称"], top["建议权重(%)"]))

if METHODS[mname][0] != "standard":
    st.markdown("###### 三周期评分对比")
    fig = go.Figure()
    for i, col in enumerate(["SPMO(近1年)", "SPMO(近6月)", "SPMO(近3月)"]):
        fig.add_trace(go.Bar(x=allr["名称"], y=allr[col], name=col.replace("SPMO", ""), marker_color=PALETTE[i]))
    fig.add_trace(go.Scatter(x=allr["名称"], y=allr["综合评分"], name="综合", mode="markers",
                             marker=dict(size=12, symbol="diamond", color="#0F172A")))
    fig.update_layout(barmode="group")
    ui.plot(charts.style(fig, 380))

st.markdown("###### 完整排名表")
show = allr.merge(top[["名称", "建议权重(%)"]], on="名称", how="left")
cfg = {"综合评分": st.column_config.NumberColumn(format="%.3f"),
       "建议权重(%)": st.column_config.ProgressColumn(min_value=0, max_value=100, format="%.2f%%")}
for c in [c for c in show.columns if c.startswith("涨幅")]:
    cfg[c] = st.column_config.NumberColumn(format="%.2f%%")
if "RSI(14)" in show:
    cfg["RSI(14)"] = st.column_config.ProgressColumn(min_value=0, max_value=100, format="%.1f")
ui.table(show, column_config=cfg)
if show_rsi and "RSI状态" in show:
    hot = show[show["RSI状态"] == "超买"]["名称"].tolist()
    if hot:
        st.markdown("⚠️ 动量靠前但已超买，追高需谨慎：" + " ".join(ui.pill(h, "up") for h in hot),
                    unsafe_allow_html=True)
st.caption("与原脚本的差别：负分品种的建议权重记为 0（原脚本可能出现负权重）；TickFlow 的 close 列也能被识别。")
c1, c2 = st.columns(2)
with c1:
    ui.download_excel({"最佳组合": top, "全部排名": allr}, f"SPMO_{METHODS[mname][0]}_{ui.stamp()}.xlsx", key="dl_spmo")
with c2:
    ui.download_csv(show, f"SPMO_{METHODS[mname][0]}_{ui.stamp()}.csv", key="dl_spmo_csv")
