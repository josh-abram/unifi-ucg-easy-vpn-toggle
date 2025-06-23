@echo off
REM Quick VPN toggle script for UniFi UCG Ultra (Windows)
REM This script checks the current VPN status and toggles it

setlocal enabledelayedexpansion

REM Configuration - modify these variables as needed
set "VPN_NAME="
REM Leave VPN_NAME empty to use the first VPN found, or specify a name like "ExpressVPN"

REM Get script directory
set "SCRIPT_DIR=%~dp0"
set "PYTHON_SCRIPT=%SCRIPT_DIR%unifi_vpn_manager.py"
set "TEMP_STATUS=%TEMP%\unifi_vpn_status.json"

echo [INFO] Checking current VPN status...

REM Check if Python script exists
if not exist "%PYTHON_SCRIPT%" (
    echo [ERROR] Python script not found: %PYTHON_SCRIPT%
    pause
    exit /b 1
)

REM Get current status
if "%VPN_NAME%"=="" (
    python "%PYTHON_SCRIPT%" --action status > "%TEMP_STATUS%" 2>nul
) else (
    python "%PYTHON_SCRIPT%" --action status --vpn-name "%VPN_NAME%" > "%TEMP_STATUS%" 2>nul
)

REM Check if command was successful
if %errorlevel% neq 0 (
    echo [ERROR] Failed to get VPN status. Check your configuration and network connection.
    if exist "%TEMP_STATUS%" del "%TEMP_STATUS%"
    pause
    exit /b 1
)

REM Check for errors in the output
findstr /c:"\"error\"" "%TEMP_STATUS%" >nul
if %errorlevel%==0 (
    echo [ERROR] VPN client not found or error occurred:
    type "%TEMP_STATUS%"
    del "%TEMP_STATUS%"
    pause
    exit /b 1
)

REM Determine current status
findstr /c:"\"enabled\": true" "%TEMP_STATUS%" >nul
if %errorlevel%==0 (
    set "CURRENT_STATUS=enabled"
    goto :toggle_vpn
)

findstr /c:"\"enabled\": false" "%TEMP_STATUS%" >nul
if %errorlevel%==0 (
    set "CURRENT_STATUS=disabled"
    goto :toggle_vpn
)

REM Handle multiple VPN clients case
findstr /c:"\"vpn_clients\"" "%TEMP_STATUS%" >nul
if %errorlevel%==0 (
    echo [WARN] Multiple VPN clients found. Using the first one or specify VPN_NAME in script
    REM Check first few lines for enabled status
    for /f "tokens=*" %%a in ('findstr /n /c:"\"enabled\"" "%TEMP_STATUS%"') do (
        echo %%a | findstr /c:"true" >nul
        if !errorlevel!==0 (
            set "CURRENT_STATUS=enabled"
            goto :toggle_vpn
        )
        echo %%a | findstr /c:"false" >nul
        if !errorlevel!==0 (
            set "CURRENT_STATUS=disabled"
            goto :toggle_vpn
        )
    )
)

echo [ERROR] Could not determine VPN status from output:
type "%TEMP_STATUS%"
del "%TEMP_STATUS%"
pause
exit /b 1

:toggle_vpn
del "%TEMP_STATUS%"

if "%CURRENT_STATUS%"=="enabled" (
    echo [INFO] VPN is currently enabled. Pausing...
    if "%VPN_NAME%"=="" (
        python "%PYTHON_SCRIPT%" --action pause
    ) else (
        python "%PYTHON_SCRIPT%" --action pause --vpn-name "%VPN_NAME%"
    )
    
    if !errorlevel!==0 (
        echo [INFO] VPN successfully paused!
    ) else (
        echo [ERROR] Failed to pause VPN
        pause
        exit /b 1
    )
    
) else if "%CURRENT_STATUS%"=="disabled" (
    echo [INFO] VPN is currently disabled. Resuming...
    if "%VPN_NAME%"=="" (
        python "%PYTHON_SCRIPT%" --action resume
    ) else (
        python "%PYTHON_SCRIPT%" --action resume --vpn-name "%VPN_NAME%"
    )
    
    if !errorlevel!==0 (
        echo [INFO] VPN successfully resumed!
    ) else (
        echo [ERROR] Failed to resume VPN
        pause
        exit /b 1
    )
    
) else (
    echo [ERROR] Unknown VPN status: %CURRENT_STATUS%
    pause
    exit /b 1
)

echo [INFO] VPN toggle operation completed successfully!
echo.
echo Press any key to exit...
pause >nul 