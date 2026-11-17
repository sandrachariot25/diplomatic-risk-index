"""Sequential HTTPS transport with robots checks and an auditable response store."""
import base64
import json
import shutil
import subprocess
import time
import urllib.error
import urllib.request
from urllib.parse import urlsplit, urljoin
from urllib.robotparser import RobotFileParser

USER_AGENT = 'DRI-Research-Audit/0.1 (small public-source feasibility audit)'
HOSTS = {'www.mofa.go.kr', 'www.mofa.go.jp'}
CAP = 4_000_000
HOST_LAST_REQUEST = {}

class AccessBlocked(RuntimeError):
    pass

class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None

def validate_url(url, hosts=None):
    p = urlsplit(url)
    if p.scheme != 'https' or p.netloc not in (hosts or HOSTS) or p.username or p.password:
        raise AccessBlocked('Only explicitly allowed official HTTPS hosts are accepted')
    return p

def urllib_get(url):
    opener = urllib.request.build_opener(NoRedirect())
    req = urllib.request.Request(url, headers={'User-Agent': USER_AGENT})
    try:
        response = opener.open(req, timeout=35)
    except urllib.error.HTTPError as error:
        response = error
    with response:
        body = response.read(CAP + 1)
        if len(body) > CAP:
            raise ValueError('Response exceeds size cap')
        return response.code, dict(response.headers), body

def windows_get(url, max_bytes=CAP):
    if not 1<=max_bytes<=16_000_000:raise ValueError('Transport cap must be 1..16000000 bytes')
    """Uses Windows trust chain validation; never disables TLS verification.

    URL is base64 passed as data, not interpolated shell syntax. HttpClient does
    not follow redirects; the Python policy checks each redirect separately.
    """
    executable = shutil.which('pwsh')
    if not executable:
        raise RuntimeError('PowerShell 7 (pwsh) required for Windows transport')
    encoded = base64.b64encode(url.encode()).decode()
    script = r'''
$ErrorActionPreference = 'Stop'
$u = [Text.Encoding]::UTF8.GetString([Convert]::FromBase64String('__URL__'))
$handler = [System.Net.Http.HttpClientHandler]::new()
$handler.AllowAutoRedirect = $false
$client = [System.Net.Http.HttpClient]::new($handler)
$client.Timeout = [TimeSpan]::FromSeconds(35)
$client.DefaultRequestHeaders.TryAddWithoutValidation('User-Agent', '__UA__') | Out-Null
try {
  $redirects = @()
  for ($hop = 0; $hop -lt 4; $hop++) {
    $response = $client.GetAsync($u, [System.Net.Http.HttpCompletionOption]::ResponseHeadersRead).GetAwaiter().GetResult()
    $status = [int]$response.StatusCode
    $location = [string]$response.Headers.Location
    if (($status -in @(301,302,303,307,308)) -and ($location -eq $u) -and ($hop -lt 3)) {
      $redirects += @{url=$u; status=$status; location=$location}
      $response.Dispose()
      Start-Sleep -Milliseconds 5500
      continue
    }
    break
  }
  $stream = $response.Content.ReadAsStream()
  $memory = [IO.MemoryStream]::new()
  $buffer = [byte[]]::new(8192)
  while (($n = $stream.Read($buffer, 0, $buffer.Length)) -gt 0) {
    $memory.Write($buffer, 0, $n)
    if ($memory.Length -gt __CAP__) { throw 'Response exceeds size cap' }
  }
  $headers = @{}
  foreach ($h in $response.Headers) { $headers[$h.Key] = ($h.Value -join ', ') }
  foreach ($h in $response.Content.Headers) { $headers[$h.Key] = ($h.Value -join ', ') }
  if ($redirects.Count -gt 0) { $headers['X-DRI-Same-URL-Redirects'] = ($redirects | ConvertTo-Json -Compress) }
  @{status=[int]$response.StatusCode; headers=$headers; body=[Convert]::ToBase64String($memory.ToArray())} | ConvertTo-Json -Compress -Depth 5
} finally { $client.Dispose(); $handler.Dispose() }
'''.replace('__URL__', encoded).replace('__UA__', USER_AGENT).replace('__CAP__',str(max_bytes))
    command = base64.b64encode(script.encode('utf-16-le')).decode()
    try:
        result = subprocess.run([executable, '-NoProfile', '-NonInteractive', '-EncodedCommand', command], capture_output=True, text=True, timeout=180)
    except subprocess.TimeoutExpired as error:
        raise OSError('Windows HTTPS transport timed out after 180 seconds: '+url) from error
    if result.returncode:
        raise OSError(result.stderr.strip())
    obj = json.loads(result.stdout.lstrip('\ufeff'))
    return obj['status'], obj['headers'], base64.b64decode(obj['body'])

class Client:
    def __init__(self, store, transport='urllib', interval=5.5, hosts=None, retain_body=True):
        if interval < 5.5:
            raise ValueError('Minimum local interval is 5.5 seconds')
        self.store = store
        self.transport = windows_get if transport == 'windows' else urllib_get
        self.interval = interval
        self.last = 0.0
        self.robots = {}
        self.blocked = set()
        self.hosts = set(hosts or HOSTS)
        self.retain_body = retain_body

    def request(self, url):
        validate_url(url, self.hosts)
        origin=urlsplit(url).netloc
        previous=max(self.last,HOST_LAST_REQUEST.get(origin,0))
        time.sleep(max(0, self.interval - (time.monotonic() - previous)))
        try:
            status, headers, body = self.transport(url)
        except Exception as error:
            self.store.record_fetch(url, None, {}, b'', f'{type(error).__name__}: {error}')
            raise
        finally:
            self.last = time.monotonic()
            HOST_LAST_REQUEST[origin]=self.last
        raw = self.store.record_fetch(url, status, headers, body, retain_body=self.retain_body or urlsplit(url).path == '/robots.txt')
        return status, {k.lower(): v for k, v in headers.items()}, body, raw

    def check_robots(self, url):
        p = validate_url(url, self.hosts)
        origin = f'{p.scheme}://{p.netloc}'
        if origin in self.blocked:
            raise AccessBlocked('Host stopped after denial or rate limit')
        if origin not in self.robots:
            status, headers, body, raw = self.request(origin + '/robots.txt')
            parser = RobotFileParser()
            if status in (404, 410):
                parser.parse([])
            elif status == 200:
                if b'<html' in body.lower():
                    self.blocked.add(origin)
                    raise AccessBlocked('robots.txt returned HTML; policy unknown')
                parser.parse(body.decode('utf-8-sig').splitlines())
            else:
                self.blocked.add(origin)
                raise AccessBlocked(f'robots.txt unavailable (HTTP {status}); collection stopped')
            self.robots[origin] = parser
        parser = self.robots[origin]
        if not parser.can_fetch(USER_AGENT, url):
            raise AccessBlocked('robots.txt disallows this URL')
        delay = parser.crawl_delay(USER_AGENT) or 0
        rate = parser.request_rate(USER_AGENT)
        self.interval = max(self.interval, delay, rate.seconds / rate.requests if rate else 0)

    def get(self, url, *, content_types=('html',)):
        for _ in range(4):
            self.check_robots(url)
            status, headers, body, raw = self.request(url)
            if status in {401, 403, 429}:
                self.blocked.add('https://' + urlsplit(url).netloc)
                raise AccessBlocked(f'HTTP {status}; no retry or bypass; Retry-After={headers.get("retry-after")}')
            if status in {301, 302, 303, 307, 308}:
                if not headers.get('location'):
                    raise ValueError('Redirect missing Location')
                url = urljoin(url, headers['location'])
                validate_url(url, self.hosts)
                continue
            if status != 200:
                raise OSError(f'HTTP {status}')
            if not any(kind in headers.get('content-type', '').lower() for kind in content_types):
                raise ValueError('Unexpected response content type')
            return body.decode('utf-8-sig'), raw, url
        raise AccessBlocked('Too many redirects')
