@echo off
setlocal enabledelayedexpansion

REM ===== CONFIGURAÇÕES =====
set ORIGEM=Y:\PLANILHAS
set DESTINO=D:\IMPRESSAO\SOFTWARES\PlasPrint IA v2.0
set ORIGEM_DB=Y:_ARQUIVOS\PlasPrint Fichas

REM ===== CRIAR PASTA DESTINO SE NÃO EXISTIR =====
if not exist "%DESTINO%" (
echo Criando pasta de destino: %DESTINO%
mkdir "%DESTINO%"
)

REM ===== COPIAR ARQUIVOS COM SOBRESCRITA =====
echo Copiando arquivos de %ORIGEM% para %DESTINO%...

for %%f in (Canudos.xlsx producao.xlsx "oee teep.xlsx") do (
if exist "%ORIGEM%%%~f" (
copy "%ORIGEM%%%~f" "%DESTINO%" /Y
if !errorlevel! equ 0 (
echo ✓ %%~f copiado com sucesso
) else (
echo ✗ Erro ao copiar %%~f
)
) else (
echo ⚠ Arquivo %%~f não encontrado em %ORIGEM%
)
)

REM ===== COPIAR ARQUIVO DB =====
echo.
echo Copiando fichas_tecnicas.db de %ORIGEM_DB% para %DESTINO%...
if exist "%ORIGEM_DB%\fichas_tecnicas.db" (
copy "%ORIGEM_DB%\fichas_tecnicas.db" "%DESTINO%\fichas_tecnicas.db" /Y
if !errorlevel! equ 0 (
echo ✓ fichas_tecnicas.db copiado com sucesso
​
) else (
echo ✗ Erro ao copiar fichas_tecnicas.db
)
) else (
echo ⚠ Arquivo fichas_tecnicas.db não encontrado em %ORIGEM_DB%
​
)

echo.
echo Processo concluído!
pause