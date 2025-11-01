
``powershell name=scripts/create-and-commit-gitignore.ps1
# create-and-commit-gitignore.ps1
# Writes a correct .gitignore, refreshes git index, stages files, commits on branch feat/auto-setup.
# Designed to run on Windows runner (actions/windows-latest) or locally in PowerShell.
Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

# Ensure running in repo root
$cwd = (Get-Location).Path
if ($cwd -notlike "*ict-trading-bot*") {
  Write-Error "Please run this script from the repository root (ict-trading-bot). Current path: $cwd"
  exit 1
}

# Exact .gitignore content (ENGLISH, each pattern on its own line)
$gitignoreLines = @(
  "*.csv",
  "*.csv.backup*",
  "/backup/",
  "/results/",
  "bot_output.txt",
  "backtest_run_output.txt",
  "analyze_output.txt",
  "*.bak",
  "*.backup",
  "/data/",
  "/dataGBPUSD_M15.csv",
  "*.pyc",
  "__pycache__/",
  ".env",
  ".venv/"
)

# Write .gitignore as UTF8 (no BOM)
$gitignoreLines | Set-Content -Encoding UTF8 .gitignore
Write-Output "Wrote .gitignore with $($gitignoreLines.Count) lines."

# Show file for logs
Write-Output "Current .gitignore content:"
Get-Content .gitignore | ForEach-Object { Write-Output "  $_" }

# Ensure git exists / initialized
if (-not (Test-Path .git\HEAD)) {
  Write-Output "No git repo detected — initializing..."
  git init
}

# Use branch for auto changes
$branch = "feat/auto-setup"

# Create or switch to branch
try {
  git checkout -B $branch
  Write-Output "Checked out branch $branch."
} catch {
  Write-Warning "Could not create/switch branch $branch — continuing on current branch."
}

# Refresh index so .gitignore takes effect
Write-Output "Removing cached files from index (if any)..."
git rm -r --cached . 2>$null || Write-Warning "git rm --cached returned non-zero or nothing to remove."

# Stage .gitignore and primary project files (silence missing-file errors)
Write-Output "Staging .gitignore and primary files..."
git add .gitignore 2>$null
git add ict_bot.py 2>$null
git add requirements.txt 2>$null
git add run_backtest_august2025.py 2>$null
git add run_fix_and_backtest_august2025.py 2>$null
git add analyze_signals_local.py 2>$null
# If you prefer to stage everything, uncomment the next line:
# git add -A

# Show staged files
Write-Output "Staged files (git status --short):"
git status --short

# Commit if there are staged changes
$staged = git diff --cached --name-only
if ($staged) {
  git commit -m "chore: add .gitignore and stage bot files (auto-setup)"
  Write-Output "Committed changes."
} else {
  Write-Output "No staged changes to commit."
}

# Push changes so create-pull-request action can open PR (in Actions runner this may succeed with persist-credentials)
try {
  git push --set-upstream origin $branch 2>$null
  Write-Output "Pushed branch $branch to origin."
} catch {
  Write-Warning "Push failed (may be expected in some runners). create-pull-request action will create the PR if possible."
}

Write-Output "Script finished."
