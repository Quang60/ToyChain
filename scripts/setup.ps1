$ErrorActionPreference = 'Stop'
python (Join-Path $PSScriptRoot 'manage.py') setup
exit $LASTEXITCODE
