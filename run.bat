@echo off
chcp 65001 >nul
title Facebook Fanpage Auto-Poster
color 0b

echo =====================================================================
echo          FACEBOOK FANPAGE AUTO-POSTER ^& CONTENT GENERATOR
echo                    Powered by Google Gemini 2.5
echo =====================================================================
echo.

REM Kiem tra Python tren he thong
where python >nul 2>nul
if %errorlevel% neq 0 (
    echo [ERROR] Khong tim thay Python tren he thong!
    echo Vui long cai dat Python 3.10+ tu https://www.python.org/ va tich chon "Add Python to PATH".
    pause
    exit /b 1
)

REM Kiem tra va kich hoat virtual environment neu co
if exist venv\Scripts\activate.bat (
    echo [*] Dang kich hoat moi truong ao venv...
    call venv\Scripts\activate.bat
) else if exist .venv\Scripts\activate.bat (
    echo [*] Dang kich hoat moi truong ao .venv...
    call .venv\Scripts\activate.bat
)

REM Kiem tra streamlit da duoc cai dat chua
python -c "import streamlit" >nul 2>nul
if %errorlevel% neq 0 (
    echo [*] Dang cai dat cac thu vien can thiet tu requirements.txt...
    pip install -r requirements.txt
    if %errorlevel% neq 0 (
        echo [ERROR] Cai dat thu vien that bai! Vui long kiem tra ket noi Internet.
        pause
        exit /b 1
    )
)

REM Tu dong bo qua man hinh hoi Email lan dau cua Streamlit
if not exist "%USERPROFILE%\.streamlit" mkdir "%USERPROFILE%\.streamlit"
if not exist "%USERPROFILE%\.streamlit\credentials.toml" (
    (
        echo [general]
        echo email = ""
    ) > "%USERPROFILE%\.streamlit\credentials.toml"
)

echo [*] Dang khoi chay Streamlit Web Dashboard...
echo [*] Trinh duyet se tu dong mo tai: http://localhost:8501
echo [*] Nhan Ctrl+C de dung ung dung.
echo.
streamlit run app.py --server.port 8501 --browser.gatherUsageStats false

if %errorlevel% neq 0 (
    echo.
    echo [ERROR] Ung dung bi dung dot ngot voi ma loi %errorlevel%.
    pause
)
