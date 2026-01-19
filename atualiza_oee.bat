@echo off
cd /d "D:\IMPRESSAO\SOFTWARES\PlasPrint IA v2.0"
git pull origin main
git add "oee teep.xlsx"
git commit -m "Atualização automática do OEE (%date% %time%)"
git push origin main
