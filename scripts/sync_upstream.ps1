# Atualiza a branch pt-br-4redes a partir do repositorio oficial 3441293738/creatorhub
$ErrorActionPreference = "Stop"
git fetch upstream
git merge upstream/main --no-edit
Write-Host "Atualizacao concluida com sucesso! Se tiver um fork no GitHub (origin), rode: git push origin pt-br-4redes" -ForegroundColor Green
