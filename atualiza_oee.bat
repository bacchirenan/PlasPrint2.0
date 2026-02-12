@echo off
REM ===== CAMINHO DO REPO =====
cd /d "D:\IMPRESSAO\SOFTWARES\PlasPrint IA v2.0"

REM ===== ATUALIZAR DO GITHUB =====
git pull origin main

REM ===== ADICIONAR AS 4 PLANILHAS (NOMES EXATOS DO REPO) =====
git add "oee teep.xlsx" "producao.xlsx" "Canudos.xlsx" "rejeito.xlsx"

REM ===== SEMPRE CRIAR COMMIT, MESMO SEM MUDANÇA =====
git commit --allow-empty -m "Atualização automática OEE, Canudos, Producao e Rejeito (%date% %time%)"

REM ===== ENVIAR PARA O GITHUB =====
git push origin main

REM ===== VER LOG =====
pause
