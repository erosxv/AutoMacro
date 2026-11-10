@echo off
rem Gera o executavel do AutoMacro para Windows em dist\AutoMacro\ (PyInstaller, modo onedir).
rem Prepara o ambiente sozinho se ainda nao existir. E preciso compilar em cada sistema
rem operacional: um executavel gerado no Windows nao roda no Linux (e vice-versa).
setlocal
cd /d "%~dp0"

set "NEEDSETUP="
if not exist ".venv\Scripts\python.exe" set "NEEDSETUP=1"
if not defined NEEDSETUP (
  ".venv\Scripts\python.exe" -c "import PyInstaller, PySide6, pynput" >nul 2>&1 || set "NEEDSETUP=1"
)
if defined NEEDSETUP (
  echo ==^> Ambiente incompleto; executando setup.bat primeiro
  call setup.bat || exit /b 1
)

echo ==^> Gerando o executavel ^(pode levar alguns minutos^)
".venv\Scripts\python.exe" -m PyInstaller --noconfirm --clean --distpath dist --workpath build\pyinstaller packaging\automacro.spec || (
  echo ERRO: a geracao do executavel falhou.
  exit /b 1
)

if exist "dist\AutoMacro\AutoMacro.exe" (
  echo ==^> Pronto: dist\AutoMacro\AutoMacro.exe
  echo     Distribua a pasta dist\AutoMacro inteira ^(compacte em .zip^).
  exit /b 0
)
echo ERRO: o executavel nao foi gerado.
exit /b 1
