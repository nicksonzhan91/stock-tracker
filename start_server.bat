@echo off
echo 台股儀表板伺服器啟動中...
echo 電腦瀏覽器：http://localhost:8080/web/index.html
echo 手機請輸入：http://192.168.8.104:8080/web/index.html
echo.
echo 按 Ctrl+C 可停止伺服器
C:\Users\nicks\AppData\Local\Programs\Python\Python314\python.exe -m http.server 8080 --directory "D:\ClaudeCode工作區\stock-tracker"
