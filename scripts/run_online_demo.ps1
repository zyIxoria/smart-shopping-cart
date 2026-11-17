# Chạy CHỈ Backend (+ giao diện) nối vào MQTT broker CÔNG CỘNG để firmware trong Wokwi liên kết được (Windows PowerShell).
# Cấu hình (broker, gốc topic, mã xe) đọc từ firmware\include\wokwi_online.h nên luôn khớp với firmware.
# Chạy từ thư mục gốc dự án:   powershell -ExecutionPolicy Bypass -File scripts\run_online_demo.ps1
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$hdr = Get-Content (Join-Path $root "firmware\include\wokwi_online.h") -Raw
function Get-Def([string]$name) {
    if ($hdr -match ('(?m)^#define\s+' + $name + '\s+"([^"]*)"')) { return $Matches[1] }
    throw "Không đọc được $name trong wokwi_online.h"
}
$env:MQTT_HOST = Get-Def "MQTT_HOST"
$env:MQTT_PORT = "1883"
$env:MQTT_TOPIC_ROOT = Get-Def "MQTT_TOPIC_ROOT"
$env:MQTT_CLIENT_ID = "backend-" + $env:MQTT_TOPIC_ROOT
$cart = Get-Def "CART_ID"
$env:PYTHONPATH = $root
Set-Location $root
Write-Host "Broker: $($env:MQTT_HOST):1883  gốc topic: $($env:MQTT_TOPIC_ROOT)  mã xe: $cart"

# Đăng nhập quản trị: không đặt ADMIN_PASSWORD thì sinh ngẫu nhiên cho lần chạy này (khách hàng không cần đăng nhập)
if (-not $env:ADMIN_PASSWORD) {
    $env:ADMIN_PASSWORD = -join ((48..57) + (97..122) | Get-Random -Count 14 | ForEach-Object { [char]$_ })
}
$adminUser = if ($env:ADMIN_USERNAME) { $env:ADMIN_USERNAME } else { "admin" }
Write-Host "Quản trị: đăng nhập $adminUser / $($env:ADMIN_PASSWORD)"

# Đăng ký xe sau 5 giây (bỏ qua nếu đã có) – cần token quản trị
Start-Job -ArgumentList $cart, $adminUser, $env:ADMIN_PASSWORD -ScriptBlock {
    param($cartId, $user, $pw)
    Start-Sleep -Seconds 5
    try {
        $login = Invoke-RestMethod -Method Post -Uri "http://127.0.0.1:8000/api/auth/login" -ContentType "application/json" `
            -Body (@{ username = $user; password = $pw } | ConvertTo-Json)
        Invoke-RestMethod -Method Post -Uri "http://127.0.0.1:8000/api/carts" -ContentType "application/json" `
            -Headers @{ Authorization = "Bearer $($login.token)" } `
            -Body (@{ cart_id = $cartId; name = "Xe Wokwi" } | ConvertTo-Json) | Out-Null
        "Đã đăng ký xe $cartId"
    } catch { "Xe $cartId : đã đăng ký từ trước hoặc lỗi ($($_.Exception.Message))" }
} | Out-Null

python -m backend.main
