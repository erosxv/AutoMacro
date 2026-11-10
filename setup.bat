@echo off
rem Prepara tudo para rodar o AutoMacro no Windows: cria o ambiente virtual (.venv),
rem instala TODAS as dependencias e roda o diagnostico. Pode ser executado varias vezes.
setlocal
cd /d "%~dp0"

rem 1) Python 3.11 ou superior ------------------------------------------------------------
set "PYCMD="
for %%V in (3.13 3.12 3.11 3.14) do (
  if not defined PYCMD (
    py -%%V -c "import sys" >nul 2>&1 && set "PYCMD=py -%%V"
  )
)
if not defined PYCMD (
  python -c "import sys; sys.exit(0 if sys.version_info >= (3, 11) else 1)" >nul 2>&1 && set "PYCMD=python"
)
if not defined PYCMD (
  echo.
  echo ERRO: Python 3.11 ou superior nao encontrado.
  echo Instale em https://www.python.org/downloads/ marcando "Add python.exe to PATH"
  echo ou, se tiver o winget:  winget install Python.Python.3.12
  echo Depois execute setup.bat novamente.
  exit /b 1
)
echo ==^> Usando %PYCMD%

rem 2) Ambiente virtual -------------------------------------------------------------------
if exist ".venv\Scripts\python.exe" (
  ".venv\Scripts\python.exe" -c "import sys" >nul 2>&1 || (
    echo ==^> Ambiente virtual quebrado; recriando
    rmdir /s /q .venv
  )
)
if not exist ".venv\Scripts\python.exe" (
  echo ==^> Criando ambiente virtual ^(.venv^)
  %PYCMD% -m venv .venv || (
    echo ERRO: nao consegui criar o ambiente virtual.
    exit /b 1
  )
)

rem 3) Dependencias -----------------------------------------------------------------------
echo ==^> Instalando dependencias ^(pode levar alguns minutos na primeira vez^)
".venv\Scripts\python.exe" -m pip install --quiet --upgrade pip || goto :pipfail
".venv\Scripts\python.exe" -m pip install --quiet -r requirements-dev.txt || goto :pipfail
rem pynput sem dependencias declaradas: mesmo conjunto do setup.sh (ver requirements.txt)
".venv\Scripts\python.exe" -m pip install --quiet --no-deps "pynput>=1.7.7" || goto :pipfail
".venv\Scripts\python.exe" -m pip install --quiet --no-deps -e . || goto :pipfail

rem 4) Diagnostico ------------------------------------------------------------------------
echo ==^> Verificando o ambiente
".venv\Scripts\python.exe" -m automacro.doctor
if errorlevel 1 (
  echo.
  echo O diagnostico encontrou problemas ^(acima^).
  exit /b 1
)
echo ==^> Tudo pronto. Para abrir o aplicativo, de dois cliques em run.bat
exit /b 0

:pipfail
echo.
echo ERRO ao instalar as dependencias. Verifique sua conexao com a internet e tente de novo.
exit /b 1
