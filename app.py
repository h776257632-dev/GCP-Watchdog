from functools import wraps
from flask import Flask, jsonify, render_template, request, Response, session, redirect, url_for

from config import settings
from monitor import collect_status
import storage

app = Flask(__name__)

# Initialize database at startup (runs under both Gunicorn and development server)
storage.init_db()
app.secret_key = settings.secret_key

def login_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        # Force setup if no administrator exists in the database
        if not storage.has_admin():
            if request.path.startswith('/api/'):
                return jsonify({"ok": False, "error": "Setup required", "redirect": "/setup"}), 401
            return redirect(url_for('setup'))
        
        # Verify login session
        if not session.get('logged_in'):
            if request.path.startswith('/api/'):
                return jsonify({"ok": False, "error": "Login required", "redirect": "/login"}), 401
            return redirect(url_for('login'))
        return fn(*args, **kwargs)
    return wrapper

@app.route("/")
@login_required
def index():
    return render_template("index.html")

@app.route("/setup", methods=["GET", "POST"])
def setup():
    if storage.has_admin():
        return redirect(url_for('login'))
    
    if request.method == "POST":
        data = request.json or {}
        username = data.get("username", "").strip()
        password = data.get("password", "")
        
        if not username or not password:
            return jsonify({"ok": False, "error": "用户名和密码不能为空"})
            
        if len(password) < 6:
            return jsonify({"ok": False, "error": "密码长度不能小于 6 位"})
            
        success = storage.create_admin(username, password)
        if success:
            session['logged_in'] = True
            session['username'] = username
            return jsonify({"ok": True, "message": "管理员账号创建成功！"})
        else:
            return jsonify({"ok": False, "error": "创建管理员失败，用户名已被占用"})
            
    return render_template("setup.html")

@app.route("/login", methods=["GET", "POST"])
def login():
    if not storage.has_admin():
        return redirect(url_for('setup'))
        
    if session.get('logged_in'):
        return redirect(url_for('index'))
        
    if request.method == "POST":
        data = request.json or {}
        username = data.get("username", "").strip()
        password = data.get("password", "")
        
        if not username or not password:
            return jsonify({"ok": False, "error": "用户名和密码不能为空"})
            
        if storage.verify_admin(username, password):
            session['logged_in'] = True
            session['username'] = username
            return jsonify({"ok": True, "message": "登录成功！"})
        else:
            return jsonify({"ok": False, "error": "用户名或密码错误"})
            
    return render_template("login.html")

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route("/api/status")
@login_required
def api_status():
    return jsonify(collect_status())

@app.route("/api/history")
@login_required
def api_history():
    limit = int(request.args.get("limit", "288"))
    return jsonify(storage.recent_metrics(limit))

@app.route("/api/alerts")
@login_required
def api_alerts():
    limit = int(request.args.get("limit", "50"))
    return jsonify(storage.recent_alerts(limit))

@app.route("/api/settings", methods=["GET"])
@login_required
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
        "disk_warn_pct": settings.disk_warn_pct,
        "webhook_url": settings.webhook_url
    })

@app.route("/api/settings", methods=["POST"])
@login_required
def post_web_settings():
    data = request.json or {}
    fields = [
        "smtp_host", "smtp_port", "smtp_user", "smtp_to", "smtp_ssl",
        "traffic_warn_mb", "traffic_critical_mb", "traffic_shutdown_mb",
        "auto_shutdown", "alert_cooldown_seconds", "daily_mail_limit",
        "mem_warn_pct", "disk_warn_pct", "webhook_url"
    ]
    for field in fields:
        if field in data:
            storage.set_state(field, str(data[field]))
            
    if "smtp_auth" in data:
        auth_val = data["smtp_auth"]
        if auth_val != "******":
            storage.set_state("smtp_auth", auth_val)
            
    return jsonify({"ok": True, "message": "Settings saved successfully"})

@app.route("/api/settings/password", methods=["POST"])
@login_required
def change_password():
    data = request.json or {}
    old_pwd = data.get("old_password", "")
    new_pwd = data.get("new_password", "")
    
    if not old_pwd or not new_pwd:
        return jsonify({"ok": False, "error": "旧密码和新密码不能为空"})
        
    if len(new_pwd) < 6:
        return jsonify({"ok": False, "error": "新密码不能少于 6 位"})
        
    username = session.get("username")
    if storage.update_admin_password(username, old_pwd, new_pwd):
        return jsonify({"ok": True, "message": "密码修改成功！"})
    else:
        return jsonify({"ok": False, "error": "旧密码验证错误"})

@app.route("/api/settings/test", methods=["POST"])
@login_required
def test_mail_api():
    from mailer import send_mail
    data = request.json or {}
    
    # Handle password masking fallback
    temp_auth = data.get("smtp_auth")
    if temp_auth == "******":
        temp_auth = settings.qq_mail_auth

    try:
        if "smtp_host" in data:
            send_mail(
                subject="GCP Watchdog 发信测试 (表单测试)",
                body="如果你收到这封邮件，说明你刚刚在 Web 表单中填写的 SMTP 配置工作完全正常，可以放心保存配置。",
                to=data.get("smtp_to"),
                host=data.get("smtp_host"),
                port=int(data.get("smtp_port", 465)) if data.get("smtp_port") else None,
                sender=data.get("smtp_user"),
                auth_code=temp_auth,
                use_ssl=bool(data.get("smtp_ssl", True))
            )
        else:
            send_mail("GCP Watchdog 发信测试", "如果你收到这封邮件，说明后台 SMTP 配置及发信功能运行正常。")
        return jsonify({"ok": True, "message": "Test mail sent successfully!"})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500

if __name__ == "__main__":
    app.run(host=settings.web_host, port=settings.web_port)
