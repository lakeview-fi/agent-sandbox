<#
.SYNOPSIS
Create (if needed) and start this repo's Docker Sandbox with Claude Code.

.DESCRIPTION
Run from PowerShell on Windows (sbx is a Windows binary). Verified on Windows only; `pwsh` on
macOS or Linux is untested (TODO, see PLATFORM-NOTES.md in the develop-sandbox skill).
The sandbox is defined by two env files, merged by `sbx env`: the global ~/.sbxenv.yaml (agent,
shared mounts, sizing) and this repo's sbxenv.yaml (name, workspace, venv path). On the first run:
  1. creates the sandbox with `sbx env create` from the repo root;
  2. applies sandbox/allowed-hosts.txt as per-sandbox network rules (env files have no network field);
  3. runs sandbox/setup-in-sandbox.sh inside (tools, agents, git, deps).
On every start it also launches sandbox/watch-policy.ps1 in the background (unless -NoWatch), which
logs allowed and blocked network requests to a file outside the repo.
Then it attaches to Claude Code (with -Agent: that custom agent).

Default mode: direct mount. The agent edits and commits in this working tree; nothing to fetch.
-Clone: the agent works on a private clone; bring its commits back with sandbox/pull.ps1.
Changing mode needs -Recreate. Stop with sandbox/stop.ps1.

.EXAMPLE
.\sandbox\start.ps1                                  # interactive session
.\sandbox\start.ps1 -Prompt "Do X, then report."     # non-interactive run
.\sandbox\start.ps1 -Clone -Recreate                 # switch to the safer clone mode
.\sandbox\start.ps1 -Resetup -SetupOnly              # rerun the in-sandbox setup only
#>
param(
    [string]$Agent = '',   # ADAPT: default custom agent for `claude --agent` ('' = plain Claude Code)
    [string]$Prompt,
    [switch]$Clone,        # private clone instead of the direct mount (safer; see README.md)
    [switch]$Recreate,     # delete the sandbox first (clone mode: pull first, see stop.ps1)
    [switch]$Resetup,      # rerun setup-in-sandbox.sh in an existing sandbox
    [switch]$SetupOnly,    # create and set up, but do not start the agent
    [switch]$NoWatch       # do not start the background policy-log watcher (watch-policy.ps1)
)
$ErrorActionPreference = 'Stop'

$Repo = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$EnvFile = Join-Path $Repo 'sbxenv.yaml'
$Name = (Select-String -Path $EnvFile -Pattern '^name:\s*(\S+)').Matches[0].Groups[1].Value
$GlobalEnvFile = Join-Path $HOME '.sbxenv.yaml'
if (-not (Test-Path $GlobalEnvFile)) {
    # The repo file holds only repo-specific values; the agent and shared mounts are in the global file.
    throw "Missing $GlobalEnvFile. Install it from the develop-sandbox skill's docker/templates/global-sbxenv.yaml."
}

function Invoke-Native([scriptblock]$Command) {
    & $Command | Out-Host
    if ($LASTEXITCODE -ne 0) { throw "Command failed (exit $LASTEXITCODE): $Command" }
}

function Test-Sandbox {
    $names = sbx ls 2>$null | Select-Object -Skip 1 | ForEach-Object { ($_ -split '\s+')[0] }
    return $names -contains $Name
}

function Test-CloneMode {
    # `sbx inspect` shows "Clone source: -" for a direct mount. (The git remote sandbox-<name> is not
    # a reliable signal: it can disappear while the sandbox still exists.)
    $line = sbx inspect $Name 2>$null | Select-String -Pattern '^\s*Clone source:\s*(\S+)'
    return [bool]$line -and $line.Matches[0].Groups[1].Value -ne '-'
}

function ConvertTo-SandboxPath([string]$HostPath) {
    $full = (Resolve-Path $HostPath).Path
    '/' + $full.Substring(0, 1).ToLower() + ($full.Substring(2) -replace '\\', '/')
}

if ($Recreate -and (Test-Sandbox)) {
    if (Test-CloneMode) {
        Write-Host "== clone mode: pulling the agent's commits before removal"
        & (Join-Path $PSScriptRoot 'pull.ps1')
    }
    Write-Host "== removing sandbox $Name"
    Invoke-Native { sbx rm --force $Name }
}

if (Test-Sandbox) {
    if ($Clone -ne (Test-CloneMode)) {
        $current = if (Test-CloneMode) { 'clone' } else { 'direct' }
        throw "Sandbox $Name exists in $current mode. Add -Recreate to change mode."
    }
} else {
    $mode = if ($Clone) { 'clone' } else { 'direct mount' }
    Write-Host "== creating sandbox $Name ($mode) from ~/.sbxenv.yaml + sbxenv.yaml"
    # No PATH argument: that is what makes sbx merge ~/.sbxenv.yaml with ./sbxenv.yaml.
    # @(...) around the if: a one-element array returned from `if` unwraps to a string, and splatting
    # a string passes its characters (- - c l o n e).
    $cloneArg = @(if ($Clone) { '--clone' })
    Push-Location $Repo
    try { Invoke-Native { sbx env create --force @cloneArg } } finally { Pop-Location }

    Write-Host "== network allow list (sandbox/allowed-hosts.txt)"
    $lines = Get-Content (Join-Path $PSScriptRoot 'allowed-hosts.txt') |
        ForEach-Object { $_.Trim() } | Where-Object { $_ -and -not $_.StartsWith('#') }
    # A bare host is a TCP rule; `<host> <METHODS> <path-glob>` is an HTTP rule for that path only.
    $hosts = $lines | Where-Object { $_ -notmatch '\s' }
    Invoke-Native { sbx policy allow network --sandbox $Name ($hosts -join ',') }
    foreach ($rule in ($lines | Where-Object { $_ -match '\s' })) {
        $hostName, $methods, $path = $rule -split '\s+'
        Invoke-Native { sbx policy allow network --sandbox $Name $hostName --method $methods --path $path }
    }
    $Resetup = $true
}

if (-not $NoWatch) {
    # Background watcher: appends allowed and blocked network requests to a file outside the repo.
    # It exits by itself when the sandbox is removed; a second start finds it running and exits.
    $watcher = Join-Path $PSScriptRoot 'watch-policy.ps1'
    if ($IsWindows) {
        Write-Host "== policy-log watcher -> $env:LOCALAPPDATA\sbx-policy-logs\$Name.jsonl"
        Start-Process pwsh -WindowStyle Hidden -ArgumentList @('-NoLogo', '-NoProfile', '-File', $watcher)
    } else {
        # TODO (macOS, Linux): background start is untested; run the watcher in a second terminal.
        Write-Host "== policy-log watcher not started automatically on this OS; run: pwsh -File $watcher"
    }
}

if ($Resetup) {
    Write-Host "== setup inside the sandbox"
    $mode     = if (Test-CloneMode) { 'clone' } else { 'direct' }
    $gitName  = git -C $Repo config user.name
    $gitEmail = git -C $Repo config user.email
    $hooks    = git -C $Repo config core.hooksPath
    # bash needs LF. PowerShell ends piped text with CRLF, so the script ends on a comment line
    # that absorbs the stray CR.
    $setup = ((Get-Content -Raw (Join-Path $PSScriptRoot 'setup-in-sandbox.sh')) -replace "`r`n", "`n") +
        "`n# end of piped script"
    Invoke-Native {
        $setup | sbx exec -i $Name -- bash -s -- `
            (ConvertTo-SandboxPath $Repo) $mode "$gitName" "$gitEmail" "$hooks"
    }
}

if ($SetupOnly) { return }

# ADAPT: print any rule the developer must keep while the agent runs, for example a shared SQLite
# DB on a read-write mount: SQLite locks do not cross the VM boundary, so one writer side at a time.
$agentArgs = if ($Agent) { @('--agent', $Agent) } else { @() }
if ($Prompt) {
    # Run log outside the repo, so the agent cannot change it in direct mode.
    $runLog = Join-Path $env:LOCALAPPDATA "sbx-agent-logs\$Name-$(Get-Date -Format yyyyMMdd-HHmmss).log"
    New-Item -ItemType Directory -Force (Split-Path $runLog) | Out-Null
    Write-Host "== agent run log -> $runLog"
    "# prompt: $Prompt" | Set-Content -Encoding utf8 $runLog
    # As the built-in agent and the kit's ENTRYPOINT: permission prompts bypassed; the microVM is
    # the boundary.
    sbx exec $Name -- claude --dangerously-skip-permissions @agentArgs -p $Prompt 2>&1 |
        Tee-Object -FilePath $runLog -Append | Out-Host
    if ($LASTEXITCODE -ne 0) { throw "Agent run failed (exit $LASTEXITCODE); see $runLog" }
} else {
    sbx run --name $Name -- @agentArgs
}
