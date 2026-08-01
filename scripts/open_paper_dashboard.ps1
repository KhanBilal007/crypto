$ErrorActionPreference = "Stop"

$ProjectRoot = "E:\krypto"
$Python = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
$DashboardPort = 8785
$DashboardUrl = "http://127.0.0.1:$DashboardPort/"
$StatusUrl = "${DashboardUrl}api/status"
$env:PYTHONPATH = Join-Path $ProjectRoot "src"
$env:ABTP_MARKET_DATA_SOURCE = "binance"
$env:ABTP_PAPER_STATE_PATH = Join-Path $ProjectRoot "docs\paper_dashboard_state.json"
$env:ABTP_PAPER_DB_PATH = Join-Path $ProjectRoot "docs\paper_dashboard.sqlite"

function Stop-StaleDashboard {
    $connections = Get-NetTCPConnection `
        -LocalAddress "127.0.0.1" `
        -LocalPort $DashboardPort `
        -State Listen `
        -ErrorAction SilentlyContinue
    foreach ($connection in $connections) {
        Stop-Process -Id $connection.OwningProcess -Force -ErrorAction SilentlyContinue
    }
    if ($connections) {
        Start-Sleep -Seconds 1
    }
}

try {
    $page = Invoke-WebRequest -Uri $DashboardUrl -UseBasicParsing -TimeoutSec 2
    if ($page.Content -notmatch 'setInterval\(load, 15000\)') {
        throw "Dashboard on $DashboardPort is not the auto-refresh paper UI."
    }
}
catch {
    Stop-StaleDashboard
    Start-Process `
        -FilePath $Python `
        -ArgumentList "-m", "abtp.dashboard.paper_server", "--host", "127.0.0.1", "--port", "$DashboardPort" `
        -WorkingDirectory $ProjectRoot `
        -WindowStyle Hidden

    Start-Sleep -Seconds 2
}

Start-Process $DashboardUrl
