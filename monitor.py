import os
import time
import socket
import subprocess
import concurrent.futures
from urllib.parse import urlparse

import psutil
import requests

import storage
from config import settings
from mailer import send_mail

def default_iface() -> str:
    try:
        route = subprocess.check_output(["ip", "route"], text=True)
        for line in route.splitlines():
            parts = line.split()
            if parts and parts[0] == "default" and "dev" in parts:
                return parts[parts.index("dev") + 1]
    except Exception:
        pass
    stats = psutil.net_if_stats()
    for name, st in stats.items():
        if st.isup and name != "lo":
            return name
    return "eth0"

def read_net_bytes(iface: str) -> tuple[int, int]:
    try:
        counters = psutil.net_io_counters(pernic=True)
        if iface in counters:
            return counters[iface].bytes_sent, counters[iface].bytes_recv
    except Exception:
        pass
    try:
        base = f"/sys/class/net/{iface}/statistics"
        with open(os.path.join(base, "tx_bytes"), "r") as f:
            tx = int(f.read().strip())
        with open(os.path.join(base, "rx_bytes"), "r") as f:
            rx = int(f.read().strip())
        return tx, rx
    except Exception:
        pass
    return 0, 0

def update_monthly_traffic(iface: str, tx: int, rx: int) -> tuple[int, int, float, float]:
    now = int(time.time())
    month_key = time.strftime("%Y-%m")
    
    saved_month = storage.get_state("baseline_month")
    
    monthly_tx_bytes = int(storage.get_state("monthly_tx_bytes", "0"))
    monthly_rx_bytes = int(storage.get_state("monthly_rx_bytes", "0"))
    
    last_tx = storage.get_state("last_tx")
    last_rx = storage.get_state("last_rx")
    last_iface = storage.get_state("last_iface")
    last_ts = int(storage.get_state("last_ts", "0"))
    
    if saved_month != month_key:
        storage.set_state("baseline_month", month_key)
        monthly_tx_bytes = 0
        monthly_rx_bytes = 0
        storage.set_state("monthly_tx_bytes", "0")
        storage.set_state("monthly_rx_bytes", "0")
        storage.set_state("baseline_tx", str(tx))
        storage.set_state("baseline_rx", str(rx))
        last_tx = None
        last_rx = None
    
    delta_tx = 0
    delta_rx = 0
    
    if last_tx is not None and last_rx is not None and last_iface == iface:
        ltx = int(last_tx)
        lrx = int(last_rx)
        
        if tx < ltx:
            delta_tx = tx
        else:
            delta_tx = tx - ltx
            
        if rx < lrx:
            delta_rx = rx
        else:
            delta_rx = rx - lrx
    else:
        delta_tx = 0
        delta_rx = 0
        
    monthly_tx_bytes += delta_tx
    monthly_rx_bytes += delta_rx
    
    storage.set_state("monthly_tx_bytes", str(monthly_tx_bytes))
    storage.set_state("monthly_rx_bytes", str(monthly_rx_bytes))
    
    storage.set_state("last_tx", str(tx))
    storage.set_state("last_rx", str(rx))
    storage.set_state("last_iface", iface)
    storage.set_state("last_ts", str(now))
    
    dt = max(now - last_ts, 1) if last_ts > 0 else 1
    tx_speed_kbps = max(delta_tx, 0) / dt / 1024
    rx_speed_kbps = max(delta_rx, 0) / dt / 1024
    
    return monthly_tx_bytes, monthly_rx_bytes, tx_speed_kbps, rx_speed_kbps

def check_url(url: str) -> dict:
    start = time.time()
    try:
        resp = requests.get(url, timeout=8, verify=True, allow_redirects=True)
        elapsed = time.time() - start
        ok = 200 <= resp.status_code < 500
        return {"target": url, "ok": ok, "status": resp.status_code, "elapsed": elapsed, "error": ""}
    except Exception as e:
        return {"target": url, "ok": False, "status": None, "elapsed": None, "error": str(e)}

def check_tcp(target: str) -> dict:
    try:
        host, port_s = target.rsplit(":", 1)
        port = int(port_s)
        start = time.time()
        with socket.create_connection((host, port), timeout=5):
            elapsed = time.time() - start
        return {"target": target, "ok": True, "elapsed": elapsed, "error": ""}
    except Exception as e:
        return {"target": target, "ok": False, "elapsed": None, "error": str(e)}

def concurrent_check_urls(urls: list[str]) -> list[dict]:
    if not urls:
        return []
    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
        results = list(executor.map(check_url, urls))
    return results

def concurrent_check_tcp(targets: list[str]) -> list[dict]:
    if not targets:
        return []
    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
        results = list(executor.map(check_tcp, targets))
    return results

def collect_status() -> dict:
    iface = default_iface()
    tx, rx = read_net_bytes(iface)
    
    monthly_tx_bytes, monthly_rx_bytes, tx_speed_kbps, rx_speed_kbps = update_monthly_traffic(iface, tx, rx)

    vm = psutil.virtual_memory()
    disk = psutil.disk_usage("/")
    try:
        load1 = os.getloadavg()[0]
    except Exception:
        load1 = 0.0

    boot = psutil.boot_time()
    uptime_seconds = int(time.time() - boot)

    url_checks = concurrent_check_urls(settings.check_urls)
    tcp_checks = concurrent_check_tcp(settings.check_tcp)

    data = {
        "ts": int(time.time()),
        "iface": iface,
        "tx_bytes": tx,
        "rx_bytes": rx,
        "tx_used_mb": round(monthly_tx_bytes / 1024 / 1024, 3),
        "rx_used_mb": round(monthly_rx_bytes / 1024 / 1024, 3),
        "tx_speed_kbps": round(tx_speed_kbps, 3),
        "rx_speed_kbps": round(rx_speed_kbps, 3),
        "cpu_percent": psutil.cpu_percent(interval=0.3),
        "mem_percent": vm.percent,
        "disk_percent": disk.percent,
        "load1": load1,
        "uptime_seconds": uptime_seconds,
        "url_checks": url_checks,
        "tcp_checks": tcp_checks,
        "thresholds": {
            "warn": settings.traffic_warn_mb,
            "critical": settings.traffic_critical_mb,
            "shutdown": settings.traffic_shutdown_mb,
        },
        "auto_shutdown": settings.auto_shutdown,
    }
    return data

def alert_allowed(alert_type: str) -> bool:
    if storage.count_mails_today() >= settings.daily_mail_limit:
        return False
    key = f"last_alert_{alert_type}"
    last = int(storage.get_state(key, "0"))
    now = int(time.time())
    if now - last < settings.alert_cooldown_seconds:
        return False
    storage.set_state(key, str(now))
    return True

def send_alert(level: str, alert_type: str, title: str, message: str):
    sent = False
    if alert_allowed(alert_type):
        try:
            send_mail(title, message)
            sent = True
        except Exception as e:
            print(f"Failed to send email alert for {alert_type}: {e}")
    storage.insert_alert(level, alert_type, title, message, sent=sent)

def evaluate_and_alert(data: dict):
    tx = float(data["tx_used_mb"])

    base_msg = (
        f"时间: {time.strftime('%Y-%m-%d %H:%M:%S')}\n"
        f"网卡: {data['iface']}\n"
        f"本月发送: {data['tx_used_mb']} MB\n"
        f"本月接收: {data['rx_used_mb']} MB\n"
        f"当前上传速度: {data['tx_speed_kbps']} KB/s\n"
        f"CPU: {data['cpu_percent']}%\n"
        f"内存: {data['mem_percent']}%\n"
        f"磁盘: {data['disk_percent']}%\n"
        f"负载: {data['load1']}\n"
    )

    if tx >= settings.traffic_shutdown_mb:
        send_alert("danger", "traffic_shutdown", "GCP Watchdog：出站流量达到关机阈值", base_msg)
        if settings.auto_shutdown:
            time.sleep(5)
            try:
                subprocess.Popen(["/sbin/shutdown", "-h", "now", "GCP Watchdog traffic limit exceeded"])
            except Exception:
                try:
                    subprocess.Popen(["shutdown", "-h", "now", "GCP Watchdog traffic limit exceeded"])
                except Exception:
                    try:
                        subprocess.Popen(["systemctl", "poweroff"])
                    except Exception as e:
                        print(f"Failed to initiate shutdown: {e}")
    elif tx >= settings.traffic_critical_mb:
        send_alert("critical", "traffic_critical", "GCP Watchdog：出站流量严重警告", base_msg)
    elif tx >= settings.traffic_warn_mb:
        send_alert("warning", "traffic_warn", "GCP Watchdog：出站流量提醒", base_msg)

    if data["mem_percent"] >= settings.mem_warn_pct:
        send_alert("warning", "mem_high", "GCP Watchdog：内存使用率过高", base_msg)

    if data["disk_percent"] >= settings.disk_warn_pct:
        send_alert("warning", "disk_high", "GCP Watchdog：磁盘使用率过高", base_msg)

    for item in data.get("url_checks", []):
        target = item["target"]
        alert_key = "url_down_" + target
        last_state_key = "state_url_" + target
        
        prev_state = storage.get_state(last_state_key, "ok")
        
        if not item["ok"]:
            storage.set_state(last_state_key, "down")
            send_alert("warning", alert_key, "GCP Watchdog：URL 检测失败", 
                       base_msg + f"\nURL: {target}\n错误: {item['error']}\n状态: {item['status']}\n")
        else:
            storage.set_state(last_state_key, "ok")
            if prev_state == "down":
                send_alert("info", "url_up_" + target, "GCP Watchdog：URL 检测已恢复", 
                           base_msg + f"\nURL: {target} 已经恢复正常。\n")

    for item in data.get("tcp_checks", []):
        target = item["target"]
        alert_key = "tcp_down_" + target
        last_state_key = "state_tcp_" + target
        
        prev_state = storage.get_state(last_state_key, "ok")
        
        if not item["ok"]:
            storage.set_state(last_state_key, "down")
            send_alert("warning", alert_key, "GCP Watchdog：TCP 检测失败", 
                       base_msg + f"\nTCP: {target}\n错误: {item['error']}\n")
        else:
            storage.set_state(last_state_key, "ok")
            if prev_state == "down":
                send_alert("info", "tcp_up_" + target, "GCP Watchdog：TCP 检测已恢复", 
                           base_msg + f"\nTCP: {target} 已经恢复正常。\n")

def run_once() -> dict:
    storage.init_db()
    data = collect_status()
    storage.insert_metric(data)
    evaluate_and_alert(data)
    storage.cleanup_old(30)
    return data
