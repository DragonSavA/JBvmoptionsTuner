param(
    [Parameter(Mandatory = $true)][ValidatePattern('^\d+\.\d+$')][string]$Release,
    [Parameter(Mandatory = $true)][ValidateSet('x64', 'x86', 'arm64')][string]$Architecture
)

$ErrorActionPreference = 'Stop'
try {
    # The parent Python process can be x86 on x64 Windows or x64 on ARM64.
    # Its ABI selects the runtime installer rather than the host OS alone.
    $winget = Get-Command winget.exe -ErrorAction SilentlyContinue
    if ($winget) {
        & $winget.Source install --exact --id "Microsoft.WindowsAppRuntime.$Release" --source winget --architecture $Architecture --silent --accept-package-agreements --accept-source-agreements
        if ($LASTEXITCODE -eq 0) { exit 0 }
        Write-Host 'Trying the official Windows App Runtime installer...'
    }
    $installer = Join-Path ([IO.Path]::GetTempPath()) ('vmopt-runtime-' + [Guid]::NewGuid().ToString('N') + '.exe')
    try {
        [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
        Invoke-WebRequest -UseBasicParsing -Uri "https://aka.ms/windowsappsdk/$Release/latest/windowsappruntimeinstall-$Architecture.exe" -OutFile $installer
        $signature = Get-AuthenticodeSignature -LiteralPath $installer
        if ($signature.Status -ne 'Valid' -or $signature.SignerCertificate.Subject -notmatch '(CN|O)=Microsoft Corporation(,|$)') {
            throw 'The Windows App Runtime installer signature could not be verified.'
        }
        $process = Start-Process -FilePath $installer -ArgumentList '--quiet' -WindowStyle Hidden -Wait -PassThru
        if ($process.ExitCode -notin @(0, 3010)) { throw "Windows App Runtime installer exited with code $($process.ExitCode)." }
    } finally {
        if (Test-Path -LiteralPath $installer) { Remove-Item -LiteralPath $installer -Force }
    }
    exit 0
} catch {
    Write-Host ('ERROR: ' + $_.Exception.Message) -ForegroundColor Red
    exit 1
}
