# gen-types.ps1
# This script generates TypeScript interfaces from Pydantic models.

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$RepoRoot = Split-Path -Parent $ScriptDir
$ModulePath = Join-Path $RepoRoot "packages/shared/python/evidence_shared/schemas.py"
$OutputPath = Join-Path $RepoRoot "apps/web/types/generated.ts"

Write-Host "Generating TypeScript interfaces from $ModulePath..."

# Try to find pydantic2ts
$Pydantic2Ts = Get-Command pydantic2ts -ErrorAction SilentlyContinue
if ($null -eq $Pydantic2Ts) {
    # Try common user-install location on Windows
    $UserScripts = Join-Path $env:APPDATA "Python\Python313\Scripts\pydantic2ts.exe"
    if (Test-Path $UserScripts) {
        $Pydantic2Ts = $UserScripts
    } else {
        # Search for any pydantic2ts.exe in AppData
        $UserScriptsBase = Join-Path $env:APPDATA "Python"
        if (Test-Path $UserScriptsBase) {
            $Found = Get-ChildItem -Path $UserScriptsBase -Filter "pydantic2ts.exe" -Recurse -ErrorAction SilentlyContinue | Select-Object -First 1
            if ($Found) {
                $Pydantic2Ts = $Found.FullName
            }
        }
    }
}

if ($null -eq $Pydantic2Ts) {
    Write-Error "pydantic2ts not found. Please install it with 'pip install pydantic-to-typescript2'"
    exit 1
}

Write-Host "Using pydantic2ts at $Pydantic2Ts"

# Use npx from the web app directory to ensure json2ts is available
$WebDir = Join-Path $RepoRoot "apps/web"
Push-Location $WebDir
& $Pydantic2Ts --module $ModulePath --output $OutputPath --json2ts-cmd "npx json2ts"
$Success = ($LASTEXITCODE -eq 0)
Pop-Location

if ($Success) {
    Write-Host "Successfully generated $OutputPath"
} else {
    Write-Error "Failed to generate TypeScript interfaces"
    exit 1
}
