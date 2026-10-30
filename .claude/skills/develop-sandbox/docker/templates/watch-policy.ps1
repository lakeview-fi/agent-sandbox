<#
.SYNOPSIS
Watch this repo's Docker Sandbox network policy log and append allowed and blocked requests to a file.

.DESCRIPTION
`sbx policy log` keeps one aggregate entry per host and decision (count, first and last seen), not
one entry per request, and has no follow mode. This script polls it (`--json`) and writes a JSON
line whenever an entry is new or its count has grown: decision (allowed or blocked), host,
new_requests since the last line, total, rule and reason. Lines written on startup for requests made
before the watcher ran carry "baseline": true. Paths and methods within a host are not in the sbx
log. Filesystem denials are not logged by sbx (v0.50.1).

The log file is outside the repo on purpose: in direct mode the agent can write the repo.
start.ps1 starts this script in the background (unless -NoWatch). It exits when the sandbox is
removed. One watcher per sandbox: a second one exits at once.
Verified on Windows only. macOS and Linux (pwsh) are TODO: the log folder fallback and the named
mutex are untested there (see PLATFORM-NOTES.md in the develop-sandbox skill).

.EXAMPLE
.\sandbox\watch-policy.ps1                    # foreground, all decisions
.\sandbox\watch-policy.ps1 -BlockedOnly       # only blocked requests
Get-Content -Wait "$env:LOCALAPPDATA\sbx-policy-logs\<name>.jsonl"   # follow the file
#>
param(
    [int]$IntervalSeconds = 5,
    [switch]$BlockedOnly,
    # Windows: %LOCALAPPDATA%. Elsewhere (untested): ~/.local/state.
    [string]$LogDir = (Join-Path ($env:LOCALAPPDATA ?? (Join-Path $HOME '.local/state')) 'sbx-policy-logs')
)
$ErrorActionPreference = 'Stop'
$Repo = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$Name = (Select-String -Path (Join-Path $Repo 'sbxenv.yaml') -Pattern '^name:\s*(\S+)').Matches[0].Groups[1].Value
New-Item -ItemType Directory -Force $LogDir | Out-Null
$LogFile = Join-Path $LogDir "$Name.jsonl"

# Single instance per sandbox: a named mutex is released automatically when this process ends.
$mutex = [System.Threading.Mutex]::new($false, "Local\sbx-policy-watch-$Name")
if (-not $mutex.WaitOne(0)) { Write-Host "A watcher for $Name is already running."; return }

function Test-Sandbox {
    $names = sbx ls 2>$null | Select-Object -Skip 1 | ForEach-Object { ($_ -split '\s+')[0] }
    return $names -contains $Name
}

function Get-PolicyEntries {
    $raw = sbx policy log $Name --json 2>$null
    if ($LASTEXITCODE -ne 0 -or -not $raw) { return @() }
    $log = ($raw -join "`n") | ConvertFrom-Json
    foreach ($decision in 'allowed', 'blocked') {
        if ($BlockedOnly -and $decision -eq 'allowed') { continue }
        foreach ($e in @($log.$decision)) {
            if ($e) { $e | Add-Member -NotePropertyName decision -NotePropertyValue $decision -PassThru }
        }
    }
}

$seen = @{}   # "<decision>|<host>|<proxy_type>|<rule>" -> last count written
$baseline = $true
Write-Host "Watching $Name policy log every $IntervalSeconds s -> $LogFile"
try {
    while (Test-Sandbox) {
        foreach ($e in Get-PolicyEntries) {
            $key = "$($e.decision)|$($e.host)|$($e.proxy_type)|$($e.rule)"
            $previous = if ($seen.ContainsKey($key)) { $seen[$key] } else { 0 }
            if ($e.count -lt $previous) { $previous = 0 }   # counter reset (sandbox recreated)
            if ($e.count -eq $previous) { continue }
            $seen[$key] = $e.count
            [ordered]@{
                time         = (Get-Date).ToString('o')
                sandbox      = $Name
                decision     = $e.decision
                host         = $e.host
                new_requests = $e.count - $previous
                total        = $e.count
                last_seen    = $e.last_seen
                proxy_type   = $e.proxy_type
                rule         = $e.rule
                reason       = $e.reason
                baseline     = $baseline
            } | ConvertTo-Json -Compress | Add-Content -Encoding utf8 $LogFile
        }
        $baseline = $false
        Start-Sleep -Seconds $IntervalSeconds
    }
    Write-Host "Sandbox $Name is gone; watcher stops."
} finally {
    $mutex.ReleaseMutex()
}
