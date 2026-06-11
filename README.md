**HEALTHNORM**

Daemon de monitoring léger qui expose un endpoint `/health` standardisé pour n'importe quelle machine Linux.

Zéro dépendance. Python 3 stdlib uniquement.

**Démo :**

```bash
python3 healthnorm.py
```

Un menu interactif s'affiche pour choisir les métriques à exposer :

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

Appuyer sur `q` pour démarrer le serveur. Réponse :

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

**Installation :**

```bash
git clone https://github.com/Boulanger-s/healthnorm
cd healthnorm
chmod +x healthnorm.py
python3 healthnorm.py
```

Aucune dépendance à installer. Python 3.6+ suffit.

**Usage :**

```bash
python3 healthnorm.py            # port 9090 par défaut
python3 healthnorm.py 8080       # port custom
```

**Puis depuis n'importe où :**

```bash
curl http://TON_IP:9090/health
```

**Métriques disponibles :**

| Clé | Description | Source |
|-----|-------------|--------|
| `name` | Hostname de la machine | `socket.gethostname()` |
| `ip` | IP locale principale | UDP trick `8.8.8.8` |
| `service` | Services détectés (Redis, Nginx…) | TCP dial + `ss -tlnp` |
| `uptime` | Uptime système en secondes | `/proc/uptime` |
| `status` | `ok` / `degraded` / `critical` | Calculé selon seuils |
| `cpu_percent` | Usage CPU % | `/proc/stat` (delta 200ms) |
| `load_avg` | Load average 1/5/15m | `/proc/loadavg` |
| `mem_percent` | Usage mémoire % | `/proc/meminfo` |
| `swap_percent` | Usage swap % | `/proc/meminfo` |
| `disk_percent` | Usage disque % (/) | `os.statvfs` |
| `disk_iops` | IOPS lecture/écriture | `/proc/diskstats` (delta 200ms) |
| `net_bytes_sec` | Bande passante RX/TX (bytes/s) | `/proc/net/dev` (delta 200ms) |
| `tcp_connections` | Connexions TCP établies | `ss -tn state established` |
| `net_errors` | Erreurs/drops réseau | `/proc/net/dev` |
| `cpu_temp_c` | Température CPU en °C | `/sys/class/thermal/` |
| `kernel` | Version du kernel | `/proc/sys/kernel/osrelease` |
| `timestamp` | Horodatage ISO 8601 | `time.gmtime()` |
| `errors` | Liste d'erreurs | Interne |

**Seuils du status calculé :**

| Status | Condition |
|--------|-----------|
| `ok` | CPU < 70%, RAM < 80%, Disk < 85% |
| `degraded` | CPU > 70% ou RAM > 80% ou Disk > 85% |
| `critical` | CPU > 90% ou RAM > 95% ou Disk > 95% |

HTTP 503 automatique si `status != ok`.

Exposition via Nginx (optionnel)

**Pour lier à un sous-domaine :**

```nginx
server {
    listen 80;
    server_name health.tondomaine.com;

    location /health {
        proxy_pass http://127.0.0.1:9090/health;
    }
}
```

```bash
certbot --nginx -d health.tondomaine.com
```

**Lancer en service systemd :** (optionnel)

```bash
sudo cp healthnorm.py /opt/healthnorm/healthnorm.py
sudo cp healthnorm.service /etc/systemd/system/
sudo systemctl enable --now healthnorm
```

> Note : en mode service, le menu TUI est ignoré — les métriques par défaut sont utilisées.

**Compatibilité :**

| OS | Support |
|----|---------|
| Linux (Debian, Ubuntu, RHEL, Arch…) | ✅ Complet |
| Raspberry Pi OS | ✅ Complet |
| macOS | ⚠️ Partiel (`/proc` absent, métriques système désactivées) |
| Windows | ❌ Non supporté |
