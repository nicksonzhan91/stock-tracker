$repo = "D:\ClaudeCode工作區\stock-tracker"
git -C $repo add data/latest.json
$diff = git -C $repo diff --cached --name-only
if ($diff) {
    git -C $repo commit -m "data: update latest.json"
    git -C $repo push origin main
    Write-Host "[GitHub] Push 完成"
} else {
    Write-Host "[GitHub] latest.json 無變動，略過 push"
}
