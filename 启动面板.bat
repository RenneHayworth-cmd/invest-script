@echo off
chcp 65001 >nul
cd /d "%~dp0"
title A股投资工具箱

set "PY=python"
where python >nul 2>nul || set "PY=py"

echo ============================================
echo   A股投资工具箱 · 正在启动……
echo ============================================

%PY% -c "import fastapi, uvicorn, pandas, openpyxl, requests" 2>nul
if errorlevel 1 (
    echo [1/3] 首次运行：安装 fastapi / uvicorn / pandas / openpyxl ……
    %PY% -m pip install -U fastapi uvicorn pandas numpy requests openpyxl
)
%PY% -c "import tickflow" 2>nul
if errorlevel 1 (
    echo [2/3] 安装 tickflow，用于行情下载……
    %PY% -m pip install tickflow
)
%PY% -c "import akshare" 2>nul
if errorlevel 1 (
    echo [3/3] 安装 akshare，用于指数与期货；失败不影响其他功能……
    %PY% -m pip install akshare
)

echo.
%PY% server.py
pause
