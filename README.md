# GCP Watchdog

轻量级 GCP e2-micro 监控与告警工具，适合小内存 Debian 服务器。

## 功能特性

- **多维系统监控**：实时监控 CPU 占用率、内存占用、磁盘空间、系统负载和运行时间。
- **流量防爆关机**：监控网卡出站/入站流量（使用 `psutil` 跨平台计算，支持服务器重启与网卡名称变更的累计统计），超出安全阈值后自动执行系统关机保护。
- **网站与端口拨测**：支持并发 HTTP/HTTPS URL 可用性拨测与 TCP 端口联通性探测。
- **多渠道告警推送**：支持常规 SMTP 邮件通知（QQ 邮箱、Gmail、自定义 SMTP等），以及飞书、钉钉、Discord 等主流群机器人的 Webhook 推送。
- **故障恢复告警 (Recovery Alerts)**：监测点在故障恢复（Up）时发送通知，消除运维焦虑。
- **安全认证管理**：弃用 Basic Auth，改用 Flask Session Cookie 签名认证，密码使用 PBKDF2 安全哈希带盐（Salt）存储。
- **初始化向导**：首次访问强制进入向导注册管理员账户，避免硬编码密码泄露。
- **动态配置看板**：配备精美现代的暗黑毛玻璃风格 Dashboard，支持在线配置发信和告警阈值参数并一键测试。
- **自动日志切片**：所有监测及错误日志写入 `logs/watchdog.log`，单文件 5MB 自动滚存，避免撑爆磁盘。

## 目录结构

```text
gcp_watchdog/
├── app.py                  # Flask Web 面板与 API 控制器
├── config.py               # 动态配置加载模块
├── mailer.py               # SMTP 发信接口
├── monitor.py              # 核心监控指标采集与告警判定
├── storage.py              # SQLite 数据库存取与账号哈希管理
├── watchdog.py             # CLI 任务触发脚本 (定时器调用)
├── requirements.txt        # 依赖模块列表
├── .env.example            # 初始环境变量模板
├── .gitignore              # Git 上传忽略规则
├── systemd/                # systemd 服务管理配置文件
│   ├── gcp-watchdog.service
│   ├── gcp-watchdog.timer
│   └── gcp-watchdog-web.service
├── templates/              # 前端 HTML 模板
│   ├── index.html          # 主仪表盘
│   ├── login.html          # 管理员登录
│   └── setup.html          # 首次使用初始化向导
└── static/
    └── main.js             # 看板 AJAX 交互与 Chart.js 绘制
```

## 1. 安装步骤

```bash
sudo apt update
sudo apt install -y python3 python3-venv python3-pip unzip

cd /opt
sudo unzip gcp_watchdog.zip
sudo mv gcp_watchdog /opt/gcp_watchdog
sudo chown -R $USER:$USER /opt/gcp_watchdog

cd /opt/gcp_watchdog
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

## 2. 初始配置

```bash
cp .env.example .env
nano .env
chmod 600 .env
```

`.env` 中仅需保留基本的宿主主机监听地址与端口（`WEB_HOST`, `WEB_PORT`）以及数据保存目录。邮件和机器人 Webhook 凭证均可在 Web 界面中在线填写。

## 3. 运行 Web 面板服务

```bash
source venv/bin/activate
python app.py
```

默认监听地址：
```text
http://127.0.0.1:8765
```

### 首次初始化说明
1. 首次在浏览器中打开页面时，系统会检测到管理员账号未建立，强制重定向至 `/setup` 引导向导。
2. 请现场设置您的 **管理员用户名** 和 **登录密码（不小于 6 位）**。
3. 创建成功后，即可使用该凭证登录主仪表盘，并在“系统设置”页面填写您的 SMTP 发信选项和 Webhook 地址，点击“保存系统配置”。

## 4. 手动运行一次检测

```bash
source venv/bin/activate
python watchdog.py --once
```

## 5. 定时监控部署 (Systemd)

安装定时检测器：
```bash
sudo cp systemd/gcp-watchdog.service /etc/systemd/system/
sudo cp systemd/gcp-watchdog.timer /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now gcp-watchdog.timer
```

安装 Web 面板守护服务：
```bash
sudo cp systemd/gcp-watchdog-web.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now gcp-watchdog-web.service
```

## 6. 查看日志与诊断

监控运行日志将自动写入本地的滚动日志中，您可以通过以下命令查看：
```bash
# 查看 watchdog 周期执行日志
tail -n 100 logs/watchdog.log

# 实时监听日志变更
tail -f logs/watchdog.log
```

## 7. 关机保护注意事项

- 系统在流量超限时，会尝试依次下达 `/sbin/shutdown`、`shutdown`、`systemctl poweroff` 等命令。
- 为确保流量超额时能够成功关机，触发监控脚本的 `gcp-watchdog.service` 在运行时**必须具备足够的系统特权**（默认以 root 用户运行 systemd timer 即可）。
- Web 服务（Gunicorn）以只读/只写数据库的形式独立运行，建议不要开放 8765 端口到外网，通过 Nginx 反向代理并配置 SSL。
- 本地 `/data/watchdog.db` 文件包含了您的会话密钥、密码哈希和邮件授权码等高敏感数据，请确保其权限为 `600`，且绝不能通过 Git 提交。
