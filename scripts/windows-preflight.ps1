# Read-only probe for the Windows Codex desktop window. Prints no project or chat content.
$ErrorActionPreference = 'Stop'
$port = 9333
$endpoint = "http://127.0.0.1:$port/json/list"

try {
    $targets = @(Invoke-RestMethod -Uri $endpoint -TimeoutSec 3)
} catch {
    Write-Output 'RESULT: NO_DEBUG_PORT'
    Write-Output 'Codex is not reachable on the local debugging port. Exit Codex normally, then start it with --remote-debugging-address=127.0.0.1 --remote-debugging-port=9333 and run this file again.'
    exit 2
}

$target = $targets | Where-Object { $_.type -eq 'page' -and $_.url -like 'app://-/index.html*' } | Select-Object -First 1
if (-not $target) {
    Write-Output 'RESULT: NO_CODEX_WINDOW'
    Write-Output 'The port is open, but it does not expose a Codex desktop window.'
    exit 3
}

$uri = [Uri]$target.webSocketDebuggerUrl
if ($uri.Scheme -ne 'ws' -or $uri.Host -notin @('127.0.0.1', 'localhost') -or $uri.Port -ne $port) {
    Write-Output 'RESULT: INVALID_LOCAL_TARGET'
    exit 4
}

$socket = New-Object System.Net.WebSockets.ClientWebSocket
$timeout = New-Object System.Threading.CancellationTokenSource(5000)
try {
    $socket.ConnectAsync($uri, $timeout.Token).GetAwaiter().GetResult()
    $expression = '(() => ({ shell: !!document.querySelector("nav[data-app-navigation-rail]"), shared: !!document.querySelector("link[rel=modulepreload][href*=app-shared-]"), initial: !!document.querySelector("link[rel=modulepreload][href*=app-initial-]") }))()'
    $message = @{ id = 1; method = 'Runtime.evaluate'; params = @{ expression = $expression; returnByValue = $true } } | ConvertTo-Json -Compress -Depth 5
    $bytes = [Text.Encoding]::UTF8.GetBytes($message)
    $socket.SendAsync((New-Object 'System.ArraySegment[byte]' -ArgumentList @(,$bytes)), [System.Net.WebSockets.WebSocketMessageType]::Text, $true, $timeout.Token).GetAwaiter().GetResult()

    $reply = $null
    while ($null -eq $reply) {
        $buffer = New-Object byte[] 8192
        $stream = New-Object IO.MemoryStream
        do {
            $segment = New-Object 'System.ArraySegment[byte]' -ArgumentList @(,$buffer)
            $part = $socket.ReceiveAsync($segment, $timeout.Token).GetAwaiter().GetResult()
            if ($part.MessageType -eq [System.Net.WebSockets.WebSocketMessageType]::Close) { throw 'Connection closed' }
            $stream.Write($buffer, 0, $part.Count)
        } until ($part.EndOfMessage)
        $parsed = [Text.Encoding]::UTF8.GetString($stream.ToArray()) | ConvertFrom-Json
        if ($parsed.id -eq 1) { $reply = $parsed }
    }
    if ($reply.error -or $reply.result.exceptionDetails) { throw 'Read-only window inspection failed' }
    $result = $reply.result.result.value
    if ($result.shell -and $result.shared -and $result.initial) {
        Write-Output 'RESULT: CONNECTABLE'
        Write-Output 'Codex window, navigation shell, and required native UI bundles are reachable.'
    } else {
        Write-Output 'RESULT: UI_ADAPTATION_NEEDED'
        Write-Output ("shell={0} shared={1} initial={2}" -f [bool]$result.shell, [bool]$result.shared, [bool]$result.initial)
    }
} catch {
    Write-Output 'RESULT: INSPECTION_FAILED'
    Write-Output 'The Codex window was found, but its read-only UI check could not finish.'
    exit 5
} finally {
    $timeout.Dispose()
    $socket.Dispose()
}
