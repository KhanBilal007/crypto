$ErrorActionPreference = "Stop"

$ProjectRoot = "E:\krypto"
$Python = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
$DashboardPort = 8765
$DashboardUrl = "http://127.0.0.1:$DashboardPort/"
$StatusUrl = "${DashboardUrl}api/status"
$env:PYTHONPATH = Join-Path $ProjectRoot "src"
$env:ABTP_MARKET_DATA_SOURCE = "binance"
$env:ABTP_PAPER_INITIAL_CASH = "1000"
$env:ABTP_PAPER_STATE_PATH = Join-Path $ProjectRoot "docs\paper_dashboard_state.json"
$env:ABTP_PAPER_DB_PATH = Join-Path $ProjectRoot "docs\paper_dashboard.sqlite"

function Stop-StaleDashboard {
    $listenerProcessIds = Get-DashboardListenerProcessIds
    foreach ($processId in $listenerProcessIds) {
        if (-not (Test-OwnedDashboardProcess $processId)) {
            throw "Port $DashboardPort is used by process $processId, but it does not look like this dashboard. Close it manually or choose another port."
        }
        Stop-Process -Id $processId -Force -ErrorAction Stop
    }
    if ($listenerProcessIds) {
        Start-Sleep -Seconds 1
    }
}

function Test-OwnedDashboardProcess {
    param([string]$ProcessId)

    $process = Get-CimInstance Win32_Process `
        -Filter "ProcessId = $ProcessId" `
        -ErrorAction SilentlyContinue
    if ($null -eq $process) {
        return $false
    }

    $commandLine = [string]$process.CommandLine
    $executablePath = [string]$process.ExecutablePath
    $pythonPattern = [regex]::Escape($Python)
    $portPattern = "--port\s+$DashboardPort(?:\s|$)"

    return (
        ($executablePath -match 'python(?:\.exe)?$' -or $commandLine -match $pythonPattern) -and
        $commandLine -match 'abtp\.dashboard\.paper_server' -and
        $commandLine -match $portPattern
    )
}

function Get-DashboardListenerProcessIds {
    $pattern = "127\.0\.0\.1:$DashboardPort\s+0\.0\.0\.0:0\s+LISTENING"
    return @(
        netstat -ano |
            Select-String $pattern |
            ForEach-Object { ($_ -split "\s+")[-1] } |
            Sort-Object -Unique
    )
}

Stop-StaleDashboard
Start-Process `
    -FilePath $Python `
    -ArgumentList "-m", "abtp.dashboard.paper_server", "--host", "127.0.0.1", "--port", "$DashboardPort" `
    -WorkingDirectory $ProjectRoot `
    -WindowStyle Hidden

Start-Sleep -Seconds 2

$page = Invoke-WebRequest -Uri $DashboardUrl -UseBasicParsing -TimeoutSec 5
if (
    $page.Content -notmatch 'setInterval\(load, 15000\)' -or
    $page.Content -notmatch 'data-dashboard-build="portfolio-tiles-v2"' -or
    $page.Content -notmatch 'class="topbar"' -or
    $page.Content -notmatch 'notification_bell' -or
    $page.Content -notmatch 'portfolio-grid' -or
    $page.Content -notmatch '>AI Decision Checks</h2>' -or
    $page.Content -notmatch '>Paper Trading</option>' -or
    $page.Content -notmatch '>Live Trading</option>' -or
    $page.Content -notmatch '>Beginner</strong>' -or
    $page.Content -notmatch '>Advanced</strong>' -or
    $page.Content -notmatch '>Strategy Mode</strong>'
) {
    throw "Dashboard on $DashboardPort is not the polished adaptive paper UI."
}
$status = Invoke-WebRequest -Uri $StatusUrl -UseBasicParsing -TimeoutSec 5 |
    Select-Object -ExpandProperty Content |
    ConvertFrom-Json
if ($status.market.source -eq "demo" -and $status.market.data_freshness -eq "healthy") {
    throw "Dashboard on $DashboardPort was started without Binance market mode."
}

Start-Process $DashboardUrl
