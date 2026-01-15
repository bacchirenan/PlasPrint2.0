@echo off

REM ===== CONFIGURAÇÕES =====
REM Caminho do repo local
cd "D:\IMPRESSAO\SOFTWARES\PlasPrint IA v2.0\PlasPrint2.0"

REM Caminho do arquivo .db na unidade Y:
set SRC_DB="Y:\_ARQUIVOS\PlasPrint Fichas\fichas_tecnicas.db"

REM Caminho de destino dentro do repo
set DST_DB="D:\IMPRESSAO\SOFTWARES\PlasPrint IA v2.0\PlasPrint2.0\fichas_tecnicas.db"

REM ===== COPIAR O ARQUIVO =====
copy %SRC_DB% %DST_DB% /Y

REM ===== ATUALIZAR REPO (pull + commit + push) =====
git pull origin main

git add fichas_tecnicas.db

git commit -m "Atualização automática do fichas_tecnicas.db" || goto end

git push origin main

:end
exit /b 0
