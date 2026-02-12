@echo off
chcp 850 >nul
setlocal enabledelayedexpansion

REM ===== CONFIGURAÇÕES =====
set ORIGEM=Y:\PLANILHAS
set DESTINO=D:\IMPRESSAO\SOFTWARES\PlasPrint IA v2.0
set ORIGEM_DB=Y:\_ARQUIVOS\PlasPrint Fichas

REM ===== CRIAR PASTA DESTINO SE NÃO EXISTIR =====
if not exist "%DESTINO%" (
    echo Criando pasta de destino: %DESTINO%
    mkdir "%DESTINO%"
)

echo Copiando arquivos de %ORIGEM% para %DESTINO%...

REM Canudos.xlsx
if exist "%ORIGEM%\Canudos.xlsx" (
    copy "%ORIGEM%\Canudos.xlsx" "%DESTINO%\Canudos.xlsx" /Y
    echo ✓ Canudos.xlsx copiado com sucesso
) else (
    echo ⚠ Arquivo Canudos.xlsx não encontrado em %ORIGEM%
)

REM producao.xlsx
if exist "%ORIGEM%\producao.xlsx" (
    copy "%ORIGEM%\producao.xlsx" "%DESTINO%\producao.xlsx" /Y
    echo ✓ producao.xlsx copiado com sucesso
) else (
    echo ⚠ Arquivo producao.xlsx não encontrado em %ORIGEM%
)

REM oee teep.xlsx
if exist "%ORIGEM%\oee teep.xlsx" (
    copy "%ORIGEM%\oee teep.xlsx" "%DESTINO%\oee teep.xlsx" /Y
    echo ✓ oee teep.xlsx copiado com sucesso
) else (
    echo ⚠ Arquivo oee teep.xlsx não encontrado em %ORIGEM%
)

REM oee teep.xlsx
if exist "%ORIGEM%\rejeito.xlsx" (
    copy "%ORIGEM%\rejeito.xlsx" "%DESTINO%\rejeito.xlsx" /Y
    echo ✓ rejeito.xlsx copiado com sucesso
) else (
    echo ⚠ Arquivo rejeito.xlsx não encontrado em %ORIGEM%
)

echo.
echo Copiando fichas_tecnicas.db de %ORIGEM_DB% para %DESTINO%...
if exist "%ORIGEM_DB%\fichas_tecnicas.db" (
    copy "%ORIGEM_DB%\fichas_tecnicas.db" "%DESTINO%\fichas_tecnicas.db" /Y
    echo ✓ fichas_tecnicas.db copiado com sucesso
) else (
    echo ⚠ Arquivo fichas_tecnicas.db não encontrado em %ORIGEM_DB%
)

echo.
echo Processo concluído!
pause
