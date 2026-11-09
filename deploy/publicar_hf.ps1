<#
Publica o commit atual no Hugging Face Spaces.

Uso (na raiz do projeto):
    .\deploy\publicar_hf.ps1 https://huggingface.co/spaces/USUARIO/NOME

O Space recebe uma cópia do commit, sem as imagens de docs/ (o Hugging Face recusa
binários enviados por git comum) e com o README de deploy/huggingface/, que tem o
cabeçalho de configuração do Space. O histórico do Space é só de publicações: cada
envio substitui o anterior (push --force). O histórico real fica no GitHub.

Na primeira vez, o git pede usuário e senha: use o seu usuário do Hugging Face e,
como senha, um token de acesso com permissão "Write" (huggingface.co/settings/tokens).
#>
param([Parameter(Mandatory = $true)][string]$Space)

$ErrorActionPreference = "Stop"
$raiz = Split-Path -Parent $PSScriptRoot

function Git-Ok {
    param([string[]]$Argumentos)
    & git @Argumentos
    if ($LASTEXITCODE -ne 0) { throw "Falhou: git $($Argumentos -join ' ')" }
}

if ($Space -notmatch '^https://huggingface\.co/spaces/[^/]+/[^/]+$') {
    throw "Endereço inesperado: $Space. Use https://huggingface.co/spaces/USUARIO/NOME"
}
if (git -C $raiz status --porcelain) {
    throw "Há mudanças sem commit. Faça o commit antes de publicar, para o Space mostrar uma versão que está no GitHub."
}

$commit = (git -C $raiz rev-parse --short HEAD).Trim()
$pasta = Join-Path $env:TEMP "swing-b3-hf"
if (Test-Path $pasta) { Remove-Item -Recurse -Force $pasta }
New-Item -ItemType Directory -Path $pasta | Out-Null

# Cópia exata do commit, sem nada que não esteja versionado (banco, token, .venv).
Git-Ok @("-C", $raiz, "archive", "--format=tar", "-o", "$pasta\fonte.tar", "HEAD")
& "$env:SystemRoot\System32\tar.exe" -xf "$pasta\fonte.tar" -C $pasta
if ($LASTEXITCODE -ne 0) { throw "Falhou ao extrair a cópia do commit." }
Remove-Item "$pasta\fonte.tar"
Remove-Item -Recurse -Force "$pasta\docs\imagens"
Copy-Item -Force "$raiz\deploy\huggingface\README.md" "$pasta\README.md"

Git-Ok @("-C", $pasta, "init", "-q", "-b", "main")
Git-Ok @("-C", $pasta, "add", "-A")
Git-Ok @("-C", $pasta, "commit", "-q", "-m", "Publicação do commit $commit do GitHub")
Git-Ok @("-C", $pasta, "push", "--force", $Space, "main")

Write-Host ""
Write-Host "Enviado o commit $commit. O Space monta a imagem em alguns minutos; acompanhe em $Space"
