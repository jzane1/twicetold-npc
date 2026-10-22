#requires -Version 7.0
<#
Build and verify the documented fake-provider stack in a fresh Compose project.
No .env or host Python required. Logs remain in artifacts/verification/<project>.
#>
[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'
$PSNativeCommandUseErrorActionPreference = $false
$repoRoot = Split-Path -Parent $PSScriptRoot
$project = 'twicetold-verify-' + [guid]::NewGuid().ToString('N')
$testContainer = "$project-tests"
$artifactDir = Join-Path $repoRoot "artifacts/verification/$project"
$compose = @('compose', '--env-file', '.env.example', '-p', $project,
    '-f', 'compose.demo.yml', '-f', 'compose.verify.yml')
$testsStarted = $false
$passed = $false

function Invoke-DockerCheck {
    param([string]$Log, [string[]]$Arguments)
    & docker @Arguments 2>&1 | Tee-Object -FilePath (Join-Path $artifactDir "$Log.log") | Out-Host
    if ($LASTEXITCODE -ne 0) {
        throw "$Log failed (exit $LASTEXITCODE). See $artifactDir."
    }
}

Get-Command docker -ErrorAction Stop | Out-Null
New-Item -ItemType Directory -Path $artifactDir -Force | Out-Null
Push-Location $repoRoot
try {
    $revision = 'source archive'
    if (Test-Path -LiteralPath '.git') {
        $revision = (& git rev-parse HEAD).Trim()
        if ($LASTEXITCODE -ne 0) { throw 'Could not record source revision.' }
    }
    [ordered]@{
        revision = $revision
        project = $project
        started_at = [DateTimeOffset]::UtcNow.ToString('o')
        provider_mode = 'fake'
    } | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $artifactDir 'run.json') -Encoding utf8

    Invoke-DockerCheck 'build' ($compose + @('build', 'api'))
    Invoke-DockerCheck 'image' @('image', 'inspect', "$project-app:verify", '--format', '{{.Id}}')
    Invoke-DockerCheck 'dependencies' ($compose + @('run', '--rm', '--no-deps', 'tests', 'python', '-m', 'pip', 'freeze'))
    Invoke-DockerCheck 'lint' ($compose + @('run', '--rm', '--no-deps', 'tests', 'python', '-m', 'ruff', 'check', 'app', 'db', 'tests', 'examples'))
    Invoke-DockerCheck 'format' ($compose + @('run', '--rm', '--no-deps', 'tests', 'python', '-m', 'ruff', 'format', '--check', 'app', 'db', 'tests', 'examples'))
    Invoke-DockerCheck 'startup' ($compose + @('up', '-d', '--wait', '--wait-timeout', '360', 'api'))
    Invoke-DockerCheck 'migration-rerun' ($compose + @('run', '--rm', '--no-deps', 'migrate'))
    $testsStarted = $true
    Invoke-DockerCheck 'pytest' ($compose + @('run', '--name', $testContainer, '--no-deps', 'tests'))
    Invoke-DockerCheck 'first-run' ($compose + @('run', '--rm', '--no-deps', 'demo'))
    Invoke-DockerCheck 'application' ($compose + @('run', '--rm', '--no-deps', 'demo',
        'python', '-m', 'examples.chat', '--base-url', 'http://api:8000',
        '--state', '/tmp/chat-session.json', '--demo'))
    $passed = $true
}
finally {
    # Cleanup uses only this invocation's generated names. Never prune shared Docker state.
    try {
        & docker @compose ps -a 2>&1 | Set-Content -LiteralPath (Join-Path $artifactDir 'containers.log') -Encoding utf8
        & docker @compose logs --no-color --tail 150 api migrate db 2>&1 | Set-Content -LiteralPath (Join-Path $artifactDir 'services.log') -Encoding utf8
        if ($testsStarted) {
            & docker cp "${testContainer}:/tmp/pytest.xml" (Join-Path $artifactDir 'pytest.xml')
            if ($LASTEXITCODE -ne 0) { Write-Warning 'No pytest XML was available; inspect pytest.log.' }
            & docker rm -f $testContainer | Out-Host
        }
    }
    finally {
        try {
            & docker @compose down --volumes --remove-orphans 2>&1 | Tee-Object -FilePath (Join-Path $artifactDir 'cleanup.log') | Out-Host
            if ($LASTEXITCODE -ne 0) { throw "Verification project cleanup failed: $project" }
        }
        finally { Pop-Location }
    }
}
if ($passed) { Write-Host "PASS clean backend verification. Reports: $artifactDir" }
