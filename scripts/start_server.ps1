<#
.SYNOPSIS
  Start the internal tools web app and print the address to share.

.DESCRIPTION
  Activates the virtual environment if there is one, checks the dependencies,
  then serves the app on every network interface so colleagues on the internal
  network can reach it.

.EXAMPLE
  .\scripts\start_server.ps1
  .\scripts\start_server.ps1 -Port 8080
#>

[CmdletBinding()]
param(
    [int]$Port = 8000,
    [switch]$SkipDependencyCheck
)

$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

foreach ($candidate in @('.venv\Scripts\Activate.ps1', 'venv\Scripts\Activate.ps1')) {
    if (Test-Path $candidate) {
        Write-Host "Activating virtual environment: $candidate" -ForegroundColor DarkGray
        . $candidate
        break
    }
}

if (-not $SkipDependencyCheck) {
    python -c "import fastapi, uvicorn, pandas, PIL, requests" 2>$null
    if ($LASTEXITCODE -ne 0) {
        Write-Host 'Installing dependencies...' -ForegroundColor Yellow
        python -m pip install -r requirements.txt --disable-pip-version-check
        if ($LASTEXITCODE -ne 0) {
            throw 'Dependencies could not be installed. Run: python -m pip install -r requirements.txt'
        }
    }

    # Optional tools. The app runs without any of them and says so on the tab, so
    # a missing or unreachable install must never stop the server.
    $optional = @(
        @{ Module = 'flatten_pdf';              Name = 'PDF Flatten';                Requirements = 'requirements-flatten.txt' },
        @{ Module = 'image_from_folder';        Name = 'Images from Folder';         Requirements = 'requirements-folder.txt' },
        @{ Module = 'greystar_email_converter'; Name = 'Emails to HTML and Images'; Requirements = 'requirements-emails.txt' }
    )

    foreach ($tool in $optional) {
        python -c "import $($tool.Module)" 2>$null
        if ($LASTEXITCODE -ne 0) {
            Write-Host "$($tool.Name) is not installed. That tool will show as unavailable." -ForegroundColor Yellow
            Write-Host "  To add it: python -m pip install -r $($tool.Requirements)" -ForegroundColor DarkGray
        }
    }

    # Emails to HTML and Images screenshots each email by shelling out to wkhtmltoimage,
    # which is an ordinary program and cannot be pip installed. Checked here so a
    # missing install is found now rather than by the first person to run a job.
    # Decoding to HTML works without it, so this is a warning, not a failure.
    python -c "import greystar_email_converter" 2>$null
    if ($LASTEXITCODE -eq 0) {
        python -c "from greystar_email_converter import find_wkhtmltoimage; find_wkhtmltoimage()" 2>$null
        if ($LASTEXITCODE -ne 0) {
            Write-Host 'wkhtmltoimage was not found. Email runs will produce HTML but no screenshots.' -ForegroundColor Yellow
            Write-Host '  Install it from https://wkhtmltopdf.org/downloads.html, or set WKHTMLTOIMAGE_PATH' -ForegroundColor DarkGray
            Write-Host '  to the full path of wkhtmltoimage.exe.' -ForegroundColor DarkGray
        }
    }
}

# The address colleagues type. Prefer the interface that reaches the network.
$address = (Get-NetIPConfiguration |
    Where-Object { $_.IPv4DefaultGateway -and $_.NetAdapter.Status -eq 'Up' } |
    Select-Object -First 1).IPv4Address.IPAddress

if (-not $address) {
    $address = (Get-NetIPAddress -AddressFamily IPv4 |
        Where-Object { $_.IPAddress -notlike '127.*' -and $_.IPAddress -notlike '169.254.*' } |
        Select-Object -First 1).IPAddress
}

Write-Host ''
Write-Host '  Internal Tools is starting' -ForegroundColor Cyan
Write-Host '  --------------------------'
Write-Host "  On this computer : http://localhost:$Port"
if ($address) {
    Write-Host "  Share this link  : http://$address`:$Port" -ForegroundColor Green
} else {
    Write-Host '  No network address found. Only this computer can reach the app.' -ForegroundColor Yellow
}
Write-Host ''
Write-Host '  If a colleague cannot open the link, allow the port through the firewall once,'
Write-Host '  from an administrator PowerShell window:'
Write-Host "    New-NetFirewallRule -DisplayName 'Internal Tools' -Direction Inbound ``" -ForegroundColor DarkGray
Write-Host "      -Protocol TCP -LocalPort $Port -Action Allow" -ForegroundColor DarkGray
Write-Host ''
Write-Host '  Press Ctrl+C to stop the server.' -ForegroundColor DarkGray
Write-Host ''

python -m uvicorn app.main:app --host 0.0.0.0 --port $Port
