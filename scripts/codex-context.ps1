[CmdletBinding(DefaultParameterSetName = 'Setup')]
param(
    [Parameter(ParameterSetName = 'Setup')]
    [switch] $Setup,

    [Parameter(Mandatory, ParameterSetName = 'Map')]
    [switch] $Map,

    [Parameter(Mandatory, ParameterSetName = 'Compress')]
    [string] $Compress
)

$ErrorActionPreference = 'Stop'
$project = Split-Path -Parent $PSScriptRoot
$context = Join-Path $project '.cache/codex-context'
$tokenSaver = Join-Path $context 'token-saver'
$memory = Join-Path $context 'memory-venv'
$mapTool = Join-Path $context 'codesight'
$codesight = Join-Path $mapTool 'node_modules/codesight/dist/index.js'
$tokenSaverRevision = 'bc058577e6e0c6581525f63e3bde963db4229130'
$memoryRevision = 'd594c8a86207fb9a8a5b48a6aab323349680707a'

function Invoke-Checked {
    param([string] $Program, [string[]] $Arguments)
    & $Program @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "$Program exited with status $LASTEXITCODE."
    }
}

Push-Location $project
try {
    if ($PSCmdlet.ParameterSetName -eq 'Compress') {
        $wrapper = Join-Path $tokenSaver 'scripts/wrap.py'
        if (!(Test-Path -LiteralPath $wrapper)) {
            throw 'Run scripts/codex-context.ps1 -Setup first.'
        }

        $gitExe = (Get-Command git.exe -ErrorAction Stop).Source
        $gitRoot = Split-Path -Parent (Split-Path -Parent $gitExe)
        $gitBash = Join-Path $gitRoot 'bin/bash.exe'
        $previousBash = $env:CLAUDE_CODE_GIT_BASH_PATH
        try {
            if (!$previousBash -and (Test-Path -LiteralPath $gitBash)) {
                $env:CLAUDE_CODE_GIT_BASH_PATH = $gitBash
            }
            & uv run --no-project --offline --python 3.12 $wrapper $Compress
            exit $LASTEXITCODE
        } finally {
            $env:CLAUDE_CODE_GIT_BASH_PATH = $previousBash
        }
    }

    if ($PSCmdlet.ParameterSetName -eq 'Setup') {
        New-Item -ItemType Directory -Force -Path $context | Out-Null
        if (!(Test-Path -LiteralPath (Join-Path $tokenSaver '.git'))) {
            Invoke-Checked git @('init', '--quiet', $tokenSaver)
            Invoke-Checked git @('-C', $tokenSaver, 'remote', 'add', 'origin', 'https://github.com/ppgranger/token-saver.git')
        }
        if (!(Test-Path -LiteralPath (Join-Path $tokenSaver 'scripts/wrap.py'))) {
            Invoke-Checked git @('-C', $tokenSaver, 'fetch', '--quiet', '--depth', '1', 'origin', $tokenSaverRevision)
            Invoke-Checked git @('-C', $tokenSaver, 'checkout', '--quiet', '--detach', $tokenSaverRevision)
        }
        if (!(Test-Path -LiteralPath (Join-Path $memory 'Scripts/codex-agent-mem-mcp.exe'))) {
            Invoke-Checked uv @('venv', '--python', '3.12', $memory)
            Invoke-Checked uv @('pip', 'install', '--python', (Join-Path $memory 'Scripts/python.exe'), "git+https://github.com/MarceloCaporale/codex-agent-mem.git@$memoryRevision")
        }
        if (!(Test-Path -LiteralPath $codesight)) {
            Invoke-Checked npm.cmd @('install', '--prefix', $mapTool, '--ignore-scripts', '--no-audit', '--no-fund', '--no-save', 'codesight@1.19.0')
        }
    }

    if (!(Test-Path -LiteralPath $codesight)) {
        throw 'Run scripts/codex-context.ps1 -Setup first.'
    }
    Invoke-Checked node @($codesight, '.', '--output', '.cache/codex-context/map', '--max-tokens', '3000')
} finally {
    Pop-Location
}
