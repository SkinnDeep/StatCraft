@echo off
echo ========================================================
echo Installing StatCraft Developers Official Certificate...
echo ========================================================
echo.
certutil -user -addstore -f Root "%~dp0StatCraft-Certificate.cer"
certutil -user -addstore -f TrustedPublisher "%~dp0StatCraft-Certificate.cer"
echo.
echo ========================================================
echo Certificate registered! Windows SmartScreen is now bypassed.
echo ========================================================
pause
