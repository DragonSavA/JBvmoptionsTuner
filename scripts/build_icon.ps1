param([string]$PreviewPath)

$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$assetDir = Join-Path $projectRoot 'jetbrains_vmoptions_tuner\assets'
$edgePath = Join-Path ${env:ProgramFiles(x86)} 'Microsoft\Edge\Application\msedge.exe'
if (-not (Test-Path -LiteralPath $edgePath)) {
    $edgePath = Join-Path $env:ProgramFiles 'Microsoft\Edge\Application\msedge.exe'
}
if (-not (Test-Path -LiteralPath $edgePath)) { throw 'Microsoft Edge is required to rebuild the ICO from SVG.' }

$tempDir = Join-Path ([IO.Path]::GetTempPath()) ('vmopt-icon-' + [Guid]::NewGuid().ToString('N'))
New-Item -Path $tempDir -ItemType Directory | Out-Null
$htmlPath = Join-Path $tempDir 'icon.html'
$pngPath = Join-Path $tempDir 'icon.png'
$profilePath = Join-Path $tempDir 'edge-profile'
$svg = Get-Content -LiteralPath (Join-Path $assetDir 'vmopt.svg') -Raw -Encoding UTF8
$html = '<!doctype html><meta charset="utf-8"><style>html,body{margin:0;width:1024px;height:1024px;overflow:hidden}svg{display:block;width:1024px;height:1024px}</style>' + $svg
[IO.File]::WriteAllText($htmlPath, $html, (New-Object Text.UTF8Encoding $false))
$uri = ([Uri]$htmlPath).AbsoluteUri
$arguments = @('--headless=new', '--disable-gpu', '--no-first-run', '--no-default-browser-check', '--hide-scrollbars', '--force-device-scale-factor=1', '--window-size=1024,1024', ('--screenshot="' + $pngPath + '"'), ('--user-data-dir="' + $profilePath + '"'), $uri)
$process = Start-Process -FilePath $edgePath -ArgumentList $arguments -WindowStyle Hidden -Wait -PassThru
if ($process.ExitCode -ne 0 -or -not (Test-Path -LiteralPath $pngPath)) { throw 'SVG rendering failed.' }
if ($PreviewPath) { Copy-Item -LiteralPath $pngPath -Destination $PreviewPath -Force }

Add-Type -AssemblyName System.Drawing
$source = [Drawing.Image]::FromFile($pngPath)
$sizes = @(16, 24, 32, 48, 64, 128, 256)
$images = New-Object 'System.Collections.Generic.List[byte[]]'
try {
    foreach ($size in $sizes) {
        $bitmap = New-Object Drawing.Bitmap $size, $size
        $graphics = [Drawing.Graphics]::FromImage($bitmap)
        $stream = New-Object IO.MemoryStream
        try {
            $graphics.InterpolationMode = [Drawing.Drawing2D.InterpolationMode]::HighQualityBicubic
            $graphics.PixelOffsetMode = [Drawing.Drawing2D.PixelOffsetMode]::HighQuality
            $graphics.DrawImage($source, 0, 0, $size, $size)
            $bitmap.Save($stream, [Drawing.Imaging.ImageFormat]::Png)
            $images.Add($stream.ToArray())
        } finally {
            $stream.Dispose()
            $graphics.Dispose()
            $bitmap.Dispose()
        }
    }
} finally { $source.Dispose() }

$icoPath = Join-Path $assetDir 'vmopt.ico'
$file = [IO.File]::Create($icoPath)
$writer = New-Object IO.BinaryWriter $file
try {
    $writer.Write([uint16]0)
    $writer.Write([uint16]1)
    $writer.Write([uint16]$sizes.Count)
    $offset = 6 + 16 * $sizes.Count
    for ($index = 0; $index -lt $sizes.Count; $index++) {
        $dimension = $sizes[$index] % 256
        $writer.Write([byte]$dimension)
        $writer.Write([byte]$dimension)
        $writer.Write([byte]0)
        $writer.Write([byte]0)
        $writer.Write([uint16]1)
        $writer.Write([uint16]32)
        $writer.Write([uint32]$images[$index].Length)
        $writer.Write([uint32]$offset)
        $offset += $images[$index].Length
    }
    foreach ($data in $images) { $writer.Write($data) }
} finally {
    $writer.Dispose()
    $file.Dispose()
}
Write-Host 'Generated' $icoPath
# Edge can briefly keep its profile open. Cleanup is confined to this build's
# newly allocated temporary directory; no project files are removed.
$resolvedTemp = [IO.Path]::GetFullPath($tempDir)
$tempPrefix = [IO.Path]::GetFullPath([IO.Path]::GetTempPath()).TrimEnd('\') + '\'
if ($resolvedTemp.StartsWith($tempPrefix, [StringComparison]::OrdinalIgnoreCase) -and
    (Split-Path -Leaf $resolvedTemp) -match '^vmopt-icon-[a-f0-9]{32}$') {
    Remove-Item -LiteralPath $resolvedTemp -Recurse -Force -ErrorAction SilentlyContinue
}
