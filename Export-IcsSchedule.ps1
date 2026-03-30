param(
    [string]$IcsPath = "",
    [string]$OutputPath = ""
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Get-DefaultIcsPath {
    param([string]$BaseDir)

    $utf8 = Join-Path $BaseDir "schedule.ics"
    $ansi = Join-Path $BaseDir "schedule_ansi.ics"

    if (Test-Path $utf8) { return $utf8 }
    if (Test-Path $ansi) { return $ansi }

    throw "No ICS file found. Checked: $ansi, $utf8"
}

function Get-GbkEncoding {
    try {
        return [System.Text.Encoding]::GetEncoding(936)
    }
    catch {
        [System.Text.Encoding]::RegisterProvider([System.Text.CodePagesEncodingProvider]::Instance)
        return [System.Text.Encoding]::GetEncoding(936)
    }
}

function Get-FileTextAutoEncoding {
    param([string]$Path)

    $bytes = [System.IO.File]::ReadAllBytes($Path)
    if ($bytes.Length -eq 0) { return "" }

    if ($bytes.Length -ge 3 -and $bytes[0] -eq 0xEF -and $bytes[1] -eq 0xBB -and $bytes[2] -eq 0xBF) {
        return [System.Text.Encoding]::UTF8.GetString($bytes, 3, $bytes.Length - 3)
    }
    if ($bytes.Length -ge 2 -and $bytes[0] -eq 0xFF -and $bytes[1] -eq 0xFE) {
        return [System.Text.Encoding]::Unicode.GetString($bytes, 2, $bytes.Length - 2)
    }
    if ($bytes.Length -ge 2 -and $bytes[0] -eq 0xFE -and $bytes[1] -eq 0xFF) {
        return [System.Text.Encoding]::BigEndianUnicode.GetString($bytes, 2, $bytes.Length - 2)
    }

    $gbk = Get-GbkEncoding

    $utf8Strict = New-Object System.Text.UTF8Encoding($false, $true)
    $utf8Valid = $true
    try {
        [void]$utf8Strict.GetString($bytes)
    }
    catch {
        $utf8Valid = $false
    }

    $utf8Text = [System.Text.Encoding]::UTF8.GetString($bytes)
    $gbkText = $gbk.GetString($bytes)

    if (-not $utf8Valid) {
        return $gbkText
    }

    if ($utf8Text -notmatch [char]0xFFFD) {
        return $utf8Text
    }

    $utf8Cjk = [regex]::Matches($utf8Text, '[\u4e00-\u9fff]').Count
    $gbkCjk = [regex]::Matches($gbkText, '[\u4e00-\u9fff]').Count

    if ($gbkCjk -gt $utf8Cjk) {
        return $gbkText
    }

    return $utf8Text
}

function Unfold-IcsLines {
    param([string]$Text)

    $rawLines = $Text -split "`r?`n"
    $lines = New-Object System.Collections.Generic.List[string]

    foreach ($line in $rawLines) {
        if ($line -match '^[ \t]' -and $lines.Count -gt 0) {
            $lines[$lines.Count - 1] = $lines[$lines.Count - 1] + $line.Substring(1)
        }
        else {
            $lines.Add($line)
        }
    }

    return $lines
}

function Unescape-IcsText {
    param([string]$Value)

    if ($null -eq $Value) { return "" }

    $s = $Value
    $s = $s -replace '\\n', ' '
    $s = $s -replace '\\N', ' '
    $s = $s -replace '\\,', ','
    $s = $s -replace '\\;', ';'
    $s = $s -replace '\\\\', '\\'

    return $s.Trim()
}

function Parse-IcsDateTime {
    param([string]$Raw)

    if ([string]::IsNullOrWhiteSpace($Raw)) { return $null }

    $clean = $Raw.Trim() -replace 'Z$', ''
    if ($clean -notmatch '^(\d{8})T?(\d{0,6})$') {
        return $null
    }

    $datePart = $Matches[1]
    $timePart = $Matches[2]

    $year = [int]$datePart.Substring(0, 4)
    $month = [int]$datePart.Substring(4, 2)
    $day = [int]$datePart.Substring(6, 2)

    $hour = 0
    $minute = 0
    $second = 0

    if ($timePart.Length -ge 4) {
        $hour = [int]$timePart.Substring(0, 2)
        $minute = [int]$timePart.Substring(2, 2)
        if ($timePart.Length -ge 6) {
            $second = [int]$timePart.Substring(4, 2)
        }
    }

    return [datetime]::new($year, $month, $day, $hour, $minute, $second)
}

function Get-OccurrenceDateTimes {
    param(
        [datetime]$Start,
        [string]$Rrule
    )

    $dates = New-Object System.Collections.Generic.List[datetime]

    if ([string]::IsNullOrWhiteSpace($Rrule)) {
        $dates.Add($Start)
        return $dates
    }

    $interval = 1
    if ($Rrule -match 'INTERVAL=(\d+)') {
        $interval = [Math]::Max(1, [int]$Matches[1])
    }

    $until = $null
    if ($Rrule -match 'UNTIL=([0-9TZ]+)') {
        $until = Parse-IcsDateTime $Matches[1]
    }

    if ($null -eq $until) {
        $dates.Add($Start)
        return $dates
    }

    if ($until -lt $Start) {
        $dates.Add($Start)
        return $dates
    }

    $step = [timespan]::FromDays(7 * $interval)
    $cursor = $Start

    while ($cursor -le $until) {
        $dates.Add($cursor)
        $cursor = $cursor + $step

        if ($dates.Count -gt 1000) {
            break
        }
    }

    if ($dates.Count -eq 0) {
        $dates.Add($Start)
    }

    return $dates
}

$baseDir = if ($PSScriptRoot) { $PSScriptRoot } else { (Get-Location).Path }

if ([string]::IsNullOrWhiteSpace($IcsPath)) {
    $IcsPath = Get-DefaultIcsPath -BaseDir $baseDir
}

if ([string]::IsNullOrWhiteSpace($OutputPath)) {
    $OutputPath = Join-Path $baseDir "schedule_summary.txt"
}

if (-not (Test-Path $IcsPath)) {
    throw "ICS file not found: $IcsPath"
}

$text = Get-FileTextAutoEncoding -Path $IcsPath
$lines = Unfold-IcsLines -Text $text

$events = New-Object System.Collections.Generic.List[hashtable]
$event = $null

foreach ($line in $lines) {
    if ($line -eq "BEGIN:VEVENT") {
        $event = @{}
        continue
    }

    if ($line -eq "END:VEVENT") {
        if ($null -ne $event) {
            $events.Add($event)
        }
        $event = $null
        continue
    }

    if ($null -eq $event) {
        continue
    }

    if ($line -match '^([A-Z]+)(?:;[^:]*)?:(.*)$') {
        $key = $Matches[1]
        $val = Unescape-IcsText $Matches[2]
        if ($key -in @("SUMMARY", "DTSTART", "DTEND", "RRULE")) {
            $event[$key] = $val
        }
    }
}

$weekdayMap = @{
    0 = "Sun"
    1 = "Mon"
    2 = "Tue"
    3 = "Wed"
    4 = "Thu"
    5 = "Fri"
    6 = "Sat"
}

$courses = @{}
$parsedEvents = 0

foreach ($ev in $events) {
    $name = ""
    if ($ev.ContainsKey("SUMMARY")) {
        $name = $ev["SUMMARY"].Trim()
    }

    if ([string]::IsNullOrWhiteSpace($name)) { continue }
    if (-not $ev.ContainsKey("DTSTART") -or -not $ev.ContainsKey("DTEND")) { continue }

    $start = Parse-IcsDateTime $ev["DTSTART"]
    $end = Parse-IcsDateTime $ev["DTEND"]
    if ($null -eq $start -or $null -eq $end) { continue }

    $parsedEvents++

    $singleHours = ($end - $start).TotalHours
    if ($singleHours -lt 0) { $singleHours = 0 }
    $durationMinutes = [int][Math]::Round(($end - $start).TotalMinutes)

    $rrule = if ($ev.ContainsKey("RRULE")) { $ev["RRULE"] } else { "" }
    $occurrences = @(Get-OccurrenceDateTimes -Start $start -Rrule $rrule)
    $sessions = $occurrences.Count

    $day = [int]$start.DayOfWeek
    $slot = "{0} {1:HH:mm}-{2:HH:mm}" -f $weekdayMap[$day], $start, $end

    $key = "$name|$slot"

    if (-not $courses.ContainsKey($key)) {
        $courses[$key] = [pscustomobject]@{
            Course = $name
            Time = $slot
            SingleHours = [Math]::Round($singleHours, 2)
            DurationMinutes = $durationMinutes
            Sessions = 0
            TotalHours = 0.0
            Occurrences = New-Object System.Collections.Generic.List[datetime]
        }
    }

    $courses[$key].Sessions += $sessions
    $courses[$key].TotalHours += ($singleHours * $sessions)
    $courses[$key].TotalHours = [Math]::Round($courses[$key].TotalHours, 2)

    foreach ($dt in $occurrences) {
        $courses[$key].Occurrences.Add($dt)
    }
}

$items = $courses.Values | Sort-Object Course, Time

$report = New-Object System.Collections.Generic.List[string]
$report.Add("Schedule summary")
$report.Add("Generated: " + (Get-Date -Format "yyyy-MM-dd HH:mm:ss"))
$report.Add("Source   : " + $IcsPath)
$report.Add("VEVENT   : " + $events.Count)
$report.Add("Parsed   : " + $parsedEvents)
$report.Add("Courses  : " + $items.Count)
$report.Add("")

if ($items.Count -eq 0) {
    $report.Add("No course rows were parsed.")
}
else {
    foreach ($it in $items) {
        $occSorted = $it.Occurrences | Sort-Object -Unique
        $it.Sessions = @($occSorted).Count
        $it.TotalHours = [Math]::Round($it.SingleHours * $it.Sessions, 2)

        $report.Add("Course      : " + $it.Course)
        $report.Add("Time        : " + $it.Time)
        $report.Add("SingleHours : " + $it.SingleHours)
        $report.Add("Sessions    : " + $it.Sessions)
        $report.Add("TotalHours  : " + $it.TotalHours)
        $report.Add("Dates       :")
        foreach ($dt in $occSorted) {
            $dtEnd = $dt.AddMinutes($it.DurationMinutes)
            $report.Add("  - " + ("{0:yyyy-MM-dd ddd HH:mm}-{1:HH:mm}" -f $dt, $dtEnd))
        }
        $report.Add("")
    }
}

$utf8NoBom = New-Object System.Text.UTF8Encoding($false)
[System.IO.File]::WriteAllText($OutputPath, ($report -join [Environment]::NewLine), $utf8NoBom)

$ansiPath = [System.IO.Path]::Combine(
    [System.IO.Path]::GetDirectoryName($OutputPath),
    [System.IO.Path]::GetFileNameWithoutExtension($OutputPath) + "_ansi" + [System.IO.Path]::GetExtension($OutputPath)
)
$ansiEncoding = Get-GbkEncoding
[System.IO.File]::WriteAllText($ansiPath, ($report -join [Environment]::NewLine), $ansiEncoding)

Write-Host "Done. Output written to: $OutputPath"
Write-Host "ANSI copy written to: $ansiPath"
