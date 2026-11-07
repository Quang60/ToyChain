$ErrorActionPreference = 'Stop'
python (Join-Path $PSScriptRoot 'manage.py') integration
exit $LASTEXITCODE
