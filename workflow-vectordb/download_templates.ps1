$outDir = Join-Path $PSScriptRoot "repos\n8n-templates"
New-Item -ItemType Directory -Force -Path $outDir | Out-Null

# --- Step 1: Collect template IDs (or load from checkpoint) ---
$idFile = "$outDir\_template_ids.txt"

if ([System.IO.File]::Exists($idFile)) {
    Write-Host "=== Loading cached template IDs ===" -ForegroundColor Cyan
    $allIds = [System.Collections.ArrayList]::new()
    foreach ($line in [System.IO.File]::ReadAllLines($idFile)) {
        if ($line.Trim()) { [void]$allIds.Add([int]$line.Trim()) }
    }
    Write-Host "Loaded $($allIds.Count) IDs from checkpoint" -ForegroundColor Green
} else {
    Write-Host "=== Collecting template IDs from API ===" -ForegroundColor Cyan
    $allIds = [System.Collections.ArrayList]::new()
    $seen = [System.Collections.Generic.HashSet[int]]::new()
    $batchSize = 100
    $page = 1
    $total = 0

    do {
        $url = "https://api.n8n.io/api/templates/search?rows=$batchSize&page=$page"
        $r = Invoke-RestMethod $url
        $total = $r.totalWorkflows
        $added = 0
        foreach ($wf in $r.workflows) {
            if ($seen.Add($wf.id)) {
                [void]$allIds.Add($wf.id)
                $added++
            }
        }
        if ($added -eq 0 -and $page -gt 1) { break }
        $page++
        Write-Host "`r  Collecting IDs: $($allIds.Count) / $total (page $($page - 1))" -NoNewline
        Start-Sleep -Milliseconds 500
    } while ($allIds.Count -lt $total)

    Write-Host ""
    Write-Host "Collected $($allIds.Count) template IDs" -ForegroundColor Green
}

# Save checkpoint
[System.IO.File]::WriteAllLines($idFile, [string[]]$allIds.ToArray())

# --- Step 2: Download each workflow ---
Write-Host "`n=== Downloading full workflows ===" -ForegroundColor Cyan
$success = 0
$skipped = 0
$failed = [System.Collections.ArrayList]::new()
$startTime = Get-Date

for ($i = 0; $i -lt $allIds.Count; $i++) {
    $id = $allIds[$i]
    $outFile = "$outDir\$id.json"

    if ([System.IO.File]::Exists($outFile)) {
        $skipped++
        continue
    }

    $downloaded = $false
    for ($attempt = 1; $attempt -le 3; $attempt++) {
        try {
            $resp = Invoke-WebRequest "https://api.n8n.io/api/templates/workflows/$id" -UseBasicParsing
            [System.IO.File]::WriteAllText($outFile, $resp.Content, [System.Text.Encoding]::UTF8)
            $success++
            $downloaded = $true
            break
        } catch {
            $code = 0
            try { $code = $_.Exception.Response.StatusCode.value__ } catch {}
            if ($code -eq 404 -or $code -eq 410) {
                [void]$failed.Add($id)
                break
            }
            if ($attempt -lt 3) {
                Start-Sleep -Seconds ($attempt * 3)
            } else {
                [void]$failed.Add($id)
            }
        }
    }

    # Progress
    $elapsed = (Get-Date) - $startTime
    $totalDone = $success + $failed.Count
    $rate = if ($elapsed.TotalSeconds -gt 3) { [math]::Round($totalDone / $elapsed.TotalMinutes, 1) } else { 0 }
    $remaining = $allIds.Count - $i - 1
    $eta = if ($rate -gt 0) { "$([math]::Round($remaining / $rate, 0))m" } else { "..." }
    $pct = [math]::Round(($i + 1) / $allIds.Count * 100, 1)
    Write-Host "`r  [$($i+1)/$($allIds.Count)] ${pct}% | OK:$success SKIP:$skipped FAIL:$($failed.Count) | ${rate}/min | ETA:$eta   " -NoNewline

    Start-Sleep -Milliseconds 500
    if (($success + $failed.Count) % 200 -eq 0 -and $downloaded) {
        Write-Host ""
        Write-Host "  Cooldown 3s..." -ForegroundColor DarkGray
        Start-Sleep -Seconds 3
    }
}

Write-Host "`n"

# --- Summary ---
$actualFiles = [System.IO.Directory]::GetFiles($outDir, "*.json").Count
$totalBytes = 0
foreach ($f in [System.IO.Directory]::GetFiles($outDir, "*.json")) {
    $totalBytes += ([System.IO.FileInfo]::new($f)).Length
}
$sizeMB = [math]::Round($totalBytes / 1MB, 1)

Write-Host "=== Done ===" -ForegroundColor Green
Write-Host "Downloaded: $success"
Write-Host "Skipped: $skipped"
Write-Host "Failed: $($failed.Count)"
Write-Host "Files on disk: $actualFiles"
Write-Host "Total size: ${sizeMB} MB"

if ($failed.Count -gt 0) {
    $failedFile = "$outDir\_failed_ids.txt"
    [System.IO.File]::WriteAllLines($failedFile, $failed.ToArray())
    Write-Host "Failed IDs: $failedFile"
}
