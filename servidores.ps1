# Usado pelo iniciar.bat. Mensagens sem acento: o PowerShell 5.1 le este arquivo como ANSI.
#   parar:    encerra os servidores deste projeto que ainda estejam rodando e confere se as portas ficaram livres.
#   aguardar: espera o backend e o frontend novos aceitarem conexao.
# So toca em processos deste projeto: outro programa nas portas gera erro, e nao e encerrado.
param([Parameter(Mandatory = $true)][ValidateSet('parar', 'aguardar')][string]$Acao)

$PORTAS = @{ 8000 = 'backend'; 5173 = 'frontend' }

function Porta-Em-Uso([int]$porta) {
  $cliente = New-Object Net.Sockets.TcpClient
  try {
    $tentativa = $cliente.BeginConnect('127.0.0.1', $porta, $null, $null)
    return ($tentativa.AsyncWaitHandle.WaitOne(300) -and $cliente.Connected)
  } catch {
    return $false
  } finally {
    $cliente.Close()
  }
}

if ($Acao -eq 'aguardar') {
  $limite = (Get-Date).AddSeconds(45)
  while ((Get-Date) -lt $limite) {
    if (@($PORTAS.Keys | Where-Object { -not (Porta-Em-Uso $_) }).Count -eq 0) { exit 0 }
    Start-Sleep -Milliseconds 500
  }
  foreach ($porta in $PORTAS.Keys) {
    if (-not (Porta-Em-Uso $porta)) { Write-Host "O $($PORTAS[$porta]) nao subiu na porta $porta. Veja a janela dele." }
  }
  exit 1
}

$raiz = [regex]::Escape($PSScriptRoot)
$todos = @(Get-CimInstance Win32_Process)
$porId = @{}
foreach ($p in $todos) { $porId[[int]$p.ProcessId] = $p }

# Sobe ate a janela que abriu o servidor, para fecha-la junto em vez de deixar um prompt para tras.
function Topo-Do-Servidor($processo) {
  while ($true) {
    $pai = $porId[[int]$processo.ParentProcessId]
    if (-not $pai -or $pai.Name -notin 'cmd.exe', 'node.exe', 'python.exe') { return $processo }
    if ($pai.CommandLine -notmatch 'uvicorn|vite|npm') { return $processo }
    $processo = $pai
  }
}

$servidores = $todos | Where-Object {
  ($_.ExecutablePath -match "^$raiz\\backend\\\.venv\\" -and $_.CommandLine -match 'uvicorn app\.main:app .*--port 8000') -or
  ($_.CommandLine -match "$raiz\\frontend\\node_modules\\.*vite\.js")
}
$encerrados = @{}
foreach ($s in $servidores) {
  $topo = Topo-Do-Servidor $s
  if (-not $encerrados.ContainsKey([int]$topo.ProcessId)) {
    $encerrados[[int]$topo.ProcessId] = $true
    & taskkill.exe /T /F /PID $topo.ProcessId 2>&1 | Out-Null
  }
}
if ($encerrados.Count) { Write-Host "Servidores antigos encerrados: $($encerrados.Count)." }

$limite = (Get-Date).AddSeconds(8)
do {
  $ocupadas = @($PORTAS.Keys | Where-Object { Porta-Em-Uso $_ })
  if (-not $ocupadas.Count) { exit 0 }
  Start-Sleep -Milliseconds 300
} while ((Get-Date) -lt $limite)

foreach ($porta in $ocupadas) { Write-Host "A porta $porta ($($PORTAS[$porta])) esta em uso por outro programa." }
exit 1
