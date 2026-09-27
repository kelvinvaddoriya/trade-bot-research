# Sets this laptop up to run TradeBot 24/7 in demo (docs/09 §6). Run ONCE in an elevated PowerShell:
#   powershell -ExecutionPolicy Bypass -File D:\TradeBot\ops\install-tasks.ps1
# It changes system settings (power plan, time sync, scheduled tasks), which is why it's yours to run.
# Undo: Unregister-ScheduledTask "TradeBot*" ; powercfg /restoredefaultschemes
$ErrorActionPreference = "Stop"
$root = Split-Path $PSScriptRoot -Parent
$py = Join-Path $root ".venv\Scripts\python.exe"
if (-not (Test-Path $py)) { throw "missing ${py}: run 'uv sync' in $root first" }
$backup = "C:\TradeBotBackup"

# --- power: never sleep or hibernate on AC; closing the lid does nothing on AC ---
powercfg /change standby-timeout-ac 0
powercfg /change hibernate-timeout-ac 0
powercfg /hibernate off
powercfg /setacvalueindex SCHEME_CURRENT SUB_BUTTONS LIDACTION 0
powercfg /setactive SCHEME_CURRENT

# --- time: sync hourly instead of weekly (the engine refuses new orders when the clock is off by > 2 s) ---
Set-Service w32time -StartupType Automatic
Start-Service w32time -ErrorAction SilentlyContinue
reg add "HKLM\SYSTEM\CurrentControlSet\Services\W32Time\TimeProviders\NtpClient" /v SpecialPollInterval /t REG_DWORD /d 3600 /f | Out-Null
w32tm /config /update /manualpeerlist:"time.windows.com,0x9" /syncfromflags:manual | Out-Null
Restart-Service w32time
w32tm /resync | Out-Null

# --- scheduled tasks: run whether or not anyone is logged on (S4U: no stored password) ---
$me = New-ScheduledTaskPrincipal -UserId "$env:USERDOMAIN\$env:USERNAME" -LogonType S4U -RunLevel Limited
$forever = New-ScheduledTaskSettingsSet -ExecutionTimeLimit ([TimeSpan]::Zero) -StartWhenAvailable `
    -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -MultipleInstances IgnoreNew `
    -RestartCount 999 -RestartInterval (New-TimeSpan -Minutes 1)

# Engine: starts at boot, restarted a minute after a crash. `python -m tradebot stop` exits cleanly (no restart).
$engine = New-ScheduledTaskAction -Execute "cmd.exe" -WorkingDirectory $root `
    -Argument "/c `"$py`" -m tradebot run >> data\engine.log 2>&1"
Register-ScheduledTask -TaskName "TradeBot engine" -Action $engine -Trigger (New-ScheduledTaskTrigger -AtStartup) `
    -Principal $me -Settings $forever -Force | Out-Null

# Watchdog: every minute. It only touches the broker when the engine's heartbeat is stale.
$wd = New-ScheduledTaskAction -Execute $py -Argument "-m tradebot watchdog" -WorkingDirectory $root
$every = New-ScheduledTaskTrigger -Once -At (Get-Date).AddMinutes(1) -RepetitionInterval (New-TimeSpan -Minutes 1)
Register-ScheduledTask -TaskName "TradeBot watchdog" -Action $wd -Trigger $every -Principal $me `
    -Settings (New-ScheduledTaskSettingsSet -ExecutionTimeLimit (New-TimeSpan -Minutes 5) -StartWhenAvailable `
        -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -MultipleInstances IgnoreNew) -Force | Out-Null

# Nightly backup of the demo journal/ledger to C: (SQLite's backup API: consistent while the engine writes).
New-Item -ItemType Directory -Force $backup | Out-Null
$bk = New-ScheduledTaskAction -Execute $py -WorkingDirectory $root -Argument ("-c `"import sqlite3; " +
    "sqlite3.connect('data/demo.db').backup(sqlite3.connect(r'$backup\demo.db'))`"")
Register-ScheduledTask -TaskName "TradeBot backup" -Action $bk -Trigger (New-ScheduledTaskTrigger -Daily -At 3am) `
    -Principal $me -Settings (New-ScheduledTaskSettingsSet -StartWhenAvailable -AllowStartIfOnBatteries) -Force | Out-Null

Start-ScheduledTask -TaskName "TradeBot engine"
Write-Host "Done. Engine started; watchdog every minute; backup nightly to $backup."
Write-Host "Still manual (docs/09 §6): Windows Update active hours 06:00-00:00; battery charge limit if your laptop has one."
Write-Host "Check with: cd $root; uv run python -m tradebot status"
