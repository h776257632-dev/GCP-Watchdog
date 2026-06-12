from functools import wraps
from flask import Flask, jsonify, render_template, request, Response
from config import settings
from monitor import collect_status
import storage

app = Flask(__name__)

# Initialize database at startup (runs under both Gunicorn and development server)
storage.init_db()

def require_auth(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        auth = request.authorization
        if not auth or auth.password != settings.web_password:
            return Response(
                "Authentication required",
                401,
                {"WWW-Authenticate": 'Basic realm="GCP Watchdog"'}
            )
        return fn(*args, **kwargs)
    return wrapper

@app.route("/")
@require_auth
def index():
    return render_template("index.html")

@app.route("/api/status")
@require_auth
def api_status():
    return jsonify(collect_status())

@app.route("/api/history")
@require_auth
def api_history():
    limit = int(request.args.get("limit", "288"))
    return jsonify(storage.recent_metrics(limit))

@app.route("/api/alerts")
@require_auth
def api_alerts():
    limit = int(request.args.get("limit", "50"))
    return jsonify(storage.recent_alerts(limit))

@app.route("/api/settings", methods=["GET"])
@require_auth
def get_web_settings():
    auth_val = settings.qq_mail_auth
    masked_auth = "******" if auth_val else ""
    return jsonify({
        "smtp_host": settings.smtp_host,
        "smtp_port": settings.smtp_port,
        "smtp_user": settings.qq_mail_user,
        "smtp_auth": masked_auth,
        "smtp_to": settings.qq_mail_to,
        "smtp_ssl": settings.smtp_ssl,
        "traffic_warn_mb": settings.traffic_warn_mb,
        "traffic_critical_mb": settings.traffic_critical_mb,
        "traffic_shutdown_mb": settings.traffic_shutdown_mb,
        "auto_shutdown": settings.auto_shutdown,
        "alert_cooldown_seconds": settings.alert_cooldown_seconds,
        "daily_mail_limit": settings.daily_mail_limit,
        "mem_warn_pct": settings.mem_warn_pct,
        "disk_warn_pct": settings.disk_warn_pct
    })

@app.route("/api/settings", methods=["POST"])
@require_auth
def post_web_settings():
    data = request.json or {}
    fields = [
        "smtp_host", "smtp_port", "smtp_user", "smtp_to", "smtp_ssl",
        "traffic_warn_mb", "traffic_critical_mb", "traffic_shutdown_mb",
        "auto_shutdown", "alert_cooldown_seconds", "daily_mail_limit",
        "mem_warn_pct", "disk_warn_pct"
    ]
    for field in fields:
        if field in data:
            storage.set_state(field, str(data[field]))
            
    if "smtp_auth" in data:
        auth_val = data["smtp_auth"]
        if auth_val != "******":
            storage.set_state("smtp_auth", auth_val)
            
    return jsonify({"ok": True, "message": "Settings saved successfully"})

@app.route("/api/settings/test", methods=["POST"])
@require_auth
def test_mail_api():
    from mailer import send_mail
    try:
        send_mail("GCP Watchdog 发信测试", "如果你收到这封邮件，说明后台 SMTP 配置及发信功能运行正常。")
        return jsonify({"ok": True, "message": "Test mail sent successfully!"})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500

if __name__ == "__main__":
    app.run(host=settings.web_host, port=settings.web_port)
