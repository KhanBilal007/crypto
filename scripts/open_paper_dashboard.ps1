$ErrorActionPreference = "Stop"

$ProjectRoot = "E:\krypto"
$Python = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
$DashboardUrl = "http://127.0.0.1:8785/"
$StatusUrl = "${DashboardUrl}api/status"
$env:PYTHONPATH = Join-Path $ProjectRoot "src"
$env:ABTP_MARKET_DATA_SOURCE = "binance"
$env:ABTP_PAPER_STATE_PATH = Join-Path $ProjectRoot "docs\paper_dashboard_state.json"
$env:ABTP_PAPER_DB_PATH = Join-Path $ProjectRoot "docs\paper_dashboard.sqlite"

try {
    $page = Invoke-WebRequest -Uri $DashboardUrl -UseBasicParsing -TimeoutSec 2
    if ($page.Content -notmatch 'ticket_filters') {
        throw "Dashboard on 8785 is not the updated Binance-style paper UI."
    }
}
catch {
    Start-Process `
        -FilePath $Python `
        -ArgumentList "-m", "abtp.dashboard.paper_server", "--host", "127.0.0.1", "--port", "8785" `
        -WorkingDirectory $ProjectRoot `
        -WindowStyle Hidden

    Start-Sleep -Seconds 2
}

Start-Process $DashboardUrl
