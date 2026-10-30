$ErrorActionPreference='Stop'
$taskRoot=(Resolve-Path (Join-Path $PSScriptRoot '../..')).Path
$env:QT_QPA_PLATFORM='offscreen'
$taskExe=Join-Path $taskRoot 'outputs/StatCraft.exe'
$taskFixtures=@(
 @((Join-Path $taskRoot 'outputs/StatCraft-individual-interval-demo.mpx'),'work/individual-interval-packaged-verified.json'),
 @((Join-Path $taskRoot 'outputs/StatCraft-dotplot-variants-demo.mpx'),'work/dotplot-variants-packaged-verified.json'),
 @('C:/Users/funny/Downloads/quiz1.mpx','work/quiz1-packaged-verified.json'),
 @((Join-Path $taskRoot 'outputs/StatCraft-boxplot-variants-demo.mpx'),'work/boxplot-variants-packaged-verified.json'),
 @((Join-Path $taskRoot 'outputs/StatCraft-histogram-variants-demo.mpx'),'work/histogram-variants-packaged-verified.json')
)
$taskRuns=@()
foreach($taskFixture in $taskFixtures){
 $taskReport=Join-Path $taskRoot $taskFixture[1]
 $taskArgs=@('--verify-project',('"'+$taskFixture[0]+'"'),('"'+$taskReport+'"'))
 $taskChild=Start-Process -FilePath $taskExe -ArgumentList $taskArgs -WindowStyle Hidden -PassThru
 $taskRuns+=,@($taskChild,$taskReport)
}
foreach($taskRun in $taskRuns){
 $taskRun[0].WaitForExit()
 if($taskRun[0].ExitCode -ne 0){throw ('Project verification failed: '+$taskRun[1])}
 $taskData=Get-Content -LiteralPath $taskRun[1] -Raw | ConvertFrom-Json
 if(-not $taskData.frozen -or -not $taskData.original_unchanged -or -not $taskData.ui_rendered){throw ('Incomplete project verification: '+$taskRun[1])}
 Write-Output ('Verified '+$taskRun[1])
}
