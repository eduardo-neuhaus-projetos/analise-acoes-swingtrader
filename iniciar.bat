@echo off
rem Encerra os servidores anteriores deste projeto e sobe o backend e o frontend em janelas separadas.
rem Na primeira vez, instala as dependencias.
setlocal
cd /d "%~dp0"

if not exist backend\.venv (
  echo Criando o ambiente Python...
  python -m venv backend\.venv || goto :erro
  backend\.venv\Scripts\python -m pip install -r backend\requirements.txt || goto :erro
)
if not exist frontend\node_modules (
  echo Instalando o frontend...
  pushd frontend
  call npm install || goto :erro
  popd
)

rem Sem isto, um backend antigo segura a porta e o navegador abre com o codigo velho.
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0servidores.ps1" parar || goto :portas

start "Swing B3 - backend" /d "%~dp0backend" cmd /k .venv\Scripts\python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
start "Swing B3 - frontend" /d "%~dp0frontend" cmd /k npm run dev
echo Aguardando os servidores...
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0servidores.ps1" aguardar || goto :nao_subiu
start http://127.0.0.1:5173/
exit /b 0

:portas
echo Feche o programa que usa a porta e rode de novo.
pause
exit /b 1

:nao_subiu
echo Os servidores nao ficaram prontos. Veja as janelas do Swing B3.
pause
exit /b 1

:erro
echo Falha na instalacao. Veja a mensagem acima.
pause
exit /b 1
