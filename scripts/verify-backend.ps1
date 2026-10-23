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
$evalContainer = "$project-eval"
$restoreContainer = "$project-restore"
$artifactDir = Join-Path $repoRoot "artifacts/verification/$project"
$compose = @('compose', '--env-file', '.env.example', '-p', $project,
    '-f', 'compose.demo.yml', '-f', 'compose.verify.yml')
$testsStarted = $false
$passed = $false
$steps = [ordered]@{}

function Invoke-DockerCheck {
    param([string]$Log, [string[]]$Arguments)
    & docker @Arguments 2>&1 | Tee-Object -FilePath (Join-Path $artifactDir "$Log.log") | Out-Host
    $steps[$Log] = $LASTEXITCODE
    if ($LASTEXITCODE -ne 0) {
        throw "$Log failed (exit $LASTEXITCODE). See $artifactDir."
    }
}

Get-Command docker -ErrorAction Stop | Out-Null
New-Item -ItemType Directory -Path $artifactDir -Force | Out-Null
Push-Location $repoRoot
try {
    $revision = 'source archive'
    $changes = @()
    if (Test-Path -LiteralPath '.git') {
        $revision = (& git rev-parse HEAD).Trim()
        if ($LASTEXITCODE -ne 0) { throw 'Could not record source revision.' }
        $changes = @(& git status --porcelain --untracked-files=normal)
    }
    $run = [ordered]@{
        revision = $revision
        working_tree_changes = $changes
        project = $project
        started_at = [DateTimeOffset]::UtcNow.ToString('o')
        provider_mode = 'fake'
        configuration = 'compose.demo.yml + compose.verify.yml; .env.example; no private .env'
        quality_claim = 'Structural checks only; fake embeddings and prose do not establish semantic quality.'
    }
    $run | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $artifactDir 'run.json') -Encoding utf8

    Invoke-DockerCheck 'build' ($compose + @('build', 'api'))
    Invoke-DockerCheck 'image' @('image', 'inspect', "$project-app:verify", '--format', '{{.Id}}')
    Invoke-DockerCheck 'dependencies' ($compose + @('run', '--rm', '--no-deps', 'tests', 'python', '-m', 'pip', 'freeze'))
    Invoke-DockerCheck 'lint' ($compose + @('run', '--rm', '--no-deps', 'tests', 'python', '-m', 'ruff', 'check', 'app', 'db', 'tests', 'examples'))
    Invoke-DockerCheck 'format' ($compose + @('run', '--rm', '--no-deps', 'tests', 'python', '-m', 'ruff', 'format', '--check', 'app', 'db', 'tests', 'examples'))
    Invoke-DockerCheck 'startup' ($compose + @('up', '-d', '--wait', '--wait-timeout', '360', 'api'))
    Invoke-DockerCheck 'database-image' ($compose + @('images', 'db', '--format', 'json'))
    Invoke-DockerCheck 'ready' ($compose + @('run', '--rm', '--no-deps', 'tests', 'python', '-m', 'tests.verify_deployment', 'ready'))
    Invoke-DockerCheck 'migration-rerun' ($compose + @('run', '--rm', '--no-deps', 'migrate'))
    $testsStarted = $true
    Invoke-DockerCheck 'pytest' ($compose + @('run', '--name', $testContainer, '--no-deps', 'tests'))
    Invoke-DockerCheck 'first-run' ($compose + @('run', '--rm', '--no-deps', 'demo'))
    Invoke-DockerCheck 'application' ($compose + @('run', '--rm', '--no-deps', 'demo',
        'python', '-m', 'examples.chat', '--base-url', 'http://api:8000',
        '--state', '/tmp/chat-session.json', '--demo'))
    Invoke-DockerCheck 'evaluation' ($compose + @('run', '--name', $evalContainer, '--no-deps', 'tests',
        'python', '-m', 'app.eval_runner', 'run', '--scenarios', 'data/eval/scenarios/smoke.jsonl', '--out', '/tmp/evaluation.json'))

    # Exercise a real outage and recovery only in this disposable project.
    Invoke-DockerCheck 'database-stop' ($compose + @('stop', 'db'))
    Invoke-DockerCheck 'unavailable' ($compose + @('run', '--rm', '--no-deps', 'tests', 'python', '-m', 'tests.verify_deployment', 'unavailable'))
    Invoke-DockerCheck 'database-recovery' ($compose + @('up', '-d', '--wait', '--wait-timeout', '90', 'db'))
    Invoke-DockerCheck 'api-recovery' ($compose + @('up', '-d', '--wait', '--wait-timeout', '90', 'api'))
    Invoke-DockerCheck 'recovered' ($compose + @('run', '--rm', '--no-deps', 'tests', 'python', '-m', 'tests.verify_deployment', 'ready'))

    # Quiesce all writers. The custom-format archive stays binary (no shell redirection).
    Invoke-DockerCheck 'quiesce' ($compose + @('stop', 'api'))
    Invoke-DockerCheck 'backup' ($compose + @('exec', '-T', 'db', 'pg_dump', '-U', 'demo', '-d', 'demo', '--format=custom', '--file=/tmp/verify.dump'))
    Invoke-DockerCheck 'backup-copy' ($compose + @('cp', 'db:/tmp/verify.dump', (Join-Path $artifactDir 'demo.dump')))
    Invoke-DockerCheck 'restore-create' ($compose + @('exec', '-T', 'db', 'createdb', '-U', 'demo', '--template=template0', 'twicetold_restore'))
    Invoke-DockerCheck 'restore' ($compose + @('exec', '-T', 'db', 'pg_restore', '-U', 'demo', '-d', 'twicetold_restore', '--exit-on-error', '--single-transaction', '--no-owner', '--no-privileges', '/tmp/verify.dump'))
    Invoke-DockerCheck 'restore-check' ($compose + @('run', '--name', $restoreContainer, '--no-deps', 'tests',
        'python', '-m', 'tests.verify_deployment', 'restore', '--out', '/tmp/restore.json'))
    $passed = $true
}
finally {
    # Cleanup uses only this invocation's generated names. Never prune shared Docker state.
    try {
        & docker @compose ps -a 2>&1 | Set-Content -LiteralPath (Join-Path $artifactDir 'containers.log') -Encoding utf8
        & docker @compose logs --no-color --tail 150 api migrate db 2>&1 | Set-Content -LiteralPath (Join-Path $artifactDir 'services.log') -Encoding utf8
        if ($testsStarted) {
            & docker cp "${testContainer}:/tmp/pytest.xml" (Join-Path $artifactDir 'pytest.xml')
            if ($LASTEXITCODE -ne 0) { Write-Warning 'No pytest XML was available; inspect pytest.log.'; $passed = $false }
            & docker rm -f $testContainer | Out-Host
        }
        foreach ($item in @(@($evalContainer, 'evaluation.json'), @($restoreContainer, 'restore.json'))) {
            & docker container inspect $item[0] --format '{{.Id}}' 2>$null | Out-Null
            if ($LASTEXITCODE -eq 0) {
                & docker cp "$($item[0]):/tmp/$($item[1])" (Join-Path $artifactDir $item[1])
                if ($LASTEXITCODE -ne 0) { Write-Warning "No $($item[1]) was available; inspect the step log."; $passed = $false }
                & docker rm -f $item[0] | Out-Host
            }
        }
    }
    finally {
        try {
            & docker @compose down --volumes --remove-orphans 2>&1 | Tee-Object -FilePath (Join-Path $artifactDir 'cleanup.log') | Out-Host
            if ($LASTEXITCODE -ne 0) { $passed = $false; throw "Verification project cleanup failed: $project" }
        }
        finally {
            if ($run) {
                $run['completed_at'] = [DateTimeOffset]::UtcNow.ToString('o')
                $run['passed'] = $passed
                $run['step_exit_codes'] = $steps
                $run | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath (Join-Path $artifactDir 'run.json') -Encoding utf8
            }
            Pop-Location
        }
    }
}
if ($passed) { Write-Host "PASS clean backend verification. Reports: $artifactDir" }
else { throw "Verification incomplete. Reports: $artifactDir" }
