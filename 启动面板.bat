@echo off
chcp 65001 >nul
cd /d "%~dp0"
title A股投资工具箱 · 可视化面板

set "PY=python"
where python >nul 2>nul || set "PY=py"

echo ============================================
echo   A股投资工具箱 · 正在启动……
echo ============================================

%PY% -c "import streamlit, plotly, openpyxl" 2>nul
if errorlevel 1 (
    echo [1/3] 首次运行：安装面板依赖 streamlit / plotly / openpyxl ……
    %PY% -m pip install -U streamlit plotly pandas numpy requests openpyxl
)
%PY% -c "import tickflow" 2>nul
if errorlevel 1 (
    echo [2/3] 安装 tickflow（行情下载）……
    %PY% -m pip install tickflow
)
%PY% -c "import akshare" 2>nul
if errorlevel 1 (
    echo [3/3] 安装 akshare（指数 / 期货）……若失败不影响其他功能
    %PY% -m pip install akshare
)

echo.
echo 浏览器会自动打开 http://localhost:8520 ；关闭本窗口即可退出面板。
echo.
%PY% -m streamlit run app.py --server.port 8520
pause
