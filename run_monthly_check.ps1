# 每週四 20:00 執行，判斷是否為當月第三個週四
$today = Get-Date
if ($today.DayOfWeek -ne [DayOfWeek]::Thursday) { exit 0 }

# 計算本月第三個週四的日期
$firstDay = Get-Date -Year $today.Year -Month $today.Month -Day 1
$daysUntilThursday = ([DayOfWeek]::Thursday - $firstDay.DayOfWeek + 7) % 7
$firstThursday = $firstDay.AddDays($daysUntilThursday)
$thirdThursday = $firstThursday.AddDays(14)

if ($today.Date -eq $thirdThursday.Date) {
    Write-Host "$(Get-Date -Format 'yyyy-MM-dd HH:mm') 今天是本月第三個週四，執行 fetch_options.py"
    & "D:\ClaudeCode工作區\stock-tracker\run_monthly.bat"
} else {
    Write-Host "$(Get-Date -Format 'yyyy-MM-dd HH:mm') 今天不是第三週四（第三週四為 $($thirdThursday.ToString('yyyy-MM-dd'))），略過"
}
