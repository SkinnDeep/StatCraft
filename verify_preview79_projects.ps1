$ErrorActionPreference='Stop'
$taskRoot=(Resolve-Path (Join-Path $PSScriptRoot '../..')).Path
$env:QT_QPA_PLATFORM='offscreen'
$env:TEMP=Join-Path $taskRoot 'work'
$env:TMP=$env:TEMP
$taskExe=Join-Path $taskRoot 'outputs/StatCraft-preview79.exe'
$taskNames=@('model-plots','optimizer','logistic','prediction','gage-rr','response-surface','glm','data-preparation','output-workspace','graph-builder','individual-interval','dotplot-variants','quiz1','boxplot-variants','histogram-variants','attribute-capability','advanced-quality','multiple-capability')
for($taskOffset=0;$taskOffset -lt $taskNames.Length;$taskOffset+=4){
 $taskRuns=@()
 foreach($taskName in $taskNames[$taskOffset..([Math]::Min($taskOffset+3,$taskNames.Length-1))]){
  $taskFixture=if($taskName -eq 'quiz1'){'C:/Users/funny/Downloads/quiz1.mpx'}else{Join-Path $taskRoot ('outputs/StatCraft-'+$taskName+'-demo.mpx')}
  $taskReport=Join-Path $taskRoot ('work/preview79-'+$taskName+'-packaged-verified.json')
  $taskArgs=@('--verify-project',('"'+$taskFixture+'"'),('"'+$taskReport+'"'))
  $taskChild=Start-Process -FilePath $taskExe -ArgumentList $taskArgs -WindowStyle Hidden -PassThru
  $taskRuns+=,@($taskChild,$taskReport)
 }
 foreach($taskRun in $taskRuns){
  if(-not $taskRun[0].WaitForExit(60000)){throw ('Timed out: '+$taskRun[1])}
  if($taskRun[0].ExitCode -ne 0){throw ('Project verification failed: '+$taskRun[1])}
  $taskData=Get-Content -LiteralPath $taskRun[1] -Raw | ConvertFrom-Json
  if(-not $taskData.frozen -or -not $taskData.original_unchanged -or -not $taskData.ui_rendered){throw ('Incomplete verification: '+$taskRun[1])}
  Write-Output ('Verified '+$taskRun[1])
 }
}
