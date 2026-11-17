<#
.SYNOPSIS
    Khởi chạy toàn bộ hệ thống Smart Shopping Cart cục bộ trên Windows PowerShell.
.DESCRIPTION
    Khởi động 3 tiến trình theo thứ tự:
      1. MQTT Broker thử nghiệm (cổng 1883) hoặc dùng Mosquitto ngoài nếu cấu hình MQTT_HOST khác localhost
      2. Backend FastAPI + Realtime WebSocket (/ws cổng 8000) + Web UI
      3. Python Simulator 3 xe (cổng điều khiển 8090)
    Tự động dọn dẹp các tiến trình con khi nhấn Ctrl+C.
#>

$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$RootDir = Split-Path -Parent $ScriptDir
Set-Location $RootDir
$env:PYTHONPATH = $RootDir

Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host "   SMART SHOPPING CART - KHỞI CHẠY HỆ THỐNG CỤC BỘ      " -ForegroundColor Cyan
Write-Host "==========================================================" -ForegroundColor Cyan

# 0. Nạp biến môi trường từ .env (nếu có)
$envFile = Join-Path $RootDir ".env"
if (Test-Path $envFile) {
    Write-Host "[i] Nạp cấu hình từ .env..." -ForegroundColor Gray
    Get-Content $envFile | ForEach-Object {
        $line = $_.Trim()
        if ($line -and -not $line.StartsWith("#") -and $line.Contains("=")) {
            $kv = $line.Split("=", 2)
            $k = $kv[0].Trim()
            $v = ($kv[1] -split "\s+#")[0].Trim()
            if (-not [Environment]::GetEnvironmentVariable($k, "Process")) {
                [Environment]::SetEnvironmentVariable($k, $v, "Process")
            }
        }
    }
}

# Mặc định chạy SQLite + WS gom cổng 8000 cho môi trường Windows cục bộ nếu người dùng chưa thiết lập
if (-not $env:DB_BACKEND) { $env:DB_BACKEND = "sqlite" }
if (-not $env:WS_PORT) { $env:WS_PORT = "8000" }

# 1. Kiểm tra Python
try {
    $pyVer = & python -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')"
    Write-Host "[OK] Python version: $pyVer | DB_BACKEND=$($env:DB_BACKEND)" -ForegroundColor Green
    $parts = $pyVer.Split('.')
    if ([int]$parts[0] -lt 3 -or ([int]$parts[0] -eq 3 -and [int]$parts[1] -lt 11)) {
        Write-Warning "Yêu cầu Python >= 3.11 để đảm bảo tương thích."
    }
} catch {
    Write-Error "Không tìm thấy Python trong PATH. Vui lòng cài đặt Python >= 3.11."
    exit 1
}

# 2. Kiểm tra gói cần thiết
$pkgCheck = & python -c "
pkgs = ['fastapi', 'uvicorn', 'pydantic']
if '$($env:DB_BACKEND)'.lower() == 'postgres':
    pkgs.append('psycopg')
for pkg in pkgs:
    try:
        __import__(pkg)
    except ImportError:
        print(pkg)
"
if ($pkgCheck) {
    Write-Warning "Thiếu package: $pkgCheck. Đang cài đặt từ requirements.txt..."
    & python -m pip install -r requirements.txt
}

# 3. Kiểm tra và dọn dẹp cổng trùng lặp (tránh tạo tiến trình trùng)
$ports = @(1883, 8000, 8081, 8090)
foreach ($p in $ports) {
    $conn = Get-NetTCPConnection -LocalPort $p -State Listen -ErrorAction SilentlyContinue
    if ($conn) {
        $procIds = $conn.OwningProcess | Select-Object -Unique
        Write-Warning "Cổng $p đang có tiến trình chiếm dụng (PID: $procIds)."
        Write-Host "Đang dừng tiến trình cũ trên cổng $p..." -ForegroundColor Yellow
        foreach ($procId in $procIds) {
            Stop-Process -Id $procId -Force -ErrorAction SilentlyContinue
        }
        Start-Sleep -Milliseconds 500
    }
}

# 4. Mật khẩu quản trị
if (-not $env:ADMIN_PASSWORD) {
    $env:ADMIN_PASSWORD = & python -c "import secrets; print(secrets.token_urlsafe(9))"
}
$adminUser = if ($env:ADMIN_USERNAME) { $env:ADMIN_USERNAME } else { "admin" }

$pids = @()

try {
    Write-Host "[1/3] Khởi động MQTT Broker (cổng 1883)..." -ForegroundColor Yellow
    $brokerProc = Start-Process python -ArgumentList "-m tools.dev_broker --host 127.0.0.1 --port 1883" -PassThru -NoNewWindow
    $pids += $brokerProc.Id
    Start-Sleep -Seconds 1
    if ($brokerProc.HasExited) { throw "MQTT Broker khởi động thất bại (ExitCode: $($brokerProc.ExitCode))." }

    Write-Host "[2/3] Khởi động Backend FastAPI (cổng 8000)..." -ForegroundColor Yellow
    $backendProc = Start-Process python -ArgumentList "-m backend.main" -PassThru -NoNewWindow
    $pids += $backendProc.Id

    # Đợi Backend /api/health sẵn sàng tối đa 15 giây
    $ready = $false
    for ($i = 0; $i -lt 30; $i++) {
        if ($backendProc.HasExited) { throw "Backend khởi động thất bại (ExitCode: $($backendProc.ExitCode))." }
        try {
            $resp = Invoke-WebRequest -Uri "http://127.0.0.1:8000/api/health" -UseBasicParsing -TimeoutSec 2
            if ($resp.StatusCode -eq 200) { $ready = $true; break }
        } catch {}
        Start-Sleep -Milliseconds 500
    }
    if (-not $ready) { throw "Backend không phản hồi /api/health sau 15 giây." }

    Write-Host "[3/4] Khởi động Python Simulator 3 xe (cổng 8090)..." -ForegroundColor Yellow
    $simProc = Start-Process python -ArgumentList "-m simulator.main --no-cli" -PassThru -NoNewWindow
    $pids += $simProc.Id
    Start-Sleep -Seconds 1
    if ($simProc.HasExited) { throw "Simulator khởi động thất bại (ExitCode: $($simProc.ExitCode))." }

    Write-Host "[4/4] Khởi động Cầu nối Wokwi Bridge (cổng 4000 -> MQTT xe CART_001)..." -ForegroundColor Yellow
    $bridgeProc = Start-Process python -ArgumentList "-m tools.wokwi_bridge --cart-id CART_001 --firmware-cart-id CART_001" -PassThru -NoNewWindow
    $pids += $bridgeProc.Id

    Write-Host "`n----------------------------------------------------------" -ForegroundColor Green
    Write-Host "HỆ THỐNG ĐÃ SẴN SÀNG:" -ForegroundColor Green
    Write-Host "  • Giao diện Web Khách Hàng: http://localhost:8000/customer" -ForegroundColor White
    Write-Host "  • Giao diện Quản Trị:       http://localhost:8000/admin" -ForegroundColor White
    Write-Host "  • Bản đồ Siêu thị 2D:       http://localhost:8000/simulation" -ForegroundColor White
    Write-Host "  • Simulator Phần Cứng Web:  http://localhost:8000/simulator" -ForegroundColor White
    Write-Host "  • Wokwi ESP32 Bridge:       Cổng 4000 sẵn sàng nối xe CART_001" -ForegroundColor Yellow
    Write-Host "  • Swagger API Docs:         http://localhost:8000/docs" -ForegroundColor White
    Write-Host "  • ReDoc API Docs:           http://localhost:8000/redoc" -ForegroundColor White
    Write-Host "  • WebSocket Realtime:       ws://localhost:8000/ws" -ForegroundColor White
    Write-Host "  • Tài khoản Admin:          $adminUser / $env:ADMIN_PASSWORD" -ForegroundColor Cyan
    Write-Host "  • Khách hàng:               Không cần đăng nhập" -ForegroundColor Gray
    Write-Host "----------------------------------------------------------" -ForegroundColor Green
    Write-Host "Nhấn Ctrl+C (hoặc đóng cửa sổ) để dừng toàn bộ hệ thống...`n" -ForegroundColor Gray

    while ($true) {
        foreach ($proc in @($brokerProc, $backendProc, $simProc, $bridgeProc)) {
            if ($proc.HasExited) {
                Write-Warning "Tiến trình $($proc.Id) đã dừng đột ngột (ExitCode: $($proc.ExitCode))."
                throw "Tiến trình con bị dừng."
            }
        }
        Start-Sleep -Seconds 2
    }
}
finally {
    Write-Host "`nĐang dừng các dịch vụ..." -ForegroundColor Yellow
    foreach ($id in $pids) {
        try {
            Stop-Process -Id $id -Force -ErrorAction SilentlyContinue
        } catch {}
    }
    Write-Host "Đã dừng toàn bộ dịch vụ." -ForegroundColor Green
}
