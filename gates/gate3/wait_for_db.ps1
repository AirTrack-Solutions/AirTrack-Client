# Wait for MariaDB to accept TCP connections on port 3307.
# No Python required — runs on any modern Windows machine.
$maxAttempts = 30
for ($i = 1; $i -le $maxAttempts; $i++) {
    try {
        $tcp = New-Object System.Net.Sockets.TcpClient('127.0.0.1', 3307)
        $tcp.Close()
        Write-Host "MariaDB ready."
        exit 0
    } catch {
        Write-Host "Waiting for MariaDB... ($i/$maxAttempts)"
        Start-Sleep -Seconds 2
    }
}
Write-Host "FAIL: MariaDB did not become ready in time."
exit 1
