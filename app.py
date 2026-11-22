# -*- coding: utf-8 -*-
"""A股投资工具箱 · 可视化面板
启动：streamlit run app.py   （或双击 启动面板.bat）
"""
import sys
from pathlib import Path

import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent))

from core import ui  # noqa: E402
from core.config import get_tickflow_key  # noqa: E402

st.set_page_config(page_title="A股投资工具箱", page_icon="📈", layout="wide", initial_sidebar_state="expanded")
ui.setup_page()

V = Path(__file__).resolve().parent / "views"
pages = {
    "首页": [st.Page(str(V / "home.py"), title="总览", icon="🏠", default=True)],
    "数据": [st.Page(str(V / "data_center.py"), title="数据中心", icon="📥")],
    "分析": [
        st.Page(str(V / "single.py"), title="单品种分析", icon="🔍"),
        st.Page(str(V / "market.py"), title="指数与期货", icon="🌐"),
    ],
    "策略": [
        st.Page(str(V / "backtest.py"), title="轮动回测", icon="🔁"),
        st.Page(str(V / "spmo.py"), title="SPMO 选基", icon="🏆"),
    ],
}
nav = st.navigation(pages)

with st.sidebar:
    st.markdown("### ⚙️ 设置")
    st.session_state["data_dir"] = st.text_input(
        "数据文件夹", st.session_state["data_dir"],
        help="分析页从这里列出 CSV/Excel；数据中心的下载也默认保存到这里")
    st.session_state["output_dir"] = st.text_input("报告输出文件夹", st.session_state["output_dir"])
    if get_tickflow_key():
        st.success("TickFlow 密钥：已从环境变量读取", icon="🔑")
    else:
        st.warning("未设置 TICKFLOW_API_KEY，将使用免费版（数据条数有限）", icon="🔑")
    st.caption("数据仅供研究参考，不构成投资建议")

nav.run()
