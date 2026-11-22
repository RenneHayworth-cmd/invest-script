# -*- coding: utf-8 -*-
"""轮动回测：多基金动量轮动 v4 / 双标的周度动量轮动"""
from datetime import date
from pathlib import Path

import pandas as pd
import streamlit as st

from core import backtest as bt
from core import charts, fetchers, ui
from core import io as dio

ui.header("🔁", "轮动回测", "动量轮动：定期买入过去 N 日涨幅最强的品种。建议使用后复权数据")

mode = st.segmented_control("回测模式", ["多基金轮动 v4", "双标的动量轮动"], default="多基金轮动 v4",
                            key="bt_mode") if hasattr(st, "segmented_control") else \
    st.radio("回测模式", ["多基金轮动 v4", "双标的动量轮动"], horizontal=True, key="bt_mode")
mode = mode or "多基金轮动 v4"


def show_result(R: dict, init: float, tag: str):
    m = R["metrics"]
    st.markdown(f"##### 回测结果　<span style='color:#64748B;font-size:.85rem'>{R['start']:%Y-%m-%d} ~ "
                f"{R['end']:%Y-%m-%d}</span>", unsafe_allow_html=True)
    ui.kpi_row([
        ("期末资产", f"{m['期末资产']:,.0f}", ui.tone_of(m["累计收益"]), f"初始 {init:,.0f}"),
        ("累计收益", ui.pct(m["累计收益"]), ui.tone_of(m["累计收益"]), ""),
        ("年化收益", ui.pct(m["年化收益"]), ui.tone_of(m["年化收益"]), f"年化波动 {ui.pct(m['年化波动'], sign=False)}"),
        ("最大回撤", ui.pct(m["最大回撤"]), "down", f"卡玛 {m['卡玛比率']}"),
        ("夏普 / 索提诺", f"{m['夏普比率']} / {m['索提诺比率']}", "", f"月度胜率 {ui.pct(m['月度胜率'], 1, sign=False)}"),
        ("调仓次数", f"{m['调仓次数']}", "", f"年均 {m['年化换手次数']} 次"
         + (f" · 手续费 {m['累计手续费']:,.0f}" if "累计手续费" in m else "")),
    ])
    st.write("")
    ui.plot(charts.equity_chart(R["nav"], R["bench"], init))
    c1, c2 = st.columns([1.4, 1])
    with c1:
        st.markdown("###### 策略 vs 单独持有")
        comp = pd.concat([pd.DataFrame([{"标的": "⭐ 轮动策略", "累计收益": m["累计收益"], "年化收益": m["年化收益"],
                                         "最大回撤": m["最大回撤"], "夏普比率": m["夏普比率"]}]),
                          R["bench_metrics"]], ignore_index=True)
        for c in ("累计收益", "年化收益", "最大回撤"):
            comp[c] = comp[c] * 100
        ui.table(comp, column_config={c: st.column_config.NumberColumn(format="%.2f%%")
                                      for c in ("累计收益", "年化收益", "最大回撤")})
        st.markdown("###### 月度收益热力图")
        ui.plot(charts.monthly_heatmap(R["nav"]))
    with c2:
        st.markdown("###### 持仓时间分布")
        h = R["holding_days"]
        ui.plot(charts.donut(h["holdings"], h["天数"]))
        if "yearly" in R:
            y = R["yearly"].copy()
            for c in y.columns[1:]:
                y[c] = y[c] * 100
            st.markdown("###### 年度表现")
            ui.table(y, column_config={c: st.column_config.NumberColumn(format="%.2f%%") for c in y.columns[1:]})
    with st.expander(f"📒 调仓记录（{len(R['trades'])} 条）"):
        ui.table(R["trades"], height=380)
    b1, b2, b3 = st.columns(3)
    with b1:
        ui.download_excel({"净值": R["nav"], "调仓记录": R["trades"], "对比": comp},
                          f"轮动回测_{tag}_{ui.stamp()}.xlsx", key=f"dlx_{tag}")
    with b2:
        ui.download_html(charts.equity_chart(R["nav"], R["bench"], init), f"轮动回测_{tag}.html", key=f"dlh_{tag}")
    with b3:
        if st.button("保存报告到输出文件夹", key=f"save_{tag}", **ui.STRETCH):
            out = Path(st.session_state["output_dir"]) / f"轮动回测_{tag}_{ui.stamp()}"
            out.mkdir(parents=True, exist_ok=True)
            R["nav"].to_csv(out / "nav_data.csv", index=False, encoding="utf-8-sig")
            R["trades"].to_csv(out / "rotation_trades.csv", index=False, encoding="utf-8-sig")
            comp.to_csv(out / "summary.csv", index=False, encoding="utf-8-sig")
            charts.equity_chart(R["nav"], R["bench"], init).write_html(out / "performance_chart.html",
                                                                        include_plotlyjs="cdn")
            st.success(f"已保存到 {out}")


# ================================================================== 多基金
if mode == "多基金轮动 v4":
    st.caption("来源：fund_rotation_tool_v4.py · 调仓日开盘成交（含 0.05% 滑点）、100 份整手、手续费按成交额计")
    with st.container(border=True):
        picked = ui.pick_series("rot", multi=True, label="选择参与轮动的品种（≥2）")
        c1, c2, c3, c4, c5 = st.columns(5)
        freq = c1.selectbox("调仓频率", ["每周（周一）", "每月（月初）"])
        lookback = c2.number_input("动量回看（交易日）", 5, 250, 22)
        npos = c3.number_input("持仓数量（前 N 名等权）", 1, max(1, len(picked)), 1)
        init = c4.number_input("初始资金", 10000, 100_000_000, 100000, step=10000)
        fee = c5.number_input("手续费（万分之）", 0.0, 30.0, 0.6, step=0.1)
        lo = min((p["df"]["date"].min() for p in picked), default=pd.Timestamp("2015-01-01")).date()
        hi = max((p["df"]["date"].max() for p in picked), default=pd.Timestamp.today()).date()
        d1, d2, _ = st.columns([1, 1, 3])
        s = d1.date_input("回测开始（可选）", lo, min_value=lo, max_value=hi, key="rot_s")
        e = d2.date_input("回测结束", hi, min_value=lo, max_value=hi, key="rot_e")
        go_btn = st.button("🚀 开始回测", type="primary", disabled=len(picked) < 2)
    if go_btn:
        series = {p["code"]: p["df"] for p in picked}
        names = {p["code"]: p["name"] for p in picked}
        if len(series) < len(picked):
            series = {f"{p['code']}#{i}": p["df"] for i, p in enumerate(picked)}
            names = {f"{p['code']}#{i}": p["name"] for i, p in enumerate(picked)}
        with st.spinner("回测中…"):
            try:
                st.session_state["rot_R"] = (bt.rotation_backtest(
                    series, names, "week" if freq.startswith("每周") else "month", int(lookback), int(npos),
                    float(init), fee / 10000, s if s > lo else None, e), float(init))
            except Exception as ex:  # noqa: BLE001
                st.error(f"回测失败：{ex}")
    if "rot_R" in st.session_state:
        R, init0 = st.session_state["rot_R"]
        show_result(R, init0, "多基金")

# ================================================================== 双标的
else:
    st.caption("来源：donglianglhcv2.py · 每周一开盘前按上周五收盘计算动量择强，开盘换仓；单边成本 = 佣金 + 滑点")
    with st.container(border=True):
        src = st.radio("数据来源", ["在线获取（TickFlow 后复权）", "本地文件"], horizontal=True)
        if src.startswith("在线"):
            c1, c2, c3, c4 = st.columns(4)
            code1 = c1.text_input("标的 1", "159915.SZ")
            code2 = c2.text_input("标的 2", "510880.SH")
            sd = c3.date_input("开始日期", date(2015, 1, 1))
            ed = c4.date_input("结束日期", date.today())
            picked = None
        else:
            picked = ui.pick_series("dual", multi=True, label="选择两个品种")
            sd, ed = None, None
        c1, c2, c3, c4 = st.columns(4)
        lookback = c1.number_input("动量回看（交易日）", 5, 250, 22, key="d_lb")
        init = c2.number_input("初始资金", 10000, 100_000_000, 1_000_000, step=100000, key="d_init")
        comm = c3.number_input("佣金（万分之）", 0.0, 30.0, 0.6, step=0.1, key="d_comm")
        slip = c4.number_input("滑点（万分之）", 0.0, 50.0, 5.0, step=0.5, key="d_slip")
        go_btn = st.button("🚀 开始回测", type="primary", key="d_go")
    if go_btn:
        try:
            with st.spinner("获取数据并回测…"):
                if picked is None:
                    a = fetchers.tickflow_klines(fetchers.normalize_symbol(code1), None, ed.isoformat(), "backward")
                    b = fetchers.tickflow_klines(fetchers.normalize_symbol(code2), None, ed.isoformat(), "backward")
                    if a.empty or b.empty:
                        raise RuntimeError("数据获取失败，请检查代码、网络或 TickFlow 密钥")
                    A, B = dio.standardize(a, code1), dio.standardize(b, code2)
                    n1, n2 = A["name"], B["name"]
                    dfa, dfb = A["df"], B["df"]
                else:
                    if len(picked) != 2:
                        raise ValueError("请恰好选择两个品种")
                    dfa, dfb = picked[0]["df"], picked[1]["df"]
                    n1, n2 = picked[0]["name"], picked[1]["name"]
                st.session_state["dual_R"] = (bt.dual_momentum(dfa, dfb, n1, n2, int(lookback), float(init),
                                                               comm / 10000, slip / 10000, sd, ed), float(init))
        except Exception as ex:  # noqa: BLE001
            st.error(f"回测失败：{ex}")
    if "dual_R" in st.session_state:
        R, init0 = st.session_state["dual_R"]
        show_result(R, init0, "双标的")
