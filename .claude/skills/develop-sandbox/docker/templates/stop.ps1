<#
.SYNOPSIS
Stop this repo's Docker Sandbox at the end of a session; optionally remove it.

.DESCRIPTION
A stopped sandbox keeps its disk: the installed tools, the agent's ~/.claude state, and in clone
mode its commits. It survives a host restart; start.ps1 starts it again. Shutting the computer
down without this script has the same effect as stopping. The work is not lost.

Clone mode: pulls the agent's commits into a local branch first (sandbox/pull.ps1), then stops.
A failed pull aborts, so -Remove never deletes unpulled commits.
Direct mode: the agent's work is already in this working tree; this only stops.

.EXAMPLE
.\sandbox\stop.ps1            # pull (clone mode) and stop
.\sandbox\stop.ps1 -Remove    # pull (clone mode), then delete the sandbox
#>
param(
    [switch]$Remove        # delete the sandbox after stopping (next start.ps1 recreates it)
)
$ErrorActionPreference = 'Stop'
$Repo = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$Name = (Select-String -Path (Join-Path $Repo 'sbxenv.yaml') -Pattern '^name:\s*(\S+)').Matches[0].Groups[1].Value

# `sbx inspect` shows "Clone source: -" for a direct mount.
$cloneLine = sbx inspect $Name 2>$null | Select-String -Pattern '^\s*Clone source:\s*(\S+)'
if ($cloneLine -and $cloneLine.Matches[0].Groups[1].Value -ne '-') {
    Write-Host "== clone mode: pulling the agent's commits"
    # The commits are served from inside the sandbox, so pull before stopping.
    & (Join-Path $PSScriptRoot 'pull.ps1')
}

if ($Remove) {
    Write-Host "== removing sandbox $Name"
    sbx rm --force $Name
} else {
    Write-Host "== stopping sandbox $Name"
    sbx stop $Name
}
if ($LASTEXITCODE -ne 0) { throw "sbx exited with $LASTEXITCODE" }
