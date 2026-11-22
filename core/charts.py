# -*- coding: utf-8 -*-
"""Plotly 图表工厂：统一浅色简洁风"""
import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from .config import DOWN, GRID, MUTED, PALETTE, PRIMARY, UP

FONT = "Inter, 'PingFang SC', 'Microsoft YaHei', 'Segoe UI', sans-serif"


def style(fig: go.Figure, height: int = 420, legend_top: bool = True, hover="x unified") -> go.Figure:
    fig.update_layout(
        template="plotly_white", height=height, font=dict(family=FONT, size=13, color="#1F2937"),
        margin=dict(l=10, r=10, t=40 if legend_top else 20, b=10), hovermode=hover,
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", colorway=PALETTE,
        hoverlabel=dict(bgcolor="white", bordercolor="#E5E7EB", font=dict(family=FONT, size=12)),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0,
                    bgcolor="rgba(0,0,0,0)") if legend_top else {},
    )
    fig.update_xaxes(showgrid=False, linecolor="#E5E7EB", ticks="outside", tickcolor="#E5E7EB")
    fig.update_yaxes(gridcolor=GRID, zeroline=False, linecolor="rgba(0,0,0,0)")
    return fig


def _rangeselector(fig):
    fig.update_xaxes(rangeselector=dict(
        buttons=[dict(count=6, label="6月", step="month", stepmode="backward"),
                 dict(count=1, label="1年", step="year", stepmode="backward"),
                 dict(count=3, label="3年", step="year", stepmode="backward"),
                 dict(count=1, label="今年", step="year", stepmode="todate"),
                 dict(step="all", label="全部")],
        bgcolor="#F1F5F9", activecolor="#DBEAFE", font=dict(size=11)))
    return fig


def price_drawdown(df: pd.DataFrame, name: str, extra: dict | None = None) -> go.Figure:
    """上：价格/净值（可叠加均线等）；下：回撤面积图"""
    fig = make_subplots(rows=2, cols=1, shared_xaxes=True, row_heights=[0.72, 0.28], vertical_spacing=0.04)
    fig.add_trace(go.Scatter(x=df["date"], y=df["price"], name=name, line=dict(color=PRIMARY, width=1.8)),
                  row=1, col=1)
    for i, (k, s) in enumerate((extra or {}).items()):
        fig.add_trace(go.Scatter(x=df["date"], y=s, name=k,
                                 line=dict(width=1.2, color=PALETTE[(i + 1) % len(PALETTE)])), row=1, col=1)
    dd = df["price"] / df["price"].cummax() - 1
    fig.add_trace(go.Scatter(x=df["date"], y=dd * 100, name="回撤(%)", fill="tozeroy",
                             line=dict(color=DOWN, width=1), fillcolor="rgba(18,161,80,0.15)"), row=2, col=1)
    fig.update_yaxes(title_text="回撤 %", row=2, col=1, ticksuffix="%")
    return style(fig, 560)


def rolling_return_chart(df: pd.DataFrame, s: pd.Series, years: int) -> go.Figure:
    v = s * 100
    fig = go.Figure()
    pos = v.where(v >= 0)
    neg = v.where(v < 0)
    fig.add_trace(go.Scatter(x=df["date"], y=pos, name="正收益", fill="tozeroy", mode="lines",
                             line=dict(color=UP, width=1.4), fillcolor="rgba(229,72,77,0.12)"))
    fig.add_trace(go.Scatter(x=df["date"], y=neg, name="负收益", fill="tozeroy", mode="lines",
                             line=dict(color=DOWN, width=1.4), fillcolor="rgba(18,161,80,0.12)"))
    valid = v.dropna()
    if len(valid):
        fig.add_hline(y=valid.mean(), line=dict(color=MUTED, dash="dot", width=1),
                      annotation_text=f"均值 {valid.mean():.2f}%", annotation_position="top left")
        for idx, lab, col in ((valid.idxmax(), "最高", UP), (valid.idxmin(), "最低", DOWN)):
            fig.add_annotation(x=df["date"][idx], y=valid[idx], text=f"{lab} {valid[idx]:.2f}%",
                               showarrow=True, arrowhead=2, arrowcolor=col, font=dict(color=col),
                               bgcolor="white", bordercolor=col)
    fig.update_yaxes(ticksuffix="%")
    fig.update_layout(title=dict(text=f"{years} 年滚动年化收益率", x=0, font=dict(size=15)))
    return style(fig, 380)


def drawdown_periods_chart(df: pd.DataFrame, periods: pd.DataFrame, top: int = 5) -> go.Figure:
    """净值曲线 + 前 N 大回撤波段阴影"""
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=df["date"], y=df["price"], name="价格", line=dict(color=PRIMARY, width=1.6)))
    if periods is not None and not periods.empty:
        worst = periods.nsmallest(top, "回撤深度(%)")
        last = df["date"].iloc[-1]
        for _, r in worst.iterrows():
            x1 = pd.Timestamp(r["修复完成"]) if pd.notna(r["修复完成"]) else last
            fig.add_vrect(x0=pd.Timestamp(r["开始"]), x1=x1, fillcolor="rgba(229,72,77,0.08)", line_width=0,
                          annotation_text=f"{r['回撤深度(%)']:.1f}%", annotation_position="top left",
                          annotation_font=dict(color=UP, size=11))
            fig.add_vline(x=pd.Timestamp(r["谷底"]), line=dict(color="rgba(229,72,77,0.45)", width=1, dash="dot"))
    fig.update_layout(title=dict(text=f"最大的 {top} 次回撤波段", x=0, font=dict(size=15)))
    return style(fig, 380)


def yearly_bar(tbl: pd.DataFrame) -> go.Figure:
    colors = [UP if v >= 0 else DOWN for v in tbl["年度涨幅(%)"]]
    fig = go.Figure()
    fig.add_trace(go.Bar(x=tbl["年份"].astype(str), y=tbl["年度涨幅(%)"], name="年度涨幅",
                         marker_color=colors, text=[f"{v:.1f}%" for v in tbl["年度涨幅(%)"]],
                         textposition="outside", cliponaxis=False))
    fig.add_trace(go.Scatter(x=tbl["年份"].astype(str), y=tbl["年度最大回撤(%)"], name="年内最大回撤",
                             mode="markers+lines", line=dict(color=MUTED, dash="dot", width=1),
                             marker=dict(size=8, color="white", line=dict(color=MUTED, width=2))))
    fig.update_yaxes(ticksuffix="%")
    return style(fig, 360, hover="x")


def ma_chart(d: pd.DataFrame, name: str, periods) -> go.Figure:
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=d["date"], y=d["price"], name=name, line=dict(color="#111827", width=1.6)))
    cols = ["#2563EB", "#F59E0B", "#8B5CF6", "#10B981"]
    for i, n in enumerate(periods):
        fig.add_trace(go.Scatter(x=d["date"], y=d[f"MA{n}"], name=f"MA{n}",
                                 line=dict(width=1.3, color=cols[i % 4])))
    _rangeselector(fig)
    return style(fig, 460)


def rsi_chart(t: pd.DataFrame) -> go.Figure:
    fig = make_subplots(rows=3, cols=1, shared_xaxes=True, row_heights=[0.5, 0.25, 0.25], vertical_spacing=0.04)
    fig.add_trace(go.Scatter(x=t["日期"], y=t["价格"], name="价格", line=dict(color=PRIMARY, width=1.5)), 1, 1)
    fig.add_trace(go.Scatter(x=t["日期"], y=t["RSI(14)"], name="RSI(14)", line=dict(color="#8B5CF6", width=1.2)), 2, 1)
    fig.add_hrect(y0=70, y1=100, fillcolor="rgba(229,72,77,0.08)", line_width=0, row=2, col=1)
    fig.add_hrect(y0=0, y1=30, fillcolor="rgba(18,161,80,0.08)", line_width=0, row=2, col=1)
    fig.add_hline(y=70, line=dict(color=UP, dash="dot", width=1), row=2, col=1)
    fig.add_hline(y=30, line=dict(color=DOWN, dash="dot", width=1), row=2, col=1)
    fig.add_trace(go.Scatter(x=t["日期"], y=t["价格百分位"], name="价格百分位", fill="tozeroy",
                             line=dict(color="#F59E0B", width=1), fillcolor="rgba(245,158,11,0.12)"), 3, 1)
    fig.update_yaxes(range=[0, 100], row=2, col=1)
    fig.update_yaxes(range=[0, 100], ticksuffix="%", row=3, col=1)
    return style(fig, 620)


def gauge(value: float, title: str, lo=30, hi=70) -> go.Figure:
    fig = go.Figure(go.Indicator(
        mode="gauge+number", value=value if pd.notna(value) else 0,
        number=dict(font=dict(size=34)), title=dict(text=title, font=dict(size=13, color=MUTED)),
        gauge=dict(axis=dict(range=[0, 100], tickwidth=1, tickcolor="#CBD5E1"),
                   bar=dict(color=PRIMARY, thickness=0.28), bgcolor="white", borderwidth=0,
                   steps=[dict(range=[0, lo], color="#DCFCE7"), dict(range=[lo, hi], color="#F1F5F9"),
                          dict(range=[hi, 100], color="#FEE2E2")])))
    fig.update_layout(height=210, margin=dict(l=20, r=20, t=40, b=0), paper_bgcolor="rgba(0,0,0,0)",
                      font=dict(family=FONT))
    return fig


def multi_line(series: dict, title: str = "", pct: bool = False, height: int = 420,
               highlight: str | None = None) -> go.Figure:
    fig = go.Figure()
    for i, (k, s) in enumerate(series.items()):
        w = 2.6 if k == highlight else 1.4
        fig.add_trace(go.Scatter(x=s.index, y=s.values, name=k, line=dict(width=w, color=PALETTE[i % len(PALETTE)])))
    if pct:
        fig.update_yaxes(ticksuffix="%")
    if title:
        fig.update_layout(title=dict(text=title, x=0, font=dict(size=15)))
    return style(fig, height)


def equity_chart(nav: pd.DataFrame, bench: dict, init: float) -> go.Figure:
    fig = make_subplots(rows=2, cols=1, shared_xaxes=True, row_heights=[0.72, 0.28], vertical_spacing=0.04)
    for i, (k, s) in enumerate(bench.items()):
        fig.add_trace(go.Scatter(x=s.index, y=s.values / init, name=k,
                                 line=dict(width=1.1, color=PALETTE[(i + 1) % len(PALETTE)], dash="dot")), 1, 1)
    fig.add_trace(go.Scatter(x=nav["date"], y=nav["value"] / init, name="轮动策略",
                             line=dict(width=2.4, color=PRIMARY),
                             customdata=nav["holdings"], hovertemplate="%{y:.3f} · 持有：%{customdata}"), 1, 1)
    fig.add_trace(go.Scatter(x=nav["date"], y=nav["drawdown"] * 100, name="策略回撤", fill="tozeroy",
                             line=dict(color=DOWN, width=1), fillcolor="rgba(18,161,80,0.15)"), 2, 1)
    fig.update_yaxes(title_text="净值(起点=1)", row=1, col=1)
    fig.update_yaxes(title_text="回撤 %", ticksuffix="%", row=2, col=1)
    return style(fig, 580)


def donut(labels, values, title="") -> go.Figure:
    fig = go.Figure(go.Pie(labels=labels, values=values, hole=0.62, sort=False,
                           marker=dict(colors=PALETTE, line=dict(color="white", width=2)),
                           textinfo="percent", hovertemplate="%{label}<br>%{value}<extra></extra>"))
    fig.update_layout(height=320, margin=dict(l=0, r=0, t=30 if title else 0, b=0), showlegend=True,
                      legend=dict(orientation="v", x=1, y=0.5), paper_bgcolor="rgba(0,0,0,0)",
                      title=dict(text=title, x=0, font=dict(size=14)), font=dict(family=FONT))
    return fig


def monthly_heatmap(nav: pd.DataFrame) -> go.Figure:
    s = nav.set_index("date")["value"].resample("ME").last().pct_change() * 100
    t = pd.DataFrame({"y": s.index.year, "m": s.index.month, "v": s.values}).dropna()
    pv = t.pivot(index="y", columns="m", values="v").reindex(columns=range(1, 13))
    fig = go.Figure(go.Heatmap(
        z=pv.values, x=[f"{m}月" for m in pv.columns], y=pv.index.astype(str),
        colorscale=[[0, DOWN], [0.5, "#FFFFFF"], [1, UP]], zmid=0,
        text=np.where(np.isnan(pv.values), "", np.vectorize(lambda v: f"{v:.1f}")(np.nan_to_num(pv.values))),
        texttemplate="%{text}", hovertemplate="%{y}年%{x}：%{z:.2f}%<extra></extra>", showscale=False,
        xgap=2, ygap=2))
    fig.update_yaxes(autorange="reversed")
    return style(fig, 60 + 34 * max(len(pv), 3), legend_top=False, hover="closest")


def score_bar(df: pd.DataFrame, x: str, y: str, title: str = "") -> go.Figure:
    d = df.sort_values(x)
    colors = [UP if v >= 0 else DOWN for v in d[x]]
    fig = go.Figure(go.Bar(x=d[x], y=d[y], orientation="h", marker_color=colors,
                           text=[f"{v:.2f}" for v in d[x]], textposition="outside", cliponaxis=False))
    fig.update_layout(title=dict(text=title, x=0, font=dict(size=15)))
    return style(fig, max(300, 34 * len(d) + 80), legend_top=False, hover="closest")


def bias_bars(latest: pd.DataFrame) -> go.Figure:
    d = latest.sort_values("偏离率(%)")
    colors = [UP if v >= 0 else DOWN for v in d["偏离率(%)"]]
    fig = go.Figure(go.Bar(x=d["偏离率(%)"], y=d["指数"], orientation="h", marker_color=colors,
                           text=[f"{v:+.2f}%" for v in d["偏离率(%)"]], textposition="outside", cliponaxis=False))
    fig.add_vline(x=0, line=dict(color="#CBD5E1", width=1))
    fig.update_xaxes(ticksuffix="%")
    return style(fig, max(280, 40 * len(d) + 60), legend_top=False, hover="closest")
