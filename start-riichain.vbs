Set WshShell = CreateObject("WScript.Shell")
WshShell.Run "C:\Users\96153\.workbuddy\binaries\python\versions\3.13.12\pythonw.exe -m uvicorn app.main:app --host 0.0.0.0 --port 8081", 0, False
