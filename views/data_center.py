# -*- coding: utf-8 -*-
"""数据中心：ETF/股票(前/后复权)、美股、场外基金净值、微盘股 BK1158"""
from datetime import date, timedelta
from pathlib import Path

import pandas as pd
import streamlit as st

from core import charts, fetchers, ui
from core import io as dio
from core.config import FUND_MAPPING

ui.header("📥", "数据中心", "下载的数据默认保存到左侧栏的「数据文件夹」，各分析页可直接选用")
save_dir = Path(st.session_state["data_dir"])

tab_cn, tab_us, tab_fund, tab_small = st.tabs(["🇨🇳 ETF / A股", "🇺🇸 美股", "💰 场外基金净值", "🔬 微盘股 BK1158"])


def _codes(text: str) -> list[str]:
    return [c.strip() for c in text.replace("，", ",").replace("\n", ",").replace(" ", ",").split(",") if c.strip()]


def _range_inputs(key: str, default_years: int = 5):
    c1, c2, c3 = st.columns([1, 1, 1])
    inception = c3.checkbox("成立以来", value=True, key=f"{key}_inc")
    s = c1.date_input("开始", date.today() - timedelta(days=365 * default_years), key=f"{key}_s",
                      disabled=inception)
    e = c2.date_input("结束", date.today(), key=f"{key}_e")
    return (None if inception else s.isoformat()), e.isoformat()


def _run_batch(symbols, start, end, adjust, suffix, name_fn):
    prog = st.progress(0.0, text="准备下载…")
    res = fetchers.tickflow_batch(symbols, start, end, adjust,
                                  on_progress=lambda i, n, s: prog.progress(i / n, text=f"已完成 {i}/{n}：{s}"))
    prog.empty()
    rows, frames = [], {}
    for sym in symbols:
        df, err = res.get(sym, (None, "未执行"))
        if df is not None and len(df):
            fname = f"{name_fn(sym)}{suffix}.csv"
            path = dio.save_df(df, save_dir, fname)
            frames[sym] = df
            rows.append({"代码": sym, "状态": "✅ 成功", "条数": len(df),
                         "起止": f"{df['trade_date'].min():%Y-%m-%d} ~ {df['trade_date'].max():%Y-%m-%d}",
                         "文件": path.name})
        else:
            rows.append({"代码": sym, "状态": "❌ 失败", "条数": 0, "起止": "", "文件": err})
    ui.table(pd.DataFrame(rows))
    if frames:
        curves = {}
        for s, d in frames.items():
            d = d.sort_values("trade_date")
            curves[s] = pd.Series((d["close"] / d["close"].iloc[0]).values, index=d["trade_date"].values)
        ui.plot(charts.multi_line(curves, title="下载结果预览（起点归一）", height=360))
    st.cache_data.clear()


def _cn_name(sym: str) -> str:
    code = sym.split(".")[0]
    return f"{code}{FUND_MAPPING.get(code, '')}"


# ------------------------------------------------------------------ A股
with tab_cn:
    st.caption("来源：ETFdataget.py / ETFdataget-后复权.py / datagetfree.py · 数据源 TickFlow")
    c1, c2 = st.columns([2, 1])
    with c1:
        txt = st.text_area("代码（逗号或换行分隔，可不写后缀）",
                           "512890, 159201, 159545, 159655, 159501, 518850, 513260, 159915", height=90)
    with c2:
        adj = st.radio("复权方式", ["前复权", "后复权", "不复权"], horizontal=False,
                       help="前复权适合看走势；后复权适合回测计算真实收益")
    start, end = _range_inputs("cn", 10)
    if st.button("开始下载", type="primary", key="cn_go"):
        syms = [fetchers.normalize_symbol(c) for c in _codes(txt)]
        adjust = {"前复权": "forward", "后复权": "backward", "不复权": "none"}[adj]
        suffix = {"前复权": "", "后复权": "-后复权", "不复权": "-不复权"}[adj]
        try:
            _run_batch(syms, start, end, adjust, suffix, _cn_name)
        except Exception as e:  # noqa: BLE001
            st.error(f"下载失败：{e}")

# ------------------------------------------------------------------ 美股
with tab_us:
    st.caption("来源：tickflow_USdata_fetcher.py · 数据源 TickFlow（自动加 .US 后缀，前复权）")
    txt_us = st.text_area("美股代码", "SPMO, QQQ, SPY", height=80, key="us_txt")
    start_us, end_us = _range_inputs("us", 5)
    if st.button("开始下载", type="primary", key="us_go"):
        syms = [fetchers.normalize_symbol(c, "US") for c in _codes(txt_us)]
        try:
            _run_batch(syms, start_us, end_us, "forward", "", lambda s: s.replace(".US", "") + "_US")
        except Exception as e:  # noqa: BLE001
            st.error(f"下载失败：{e}")

# ------------------------------------------------------------------ 场外基金
with tab_fund:
    st.caption("来源：fund_complete_data_get.py / 批量脚本/jjjz.py · 数据源 东方财富基金净值接口")
    c1, c2 = st.columns([2, 1])
    txt_f = c1.text_area("基金代码（可批量）", "110020, 161725", height=80, key="fund_txt")
    mode = c2.radio("范围", ["全部历史", "最新 20 条"], key="fund_mode")
    if st.button("获取净值", type="primary", key="fund_go"):
        codes = _codes(txt_f)
        prog = st.progress(0.0)
        rows, got = [], {}
        for i, code in enumerate(codes, 1):
            prog.progress(i / len(codes), text=f"正在获取 {code}（{i}/{len(codes)}）")
            try:
                df = fetchers.fund_nav_history(code, latest_only=(mode != "全部历史"))
                if df.empty:
                    rows.append({"代码": code, "状态": "❌ 无数据", "条数": 0, "文件": ""})
                    continue
                path = dio.save_df(df, save_dir, f"fund_{code}.csv")
                got[code] = df
                rows.append({"代码": code, "状态": "✅ 成功", "条数": len(df),
                             "起止": f"{df['日期'].min():%Y-%m-%d} ~ {df['日期'].max():%Y-%m-%d}",
                             "最新累计净值": df["累计净值"].iloc[-1], "文件": path.name})
            except Exception as e:  # noqa: BLE001
                rows.append({"代码": code, "状态": "❌ 失败", "条数": 0, "文件": str(e)})
        prog.empty()
        ui.table(pd.DataFrame(rows))
        for code, df in got.items():
            with st.expander(f"{code} 净值明细（{len(df)} 条）", expanded=len(got) == 1):
                c1, c2 = st.columns([2, 1])
                with c1:
                    ui.plot(charts.price_drawdown(df.rename(columns={"日期": "date", "累计净值": "price"}),
                                                  f"{code} 累计净值"))
                with c2:
                    ui.table(df.sort_values("日期", ascending=False).head(200), height=480)
        st.cache_data.clear()

# ------------------------------------------------------------------ 微盘股
with tab_small:
    st.caption("来源：wpg.py / wpg30.py · 东方财富板块成分，按总市值升序")
    c1, c2, c3 = st.columns([1, 1, 2])
    board = c1.text_input("板块代码", "BK1158")
    topn = c2.number_input("取最小前 N 只", 5, 200, 30, step=5)
    if st.button("获取名单", type="primary", key="small_go"):
        try:
            df = fetchers.board_smallest(board, int(topn))
            if df.empty:
                st.warning("没有返回数据")
            else:
                st.session_state["small_df"] = df
        except Exception as e:  # noqa: BLE001
            st.error(f"{e}\n\n提示：如持续失败，请检查网络或代理设置。")
    df = st.session_state.get("small_df")
    if df is not None:
        ui.kpi_row([("成分数量", f"{len(df)}", "", f"板块 {board}"),
                    ("市值中位数", f"{df['总市值(亿元)'].median():.2f} 亿", "", ""),
                    ("最小市值", f"{df['总市值(亿元)'].min():.2f} 亿", "", df.iloc[0]["名称"]),
                    ("今日上涨占比", ui.pct((df['涨跌幅(%)'] > 0).mean(), 0, sign=False), "", "")])
        st.write("")
        c1, c2 = st.columns([1.2, 1])
        with c1:
            ui.table(df, height=520, column_config={
                "总市值(亿元)": st.column_config.ProgressColumn("总市值(亿元)", min_value=0,
                                                              max_value=float(df["总市值(亿元)"].max()),
                                                              format="%.2f"),
                "涨跌幅(%)": st.column_config.NumberColumn(format="%.2f%%")})
        with c2:
            ui.plot(charts.score_bar(df.head(30).assign(标签=lambda d: d["名称"]), "总市值(亿元)", "标签",
                                     "总市值（亿元）"))
        b1, b2 = st.columns(2)
        with b1:
            ui.download_csv(df, f"{board}_lowest_{len(df)}.csv")
        with b2:
            if st.button("保存到数据文件夹", key="small_save", **ui.STRETCH):
                p = dio.save_df(df, save_dir.parent if save_dir.name == "stock_data" else save_dir,
                                f"{board}_lowest_{len(df)}.csv")
                st.success(f"已保存：{p}")
