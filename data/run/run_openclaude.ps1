Set-Location 'C:\Users\Adria\Documents'
$prompt = Get-Content -Raw 'C:\Users\Adria\Documents\lumina-agent\data\run\prompt.txt'
node 'C:\Users\Adria\AppData\Roaming\npm\node_modules\@gitlawb\openclaude\dist\cli.mjs' --dangerously-skip-permissions --no-session-persistence -p $prompt
'done' | Out-File -FilePath 'C:\Users\Adria\Documents\lumina-agent\data\run\done.sentinel' -Encoding utf8
Write-Host ''
Write-Host 'OpenClaude terminou. Pressione qualquer tecla para fechar.'
$null = $Host.UI.RawUI.ReadKey('NoEcho,IncludeKeyDown')
