# healthnorm

**A single-file, zero-dependency Python daemon that exposes a standardized `/health` JSON endpoint on any Linux box.**

No Prometheus, no node_exporter, no config files. Run one script, get an instant health check with CPU, memory, disk, uptime, detected services, and a computed `ok` / `degraded` / `critical` status — ready to plug into uptime monitors, load balancers, or your own dashboards.

```bash
git clone https://github.com/Boulanger-s/healthnorm
cd healthnorm
python3 healthnorm.py
```

---

## Why healthnorm?

- **Zero dependencies** — pure Python 3 stdlib, nothing to `pip install`
- **One file** — drop it on a server and run it
- **Standardized output** — same `/health` shape on every machine, so you can monitor a fleet consistently
- **Interactive setup** — a TUI lets you pick exactly which metrics to expose
- **Built-in status logic** — automatic `ok` / `degraded` / `critical` with HTTP 503 on problems
- **Works great on Raspberry Pi / homelab boxes** where installing a full monitoring stack is overkill

---

## Quick start

```bash
git clone https://github.com/Boulanger-s/healthnorm
cd healthnorm
chmod +x healthnorm.py
python3 healthnorm.py            # default port 9090
python3 healthnorm.py 8080       # custom port
```

An interactive menu lets you choose which metrics to expose:

```
  healthnorm — configure metrics

  ↑↓ navigate   enter/space toggle   q start

→  (*) Hostname
   (*) IP address
   (*) Detected services
   (*) System uptime
   (*) Computed status (ok/degraded/critical)
   (*) CPU usage %
   (*) Load average 1/5/15m
   (*) Memory usage %
   ( ) Swap usage %
   (*) Disk usage % (/)
   ( ) Disk IOPS (read/write)
   ( ) Network RX/TX (bytes/sec)
   ( ) Open TCP connections
   ( ) Network errors/drops
   ( ) CPU temperature (°C)
   ( ) Kernel version
   (*) Timestamp (ISO 8601)
   (*) Errors list
```

Press `q` to start the server. From anywhere:

```bash
curl http://YOUR_IP:9090/health
```

```json
{
  "name": "node-prod-04",
  "ip": "10.0.5.12",
  "service": "Redis / Grafana / Nginx",
  "uptime": "86412s",
  "status": "ok",
  "cpu_percent": 12.4,
  "load_avg": { "1m": 0.4, "5m": 0.3, "15m": 0.2 },
  "mem_percent": 61.3,
  "disk_percent": 43.0,
  "timestamp": "2026-06-05T10:22:01Z",
  "errors": []
}
```

No dependencies to install. Python 3.6+ is all you need.

---

## Available metrics

| Key | Description | Source |
| --- | --- | --- |
| `name` | Machine hostname | `socket.gethostname()` |
| `ip` | Primary local IP | UDP trick to `8.8.8.8` |
| `service` | Detected services (Redis, Nginx…) | TCP dial + `ss -tlnp` |
| `uptime` | System uptime in seconds | `/proc/uptime` |
| `status` | `ok` / `degraded` / `critical` | Computed from thresholds |
| `cpu_percent` | CPU usage % | `/proc/stat` (200ms delta) |
| `load_avg` | Load average 1/5/15m | `/proc/loadavg` |
| `mem_percent` | Memory usage % | `/proc/meminfo` |
| `swap_percent` | Swap usage % | `/proc/meminfo` |
| `disk_percent` | Disk usage % (`/`) | `os.statvfs` |
| `disk_iops` | Read/write IOPS | `/proc/diskstats` (200ms delta) |
| `net_bytes_sec` | RX/TX bandwidth (bytes/s) | `/proc/net/dev` (200ms delta) |
| `tcp_connections` | Established TCP connections | `ss -tn state established` |
| `net_errors` | Network errors/drops | `/proc/net/dev` |
| `cpu_temp_c` | CPU temperature (°C) | `/sys/class/thermal/` |
| `kernel` | Kernel version | `/proc/sys/kernel/osrelease` |
| `timestamp` | ISO 8601 timestamp | `time.gmtime()` |
| `errors` | List of errors | Internal |

### Status thresholds

| Status | Condition |
| --- | --- |
| `ok` | CPU < 70%, RAM < 80%, Disk < 85% |
| `degraded` | CPU > 70% or RAM > 80% or Disk > 85% |
| `critical` | CPU > 90% or RAM > 95% or Disk > 95% |

The endpoint automatically returns **HTTP 503** when `status != ok`, so you can wire it straight into load balancers and uptime checks.

---

## Deploying

### Behind Nginx (optional)

```nginx
server {
    listen 80;
    server_name health.yourdomain.com;

    location /health {
        proxy_pass http://127.0.0.1:9090/health;
    }
}
```

```bash
certbot --nginx -d health.yourdomain.com
```

### As a systemd service (optional)

```bash
sudo cp healthnorm.py /opt/healthnorm/healthnorm.py
sudo cp healthnorm.service /etc/systemd/system/
sudo systemctl enable --now healthnorm
```

> Note: in service mode, the TUI is skipped — default metrics are used.

---

## Compatibility

| OS | Support |
| --- | --- |
| Linux (Debian, Ubuntu, RHEL, Arch…) | ✅ Full |
| Raspberry Pi OS | ✅ Full |
| macOS | ⚠️ Partial (`/proc` unavailable, system metrics disabled) |
| Windows | ❌ Not supported |

---

## Contributing

Issues and PRs welcome — especially around new auto-detected services, additional metrics, and macOS/BSD support.

## License

MIT
