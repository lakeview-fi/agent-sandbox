<#
.SYNOPSIS
Clone mode only: pull the sandbox agent's commits into a local branch of this repo and show them.
Runs the copy of pull_docker_commits.py (and sandbox_git_common.py) in sandbox/scripts/; nothing here duplicates its logic.
In direct mode (the default) there is nothing to pull: the agent's work is already in this repo.

.EXAMPLE
.\sandbox\pull.ps1           # fetch, show, create branch agent/<name>/<branch>
.\sandbox\pull.ps1 -Merge    # also fast-forward the current branch (hooks disabled)
#>
param(
    [switch]$Merge
)
$ErrorActionPreference = 'Stop'
# The develop-sandbox skill copies the agent-sandbox repo's scripts/*.py here. Adapt the copy to this repo if needed.
$Scripts = Join-Path $PSScriptRoot 'scripts'
if (-not (Test-Path (Join-Path $Scripts 'pull_docker_commits.py'))) { throw "Missing $Scripts\pull_docker_commits.py: copy it and sandbox_git_common.py there from the agent-sandbox repo's scripts/ folder." }
$Repo = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$Name = (Select-String -Path (Join-Path $Repo 'sbxenv.yaml') -Pattern '^name:\s*(\S+)').Matches[0].Groups[1].Value

# Direct mode (`sbx inspect` shows "Clone source: -"): the agent's work is already in this working tree.
$cloneLine = sbx inspect $Name 2>$null | Select-String -Pattern '^\s*Clone source:\s*(\S+)'
if ($cloneLine -and $cloneLine.Matches[0].Groups[1].Value -eq '-') {
    Write-Host "Sandbox $Name mounts this repo directly: its edits and commits are already here. Nothing to pull."
    Write-Host "Review with: git log --oneline -10 ; git status ; git diff"
    $kept = git -C $Repo for-each-ref --format='%(refname)' "refs/sandboxes/$Name/"
    if ($kept) { Write-Host "Commits pulled from an earlier clone-mode sandbox are kept under:"; $kept | ForEach-Object { Write-Host "  $_" } }
    return
}

$extra = @()
if ($Merge) { $extra += '--merge' }
python (Join-Path $Scripts 'pull_docker_commits.py') $Name --repo $Repo @extra
if ($LASTEXITCODE -ne 0) { throw "pull_docker_commits.py exited with $LASTEXITCODE" }
