$ErrorActionPreference = 'Stop'
python (Join-Path $PSScriptRoot 'manage.py') check
exit $LASTEXITCODE
