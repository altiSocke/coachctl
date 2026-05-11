description: Open the coachctl dashboard locally in the browser. Bakes fresh data, checks if the dev server is already running, starts it if not, then navigates the browser to the dashboard. Use when the athlete asks to see, open, or show the dashboard.
# Skill: show-dashboard

## What I do

Bake fresh dashboard data and open the coachctl dashboard in the browser.

---

## Steps

### 1 — Bake

Call the `bake` MCP tool to ensure `data.json` is up to date before opening.

### 2 — Check if already running

Use bash to probe port 8080 first, then 8000:

```powershell
try {
    Invoke-WebRequest -Uri "http://localhost:8080" -UseBasicParsing -TimeoutSec 2 | Select-Object -ExpandProperty StatusCode
} catch { "down" }
```

If the status code is 200, the dashboard is already running. Note the port and skip to step 4.

Try port 8000 if 8080 is down.

### 3 — Start if not running

Start the dashboard as a background job:

```powershell
$job = Start-Job -ScriptBlock { cd "C:\Users\tieschy\workspace\coachctl"; uv run coachctl web }
```

Poll until ready (max 10 seconds, check every 2 seconds):

```powershell
$port = 8080
$ready = $false
for ($i = 0; $i -lt 5; $i++) {
    Start-Sleep -Seconds 2
    try {
        $code = Invoke-WebRequest -Uri "http://localhost:$port" -UseBasicParsing -TimeoutSec 2 |
                Select-Object -ExpandProperty StatusCode
        if ($code -eq 200) { $ready = $true; break }
    } catch {}
}
```

If still not ready after 10 seconds, report the error and stop.

### 4 — Open in browser

Navigate to the correct port using `chrome-devtools_navigate_page`:

```
type: url
url: http://localhost:<port>
```