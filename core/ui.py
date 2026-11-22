# -*- coding: utf-8 -*-
"""Streamlit 界面公共组件：样式、页眉、指标卡、数据选择器、下载按钮"""
from datetime import datetime
from pathlib import Path

import pandas as pd
import streamlit as st

from . import io as dio
from .config import DEFAULT_DATA_DIR, DEFAULT_OUTPUT_DIR, DOWN, MUTED, PRIMARY, UP

def _ver():
    try:
        return tuple(int(x) for x in st.__version__.split(".")[:2])
    except Exception:  # noqa: BLE001
        return (1, 40)


# 新版 Streamlit 用 width="stretch"，旧版用 use_container_width=True
STRETCH = {"width": "stretch"} if _ver() >= (1, 49) else {"use_container_width": True}

CSS = f"""
<style>
:root {{ --primary:{PRIMARY}; --up:{UP}; --down:{DOWN}; --muted:{MUTED}; }}
html, body, [class*="css"] {{ font-family: Inter, "PingFang SC", "Microsoft YaHei", "Segoe UI", sans-serif; }}
.block-container {{ padding-top: 2.2rem; padding-bottom: 3rem; max-width: 1380px; }}
section[data-testid="stSidebar"] {{ background: #F8FAFC; border-right: 1px solid #EEF1F6; }}
h1, h2, h3 {{ letter-spacing: -0.01em; }}
.qh-header {{ display:flex; align-items:center; gap:14px; margin-bottom: 6px; }}
.qh-icon {{ width:44px; height:44px; border-radius:12px; display:flex; align-items:center; justify-content:center;
           font-size:22px; background: linear-gradient(135deg,#EFF6FF,#DBEAFE); }}
.qh-title {{ font-size: 1.65rem; font-weight: 700; color:#0F172A; line-height:1.2; }}
.qh-sub {{ color: var(--muted); font-size: .92rem; margin-top:2px; }}
.kpi {{ background:#FFFFFF; border:1px solid #EEF1F6; border-radius:14px; padding:14px 16px;
        box-shadow: 0 1px 2px rgba(15,23,42,.04); height:100%; }}
.kpi .lbl {{ color: var(--muted); font-size:.8rem; margin-bottom:6px; }}
.kpi .val {{ font-size:1.45rem; font-weight:700; color:#0F172A; font-variant-numeric: tabular-nums; }}
.kpi .val.up {{ color: var(--up); }} .kpi .val.down {{ color: var(--down); }}
.kpi .hint {{ color:#94A3B8; font-size:.75rem; margin-top:4px; }}
.card {{ background:#FFFFFF; border:1px solid #EEF1F6; border-radius:16px; padding:18px 20px;
         box-shadow: 0 1px 2px rgba(15,23,42,.04); height:100%; }}
.card h4 {{ margin:0 0 6px 0; font-size:1.02rem; color:#0F172A; }}
.card p {{ margin:0; color: var(--muted); font-size:.86rem; line-height:1.55; }}
.card .tag {{ display:inline-block; font-size:.72rem; padding:2px 8px; border-radius:999px; margin:8px 6px 0 0;
              background:#F1F5F9; color:#475569; }}
.pill {{ display:inline-block; padding:2px 10px; border-radius:999px; font-size:.78rem; font-weight:600; }}
.pill.up {{ background:#FEE2E2; color:#B91C1C; }} .pill.down {{ background:#DCFCE7; color:#15803D; }}
.pill.mid {{ background:#F1F5F9; color:#475569; }}
div[data-testid="stTabs"] button p {{ font-size: .95rem; }}
div[data-testid="stDataFrame"] {{ border:1px solid #EEF1F6; border-radius:12px; }}
.stButton>button, .stDownloadButton>button {{ border-radius:10px; }}
</style>
"""


def setup_page():
    st.markdown(CSS, unsafe_allow_html=True)
    st.session_state.setdefault("data_dir", str(DEFAULT_DATA_DIR))
    st.session_state.setdefault("output_dir", str(DEFAULT_OUTPUT_DIR))


def header(icon: str, title: str, sub: str = ""):
    st.markdown(f'<div class="qh-header"><div class="qh-icon">{icon}</div><div>'
                f'<div class="qh-title">{title}</div><div class="qh-sub">{sub}</div></div></div>',
                unsafe_allow_html=True)


# ---------------------------------------------------------------- 格式化
def pct(v, digits=2, sign=True) -> str:
    if v is None or pd.isna(v):
        return "—"
    return f"{v * 100:+.{digits}f}%" if sign else f"{v * 100:.{digits}f}%"


def num(v, digits=4) -> str:
    if v is None or pd.isna(v):
        return "—"
    return f"{v:,.{digits}f}"


def kpi(label: str, value: str, tone: str = "", hint: str = ""):
    """tone: 'up' 红 / 'down' 绿 / '' 默认"""
    st.markdown(f'<div class="kpi"><div class="lbl">{label}</div><div class="val {tone}">{value}</div>'
                f'{f"<div class=hint>{hint}</div>" if hint else ""}</div>', unsafe_allow_html=True)


def tone_of(v) -> str:
    if v is None or pd.isna(v):
        return ""
    return "up" if v > 0 else ("down" if v < 0 else "")


def kpi_row(items: list[tuple]):
    """items: [(label, value_str, tone, hint), ...]"""
    cols = st.columns(len(items))
    for c, it in zip(cols, items):
        with c:
            kpi(*it)


def pill(text: str, tone: str = "mid") -> str:
    return f'<span class="pill {tone}">{text}</span>'


# ---------------------------------------------------------------- 数据选择
@st.cache_data(show_spinner=False)
def _load_cached(path: str, mtime: float):
    return dio.load_price(path)


def load_path(path) -> dict:
    p = Path(path)
    return _load_cached(str(p), p.stat().st_mtime)


def pick_series(key: str, multi: bool = False, label: str = "选择数据文件", default_all: bool = False,
                help_text: str = "支持 TickFlow K线、东财基金净值、Excel 等格式，自动识别日期与价格列") -> list[dict]:
    """返回 [标准化数据 dict, ...]；同时支持从数据文件夹选择和直接上传"""
    data_dir = Path(st.session_state.get("data_dir", DEFAULT_DATA_DIR))
    files = dio.list_data_files(data_dir)
    t1, t2 = st.tabs(["📁 数据文件夹", "⬆️ 上传文件"])
    out = []
    with t1:
        if not files:
            st.info(f"数据文件夹里还没有 CSV/Excel：`{data_dir}`。可以先到「数据中心」下载，或在左侧栏修改文件夹。")
        else:
            names = [f.name for f in files]
            if multi:
                sel = st.multiselect(label, names, default=names if default_all else names[:min(2, len(names))],
                                     key=f"{key}_ms", help=help_text)
            else:
                one = st.selectbox(label, names, key=f"{key}_sb", help=help_text)
                sel = [one] if one else []
            for n in sel:
                try:
                    out.append(load_path(data_dir / n))
                except Exception as e:  # noqa: BLE001
                    st.warning(str(e))
    with t2:
        ups = st.file_uploader("拖入文件", type=["csv", "xlsx", "xls"], accept_multiple_files=multi,
                               key=f"{key}_up", help=help_text)
        ups = ups if isinstance(ups, list) else ([ups] if ups else [])
        if ups:
            out = []  # 上传优先
            for u in ups:
                try:
                    out.append(dio.load_price(u, u.name))
                except Exception as e:  # noqa: BLE001
                    st.warning(str(e))
    return out


def date_filter(df: pd.DataFrame, key: str) -> pd.DataFrame:
    lo, hi = df["date"].min().date(), df["date"].max().date()
    c1, c2 = st.columns(2)
    s = c1.date_input("开始日期", lo, min_value=lo, max_value=hi, key=f"{key}_s")
    e = c2.date_input("结束日期", hi, min_value=lo, max_value=hi, key=f"{key}_e")
    m = (df["date"] >= pd.Timestamp(s)) & (df["date"] <= pd.Timestamp(e))
    return df[m].reset_index(drop=True)


# ---------------------------------------------------------------- 导出
def stamp() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def download_csv(df: pd.DataFrame, filename: str, label: str = "下载 CSV", key: str | None = None):
    st.download_button(label, df.to_csv(index=False).encode("utf-8-sig"), file_name=filename,
                       mime="text/csv", key=key or f"dl_{filename}", **STRETCH)


def download_excel(sheets: dict, filename: str, label: str = "下载 Excel", key: str | None = None):
    st.download_button(label, dio.to_excel_bytes(sheets), file_name=filename, key=key or f"dlx_{filename}",
                       mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                       **STRETCH)


def download_html(fig, filename: str, label: str = "下载交互图 HTML", key: str | None = None):
    st.download_button(label, fig.to_html(include_plotlyjs="cdn").encode("utf-8"), file_name=filename,
                       mime="text/html", key=key or f"dlh_{filename}", **STRETCH)


PLOT_CFG = {"displaylogo": False, "modeBarButtonsToRemove": ["lasso2d", "select2d"],
            "toImageButtonOptions": {"format": "png", "scale": 2}}


def plot(fig):
    st.plotly_chart(fig, config=PLOT_CFG, **STRETCH)


def table(df: pd.DataFrame, height: int | None = None, **kw):
    """统一表格样式"""
    if height:
        kw["height"] = height
    st.dataframe(df, hide_index=True, **STRETCH, **kw)
