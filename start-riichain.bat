@echo off
chcp 65001 >nul
cd /d "C:\Users\96153\projects\riichain"
"C:\Users\96153\.workbuddy\binaries\python\versions\3.13.12\Scripts\uvicorn.exe" app.main:app --host 0.0.0.0 --port 8081
pause
