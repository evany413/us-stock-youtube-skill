[CmdletBinding()]
param(
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$InstallerArgs
)

$ErrorActionPreference = "Stop"
$Installer = Join-Path $PSScriptRoot "install_skill.py"

& uv run --no-project --python 3.10 python $Installer @InstallerArgs
exit $LASTEXITCODE
