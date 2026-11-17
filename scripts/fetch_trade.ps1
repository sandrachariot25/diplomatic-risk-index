param(
    [ValidatePattern('^20\d{2}-(0[1-9]|1[0-2])$')][string]$From = '2015-01',
    [ValidatePattern('^20\d{2}-(0[1-9]|1[0-2])$')][string]$Through = (Get-Date).AddMonths(-1).ToString('yyyy-MM'),
    [switch]$AggregatesOnly,
    [switch]$Refresh,
    [switch]$ProductsOnly,
    [switch]$JapanOnly,
    [switch]$KoreaOnly,
    [switch]$ConcentrationOnly
)
$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$dir = Join-Path $root 'data/raw/trade'
New-Item -ItemType Directory -Force $dir | Out-Null
$manifest = Join-Path $dir $(if ($JapanOnly) { 'downloads_japan.jsonl' } elseif ($KoreaOnly) { 'downloads_korea.jsonl' } elseif ($AggregatesOnly) { 'downloads_aggregate.jsonl' } else { 'downloads.jsonl' })

function Save-Official($name, $url, $accept, $expected, $publication = $null) {
    $target = Join-Path $dir $name
    if ((Test-Path -LiteralPath $target) -and -not $Refresh) { return }
    $response = Invoke-WebRequest -Uri $url -Headers @{Accept=$accept} -TimeoutSec 90 -SkipHttpErrorCheck
    if ($response.StatusCode -eq 429) {
        $delay = 30
        $retryHeader = @($response.Headers['Retry-After'])[0]
        if ($retryHeader -match '^\d+$') { $delay = [Math]::Max(30, [int]$retryHeader) }
        if ($delay -le 120) {
            Write-Host "Rate limited ($name); waiting $delay seconds before one retry"
            Start-Sleep -Seconds $delay
            $response = Invoke-WebRequest -Uri $url -Headers @{Accept=$accept} -TimeoutSec 90 -SkipHttpErrorCheck
        }
    }
    if ($response.StatusCode -ne 200) { throw "HTTP $($response.StatusCode) ($name), retry-after $($response.Headers['Retry-After'])" }
    $binary = $expected -eq '%PDF-'
    $content = if ($binary) { [Text.Encoding]::ASCII.GetString($response.Content,0,5) } elseif ($response.Content -is [array]) { [Text.Encoding]::UTF8.GetString($response.Content) } else { $response.Content }
    $content = $content.TrimStart([char]0xFEFF)
    if (-not $content.StartsWith($expected)) { throw "Unexpected response for $name" }
    if ($name -match '^comtrade_(\d{6}|suppliers_)') {
        $payload = $content | ConvertFrom-Json
        if ($payload.error -or $payload.count -ne $payload.data.Count -or $payload.count -ge 500) {
            throw "Invalid or potentially truncated response for $name"
        }
    }
    $staging = "$target.part"
    if ($binary) { [IO.File]::WriteAllBytes($staging,$response.Content) }
    else { [IO.File]::WriteAllText($staging, $content) }
    $checksum = (Get-FileHash -LiteralPath $staging -Algorithm SHA256).Hash.ToLowerInvariant()
    $archive = Join-Path $dir "$name.$checksum"
    if (-not (Test-Path -LiteralPath $archive)) { Copy-Item -LiteralPath $staging -Destination $archive }
    $record = @{file=$name; archive=(Split-Path -Leaf $archive); url=$url; sha256=$checksum; retrieved_at=[DateTimeOffset]::UtcNow.ToString('o'); publication_date=$publication}
    Add-Content -LiteralPath $manifest -Value ($record | ConvertTo-Json -Compress) -Encoding utf8
    Move-Item -LiteralPath $staging -Destination $target -Force
    Write-Host $name
}

if ($KoreaOnly) {
    $base = 'https://www.customs.go.kr/common/nttFileDownload.do?fileKey='
    Save-Official 'kcs_202608.pdf' (${base}+'e446d2640704314b037f91cc2700398b') 'application/pdf' '%PDF-' '2026-09-15'
    Save-Official 'kcs_202609.pdf' (${base}+'525c28fb98304bd4a171d639a41ed008') 'application/pdf' '%PDF-' '2026-10-15'
    return
}

if ($JapanOnly) {
    $lastYear = [int]$Through.Substring(0,4)
    for ($year = $lastYear; $year -ge [int]$From.Substring(0,4); $year--) {
        foreach ($flow in @('X','M')) {
            $name = "japan_${year}_$flow.csv"
            if ((Test-Path -LiteralPath (Join-Path $dir $name)) -and -not $Refresh) { continue }
            $category = if ($flow -eq 'X') { '000001013190' } else { '000001013191' }
            $index = "https://www.e-stat.go.jp/stat-search/files?cycle=1&data=1&layout=datalist&metadata=1&page=1&tclass1=000001013189&tclass2=$category&tclass3val=0&toukei=00350300&tstat=000001013141&year=${year}0"
            $page = (Invoke-WebRequest $index -TimeoutSec 30).Content
            $matchesFound = [regex]::Matches($page,'stat-search/file-download\?statInfId=\d+&(?:amp;)?fileKind=1')
            if ($matchesFound.Count -ne 1) { throw "Expected one annual national CSV at $index" }
            $date = [regex]::Match($page,'公開（更新）日[^<]*</span>\s*(\d{4}-\d\d-\d\d)').Groups[1].Value
            Save-Official $name ('https://www.e-stat.go.jp/'+$matchesFound[0].Value.Replace('&amp;','&')) 'text/csv' 'Exp or Imp,Year,Country' $date
            Start-Sleep -Seconds 1
        }
    }
    return
}

if ($ConcentrationOnly) {
    for ($year = [int]$Through.Substring(0,4)-1; $year -ge [int]$From.Substring(0,4); $year--) {
        foreach ($code in @('850760','854232','848620')) {
            $name = "comtrade_suppliers_${year}_$code.json"
            if ((Test-Path -LiteralPath (Join-Path $dir $name)) -and -not $Refresh) { continue }
            $url = "https://comtradeapi.un.org/public/v1/preview/C/A/HS?period=$year&reporterCode=392,410&flowCode=M&cmdCode=$code"
            Save-Official $name $url 'application/json' '{'
            Start-Sleep -Seconds 2
        }
    }
    return
}

if (-not $ProductsOnly) {
    $imf = 'https://api.imf.org/external/sdmx/3.0/data/dataflow/IMF.STA/IMTS/+/JPN+KOR.XG_FOB_USD+MG_CIF_USD.JPN+KOR+G001.M?c%5BTIME_PERIOD%5D=ge%3A2015-01'
    Save-Official 'imf_monthly.csv' $imf 'application/vnd.sdmx.data+csv;version=2.0.0' 'STRUCTURE'
    $oecd = 'https://sdmx.oecd.org/sti-public/rest/data/OECD.STI.PIE,DSD_BTIGE@DF_BTIGE,1.0'
    Save-Official 'oecd_industry.csv' "$oecd/A.JPN+KOR..TOTAL..JPN+KOR+W.USD?startPeriod=2015&format=csvfile" 'application/vnd.sdmx.data+csv;version=2.0.0' 'STRUCTURE'
    $products = 'CPA_2_1_C26+CPA_2_1_C20+CPA_2_1_C28+CPA_2_1_C29+CPA_2_1_C24+CPA_2_1_C301+CPA_2_1_C27+CPA_2_1_B06+CPA_2_1_C19+_T'
    Save-Official 'oecd_suppliers.csv' "$oecd/A.JPN+KOR.M.TOTAL.$products..USD?startPeriod=2015&format=csvfile" 'application/vnd.sdmx.data+csv;version=2.0.0' 'STRUCTURE'
    Save-Official 'comtrade_countries.json' 'https://comtradeapi.un.org/files/v1/app/reference/partnerAreas.json' 'application/json' '{'
}
if ($AggregatesOnly) { return }
$first = [datetime]::ParseExact($From, 'yyyy-MM', [Globalization.CultureInfo]::InvariantCulture)
$last = [datetime]::ParseExact($Through, 'yyyy-MM', [Globalization.CultureInfo]::InvariantCulture)
$codes = '854231,854232,850760,280920,870899,720839,890120,271111,848620'
for ($month = $last; $month -ge $first; $month = $month.AddMonths(-1)) {
    $period = $month.ToString('yyyyMM')
    $name = "comtrade_$period.json"
    if ((Test-Path -LiteralPath (Join-Path $dir $name)) -and -not $Refresh) { continue }
    $url = "https://comtradeapi.un.org/public/v1/preview/C/M/HS?period=$period&reporterCode=410,392&partnerCode=0,392,410&flowCode=M,X&cmdCode=$codes"
    Save-Official $name $url 'application/json' '{'
    Start-Sleep -Milliseconds 1800
}
