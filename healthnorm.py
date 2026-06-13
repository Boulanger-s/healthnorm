#!/usr/bin/env python3
import json, os, socket, subprocess, sys, time
from http.server import BaseHTTPRequestHandler, HTTPServer
 
MENU = [
    ("name",         "Hostname",                               True),
    ("ip",           "IP address",                            True),
    ("service",      "Detected services",                     True),
    ("uptime",       "System uptime",                         True),
    ("status",       "Computed status (ok/degraded/critical)", True),
    ("cpu_percent",  "CPU usage %",                           True),
    ("load_avg",     "Load average 1/5/15m",                  True),
    ("mem_percent",  "Memory usage %",                        True),
    ("swap_percent", "Swap usage %",                          False),
    ("disk_percent", "Disk usage % (/)",                      True),
    ("disk_iops",    "Disk IOPS (read/write)",                False),
    ("net_bytes",    "Network RX/TX (bytes/sec)",             False),
    ("net_conns",    "Open TCP connections",                  False),
    ("net_errors",   "Network errors/drops",                  False),
    ("cpu_temp",     "CPU temperature (°C)",                  False),
    ("kernel",       "Kernel version",                        False),
    ("timestamp",    "Timestamp (ISO 8601)",                  True),
    ("errors",       "Errors list",                           True),
]
 
enabled = {key: default for key, _, default in MENU}
 
def run_menu():
    cur = 0
    subprocess.run(["stty", "raw", "-echo"], check=True)
    try:
        while True:
            sys.stdout.write("\033[H\033[2J")
            sys.stdout.write("  healthnorm — configure metrics\r\n\r\n")
            sys.stdout.write("  \033[2m↑↓ navigate   enter/space toggle   q start\033[0m\r\n\r\n")
            for i, (key, label, _) in enumerate(MENU):
                mark  = "*" if enabled[key] else " "
                arrow = "\033[1m→\033[0m" if i == cur else " "
                sys.stdout.write(f"  {arrow}  ({mark}) {label}\r\n")
            sys.stdout.flush()
 
            ch = os.read(sys.stdin.fileno(), 3)
 
            if ch == b'\x1b[A':                      cur = max(0, cur - 1)
            elif ch == b'\x1b[B':                    cur = min(len(MENU) - 1, cur + 1)
            elif ch[0:1] == b'k':                    cur = max(0, cur - 1)
            elif ch[0:1] == b'j':                    cur = min(len(MENU) - 1, cur + 1)
            elif ch[0:1] in (b'\r', b'\n', b' '):   enabled[MENU[cur][0]] = not enabled[MENU[cur][0]]
            elif ch[0:1] in (b'q', b'Q'):            break
    finally:
        subprocess.run(["stty", "sane"], check=True)
 
# ── metrics ───────────────────────────────────────────────────────────────────
 
KNOWN_PORTS = {
    "80":"Nginx","443":"HTTPS","3000":"Grafana","3306":"MySQL","5432":"Postgres",
    "6379":"Redis","8080":"HTTP-alt","9200":"Elasticsearch","27017":"MongoDB","5672":"RabbitMQ",
}
 
def local_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80)); ip = s.getsockname()[0]; s.close(); return ip
    except Exception: return "unknown"
 
def detect_services():
    seen, out = set(), []
    for port, name in KNOWN_PORTS.items():
        try:
            s = socket.create_connection(("127.0.0.1", int(port)), timeout=0.25)
            s.close(); seen.add(name); out.append(name)
        except OSError: pass
    try:
        raw = subprocess.check_output(["ss", "-tlnp"], stderr=subprocess.DEVNULL, text=True)
        for line in raw.splitlines():
            if 'users:(("' in line:
                name = line.split('users:(("')[1].split('"')[0]
                if name not in seen: seen.add(name); out.append(name)
    except Exception: pass
    return out
 
def rf(path, default=None):
    try: return [float(x) for x in open(path).read().split()]
    except Exception: return default if default is not None else []
 
def cpu_percent():
    s1 = rf("/proc/stat"); time.sleep(0.2); s2 = rf("/proc/stat")
    if len(s1) < 8 or len(s2) < 8: return -1
    idle1, total1 = s1[4], sum(s1[1:8])
    idle2, total2 = s2[4], sum(s2[1:8])
    return round((1 - (idle2 - idle1) / (total2 - total1)) * 100, 2)
 
def meminfo():
    m = {}
    for line in open("/proc/meminfo"):
        p = line.split(); m[p[0].rstrip(":")] = float(p[1])
    return m
 
def mem_percent():
    try:
        m = meminfo(); free = m["MemFree"] + m.get("Buffers",0) + m.get("Cached",0) + m.get("SReclaimable",0)
        return round((1 - free / m["MemTotal"]) * 100, 2)
    except Exception: return -1
 
def swap_percent():
    try:
        m = meminfo()
        if m.get("SwapTotal", 0) == 0: return 0
        return round((1 - m["SwapFree"] / m["SwapTotal"]) * 100, 2)
    except Exception: return -1
 
def disk_percent():
    try:
        st = os.statvfs("/"); return round((1 - st.f_bavail / st.f_blocks) * 100, 2)
    except Exception: return -1
 
def disk_iops():
    try:
        def rd(): return [float(x) for x in open("/proc/diskstats").readline().split()]
        s1 = rd(); time.sleep(0.2); s2 = rd()
        return {"read": round((s2[3]-s1[3])/0.2, 1), "write": round((s2[7]-s1[7])/0.2, 1)}
    except Exception: return {"read": -1, "write": -1}
 
def net_bytes():
    try:
        def rx_tx():
            rx = tx = 0
            for line in open("/proc/net/dev"):
                f = line.split()
                if len(f) > 9 and ":" in f[0] and "lo" not in f[0]:
                    rx += float(f[1]); tx += float(f[9])
            return rx, tx
        r1, t1 = rx_tx(); time.sleep(0.2); r2, t2 = rx_tx()
        return {"rx": round((r2-r1)/0.2), "tx": round((t2-t1)/0.2)}
    except Exception: return {"rx": -1, "tx": -1}
 
def net_conns():
    try:
        out = subprocess.check_output(["ss","-tn","state","established"], stderr=subprocess.DEVNULL, text=True)
        return max(0, len(out.strip().splitlines()) - 1)
    except Exception: return -1
 
def net_errors():
    try:
        rx = tx = 0
        for line in open("/proc/net/dev"):
            f = line.split()
            if len(f) > 11 and ":" in f[0] and "lo" not in f[0]:
                rx += float(f[3]); tx += float(f[11])
        return {"rx": rx, "tx": tx}
    except Exception: return {"rx": -1, "tx": -1}
 
def cpu_temp():
    try:
        for d in os.listdir("/sys/class/thermal"):
            if d.startswith("thermal_zone"):
                t = float(open(f"/sys/class/thermal/{d}/temp").read().strip())
                if t > 0: return round(t / 1000, 1)
    except Exception: pass
    return -1
 
def calc_status(cpu, mem, disk):
    if cpu > 90 or mem > 95 or disk > 95: return "critical"
    if cpu > 70 or mem > 80 or disk > 85: return "degraded"
    return "ok"
 
# ── HTTP handler ──────────────────────────────────────────────────────────────
 
class Handler(BaseHTTPRequestHandler):
    def log_message(self, *_): pass
    def do_GET(self):
        if self.path != "/health":
            self.send_response(404); self.end_headers(); return
        errs = []
        needs_cpu = enabled["status"] or enabled["cpu_percent"]
        cpu = cpu_percent() if needs_cpu else 0
        mem, disk = mem_percent(), disk_percent()
        if needs_cpu and cpu == -1:  errs.append("cpu_percent: /proc/stat unavailable")
        if mem == -1:  errs.append("mem_percent: /proc/meminfo unavailable")
        if disk == -1: errs.append("disk_percent: statvfs failed")
        h = {}
        if enabled["name"]:         h["name"]            = socket.gethostname()
        if enabled["ip"]:           h["ip"]              = local_ip()
        if enabled["service"]:      h["service"]         = " / ".join(detect_services())
        if enabled["uptime"]:
            up = rf("/proc/uptime")
            if up: h["uptime"] = f"{int(up[0])}s"
            else:
                h["uptime"] = "unavailable"
                errs.append("uptime: /proc/uptime unavailable")
        if enabled["status"]:       h["status"]          = calc_status(cpu, mem, disk)
        if enabled["cpu_percent"]:  h["cpu_percent"]     = cpu
        if enabled["load_avg"]:
            la = rf("/proc/loadavg")
            if len(la) >= 3: h["load_avg"] = {"1m": la[0], "5m": la[1], "15m": la[2]}
            else: errs.append("load_avg: /proc/loadavg unavailable")
        if enabled["mem_percent"]:  h["mem_percent"]     = mem
        if enabled["swap_percent"]:
            sp = swap_percent()
            if sp == -1: errs.append("swap_percent: /proc/meminfo unavailable")
            h["swap_percent"] = sp
        if enabled["disk_percent"]: h["disk_percent"]    = disk
        if enabled["disk_iops"]:
            iops = disk_iops()
            if iops["read"] == -1: errs.append("disk_iops: /proc/diskstats unavailable")
            h["disk_iops"] = iops
        if enabled["net_bytes"]:
            nb = net_bytes()
            if nb["rx"] == -1: errs.append("net_bytes_sec: /proc/net/dev unavailable")
            h["net_bytes_sec"] = nb
        if enabled["net_conns"]:
            nc = net_conns()
            if nc == -1: errs.append("tcp_connections: 'ss' command unavailable")
            h["tcp_connections"] = nc
        if enabled["net_errors"]:
            ne = net_errors()
            if ne["rx"] == -1: errs.append("net_errors: /proc/net/dev unavailable")
            h["net_errors"] = ne
        if enabled["cpu_temp"]:
            ct = cpu_temp()
            if ct == -1: errs.append("cpu_temp_c: /sys/class/thermal unavailable")
            h["cpu_temp_c"] = ct
        if enabled["kernel"]:
            try: h["kernel"] = open("/proc/sys/kernel/osrelease").read().strip()
            except Exception:
                h["kernel"] = "unavailable"
                errs.append("kernel: /proc/sys/kernel/osrelease unavailable")
        if enabled["timestamp"]:    h["timestamp"]       = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        if enabled["errors"]:       h["errors"]          = errs
        body = json.dumps(h, indent=2).encode()
        status = 503 if h.get("status") not in ("ok", None) else 200
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.end_headers(); self.wfile.write(body)
 
if __name__ == "__main__":
    if sys.stdin.isatty():
        run_menu()
        sys.stdout.write("\033[H\033[2J")
    else:
        print("healthnorm: no TTY detected, skipping interactive menu (using defaults)")
    args = sys.argv[1:]
    bind_all = "--bind-all" in args
    args = [a for a in args if a != "--bind-all"]
    port = int(args[0]) if args else 9090
    host = "" if bind_all else "127.0.0.1"
 
    active = [label for key, label, _ in MENU if enabled[key]]
    print(f"healthnorm sur {host or '0.0.0.0'}:{port}")
    if not bind_all:
        print("(écoute sur 127.0.0.1 uniquement — utilise --bind-all pour exposer sur toutes les interfaces,")
        print(" ou place healthnorm derrière un reverse proxy / une règle de firewall)")
    print(f"métriques actives : {', '.join(active)}\n")
    HTTPServer((host, port), Handler).serve_forever()
