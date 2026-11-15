param(
    [Parameter(Mandatory=$true)][string]$Cloudflared,
    [int]$Port = 8012
)
$ErrorActionPreference = 'Stop'
$application = "http://127.0.0.1:$Port"
$health = Invoke-RestMethod "$application/api/health" -TimeoutSec 3
if (-not $health.llm.ready -or $health.llm.runtime -ne 'llama.cpp' -or -not $health.public_demo) {
    throw 'Start AeroFox in public demo mode on this loopback port first.'
}
$command = Get-Command $Cloudflared -CommandType Application
Write-Host 'Share the temporary HTTPS URL while the tunnel is running. Press Ctrl+C to close it.'
& $command.Source tunnel --url $application --protocol http2
exit $LASTEXITCODE

