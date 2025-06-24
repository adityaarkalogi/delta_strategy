# delta-shift

Get-Process | Where-Object {$_.ProcessName -like "*start_execution*"} 
Stop-Process -Name "start_execution" -Force
Stop-Process -Id 1996 -Force
