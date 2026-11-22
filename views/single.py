# -*- coding: utf-8 -*-
"""单品种分析：滚动年化 & 回撤 / 均线 / RSI & 百分位"""
import pandas as pd
import streamlit as st

from core import analytics as an
from core import charts, ui

ui.header("🔍", "单品种分析", "适用于 ETF K线（收盘价）和场外基金（累计净值）")

with st.container(border=True):
    picked = ui.pick_series("single", multi=False)
if not picked:
    st.stop()
S = picked[0]
df_all = S["df"]
with st.expander("⏱️ 分析区间", expanded=False):
    df = ui.date_filter(df_all, "single")
if len(df) < 30:
    st.warning("区间内数据太少（不足 30 个交易日）")
    st.stop()

stats = an.summary_stats(df)
ui.kpi_row([
    ("品种", S["name"], "", f"价格列：{S['price_label']}"),
    ("最新价", ui.num(stats["最新价"]), "", f"{stats['最新日']}"),
    ("区间涨幅", ui.pct(stats["区间涨幅"]), ui.tone_of(stats["区间涨幅"]), f"自 {stats['起始日']}"),
    ("年化收益", ui.pct(stats["年化收益"]), ui.tone_of(stats["年化收益"]), f"年化波动 {ui.pct(stats['年化波动'], sign=False)}"),
    ("最大回撤", ui.pct(stats["最大回撤"]), "down", f"当前回撤 {ui.pct(stats['当前回撤'])}"),
])
st.write("")

t1, t2, t3 = st.tabs(["📈 滚动年化 & 回撤", "〰️ 均线系统", "🌡️ RSI & 价格百分位"])

# ------------------------------------------------------------------ 滚动年化 & 回撤
with t1:
    st.caption("来源：fund_3-Year Rolling / fund_analysis_gui_fixed / ETF-3-Year Rolling / 批量脚本/3yearsanddrawdown")
    c1, c2, c3 = st.columns([1, 1, 2])
    years = c1.selectbox("滚动窗口", [1, 2, 3, 5], index=2, format_func=lambda y: f"{y} 年")
    has_hl = {"high", "low"}.issubset(df.columns)
    hl = c2.toggle("按最高/最低价识别波段", value=has_hl, disabled=not has_hl,
                   help="ETF 脚本口径：用 K 线 High/Low 精确识别回撤；场外基金只有净值时自动用净值")
    roll = an.rolling_annualized(df, years)
    valid = roll.dropna()
    if valid.empty:
        st.info(f"数据不足 {years} 年，无法计算滚动年化收益。")
    else:
        ui.kpi_row([
            ("最新滚动年化", ui.pct(valid.iloc[-1]), ui.tone_of(valid.iloc[-1]), f"{years} 年窗口"),
            ("历史最高", ui.pct(valid.max()), "up", f"{df['date'][valid.idxmax()]:%Y-%m-%d}"),
            ("历史最低", ui.pct(valid.min()), "down", f"{df['date'][valid.idxmin()]:%Y-%m-%d}"),
            ("均值", ui.pct(valid.mean()), ui.tone_of(valid.mean()), ""),
            ("正收益占比", ui.pct((valid > 0).mean(), 1, sign=False), "", f"持有满 {years} 年赚钱的概率"),
        ])
        ui.plot(charts.rolling_return_chart(df, roll, years))

    periods = an.drawdown_periods(df, use_high_low=hl)
    ytab = an.yearly_table(df)
    c1, c2 = st.columns([1.25, 1])
    with c1:
        ui.plot(charts.drawdown_periods_chart(df, periods, top=5))
    with c2:
        st.markdown("###### 年度涨幅 & 年内最大回撤")
        if not ytab.empty:
            ui.plot(charts.yearly_bar(ytab))
    st.markdown("###### 回撤波段明细（按深度排序）")
    if periods.empty:
        st.info("区间内没有回撤")
    else:
        unrecovered = periods[~periods["是否已修复"]]
        if not unrecovered.empty:
            r = unrecovered.iloc[-1]
            st.markdown(f"当前处于回撤中：自 **{r['开始']}** 起最深 **{r['回撤深度(%)']:.2f}%**，"
                        f"谷底后已过 **{r['修复天数']}** 天 " + ui.pill("未修复", "down"), unsafe_allow_html=True)
        ui.table(periods.sort_values("回撤深度(%)").head(50), height=320, column_config={
            "回撤深度(%)": st.column_config.NumberColumn(format="%.2f%%"),
            "是否已修复": st.column_config.CheckboxColumn()})
    with st.expander("年度明细表"):
        ui.table(ytab)
    b1, b2, b3 = st.columns(3)
    with b1:
        out = df[["date", "price"]].assign(**{f"{years}年滚动年化(%)": (roll * 100).round(4)})
        ui.download_csv(out, f"{S['code']}_{years}年滚动年化.csv", key="dl_roll")
    with b2:
        ui.download_excel({"年度统计": ytab, "回撤波段": periods}, f"{S['code']}_回撤分析_{ui.stamp()}.xlsx",
                          key="dl_dd")
    with b3:
        ui.download_html(charts.price_drawdown(df, S["name"]), f"{S['code']}_净值回撤.html", key="dl_ddh")

# ------------------------------------------------------------------ 均线
with t2:
    st.caption("来源：fund_20&60&120&250day_moving_average.py")
    periods_ma = st.multiselect("均线周期", [5, 10, 20, 30, 60, 120, 250], default=[20, 60, 120, 250])
    if periods_ma:
        d = an.moving_averages(df, sorted(periods_ma))
        ui.plot(charts.ma_chart(d, S["name"], sorted(periods_ma)))
        last = d.iloc[-1]
        items = []
        for n in sorted(periods_ma):
            v = last.get(f"MA{n}偏离(%)")
            items.append((f"MA{n}", ui.num(last.get(f"MA{n}")),
                          ui.tone_of(v), "数据不足" if pd.isna(v) else f"偏离 {v:+.2f}% {'↑在上方' if v > 0 else '↓在下方'}"))
        ui.kpi_row(items)
        st.write("")
        # 均线排列判断
        vals = [last.get(f"MA{n}") for n in sorted(periods_ma)]
        if all(pd.notna(v) for v in vals) and len(vals) >= 2:
            if all(a > b for a, b in zip(vals, vals[1:])) and last["price"] > vals[0]:
                st.markdown("均线形态：" + ui.pill("多头排列", "up"), unsafe_allow_html=True)
            elif all(a < b for a, b in zip(vals, vals[1:])) and last["price"] < vals[0]:
                st.markdown("均线形态：" + ui.pill("空头排列", "down"), unsafe_allow_html=True)
            else:
                st.markdown("均线形态：" + ui.pill("交织 / 震荡", "mid"), unsafe_allow_html=True)
        c1, c2 = st.columns(2)
        with c1:
            ui.download_excel({"均线数据": d}, f"{S['code']}_均线_{ui.stamp()}.xlsx", key="dl_ma")
        with c2:
            ui.download_html(charts.ma_chart(d, S["name"], sorted(periods_ma)), f"{S['code']}_均线.html",
                             key="dl_mah")

# ------------------------------------------------------------------ RSI
with t3:
    st.caption("来源：fund_RSI&percentile_analyzer.py")
    base = st.date_input("自定义涨幅基准日", pd.Timestamp("2024-09-30"),
                         help="原脚本固定为 2024-09-30（\"924 行情\"起点），这里可改")
    t = an.indicator_table(df, str(base))
    last = t.iloc[-1]
    r = last["RSI(14)"]
    c1, c2 = st.columns([1, 2.4])
    with c1:
        st.plotly_chart(charts.gauge(r, "RSI(14)"), config=ui.PLOT_CFG, **ui.STRETCH)
        st.plotly_chart(charts.gauge(last["价格百分位"], "历史价格百分位", lo=20, hi=80), config=ui.PLOT_CFG,
                        **ui.STRETCH)
    with c2:
        tone = {"超买": "up", "超卖": "down"}.get(last["状态"], "mid")
        bcol = [c for c in t.columns if c.startswith("自")][0] if any(c.startswith("自") for c in t.columns) else None
        ui.kpi_row([
            ("RSI 状态", last["状态"], tone, f"RSI = {r:.1f}" if pd.notna(r) else ""),
            ("20日涨幅", f"{last['20日涨幅(%)']:+.2f}%" if pd.notna(last["20日涨幅(%)"]) else "—",
             ui.tone_of(last["20日涨幅(%)"]), f"60日 {last['60日涨幅(%)']:+.2f}%" if pd.notna(last["60日涨幅(%)"]) else ""),
            ("今年以来", f"{last['YTD涨幅(%)']:+.2f}%", ui.tone_of(last["YTD涨幅(%)"]), ""),
            ("自基准日", f"{last[bcol]:+.2f}%" if bcol and pd.notna(last[bcol]) else "—",
             ui.tone_of(last[bcol]) if bcol else "", str(base)),
            ("动量/波动(20日)", f"{last['动量/波动(20日)']:.2f}", ui.tone_of(last["动量/波动(20日)"]),
             f"20日波动 {last['20日波动率(%)']:.2f}%"),
        ])
        ui.plot(charts.rsi_chart(t))
    with st.expander("逐日指标表（最近 250 天）"):
        ui.table(t.sort_values("日期", ascending=False).head(250), height=420)
    c1, c2 = st.columns(2)
    with c1:
        ui.download_excel({"每日完整数据": t, "最新一日摘要": t.tail(1)},
                          f"{S['code']}_RSI百分位_{ui.stamp()}.xlsx", key="dl_rsi")
    with c2:
        ui.download_html(charts.rsi_chart(t), f"{S['code']}_RSI.html", key="dl_rsih")
