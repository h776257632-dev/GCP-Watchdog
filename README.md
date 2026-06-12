# GCP Watchdog

轻量级 GCP e2-micro 监控与邮件告警工具，适合小内存 Debian 服务器。

功能：

- 监控出站/入站流量
- 监控 CPU、内存、磁盘、负载、运行时间
- 检测网站/端口可用性
- QQ 邮箱 SMTP 告警
- 每日发信数量限制
- 同类告警冷却
- 可选自动关机保护
- Flask Web 面板
- SQLite 历史记录

## 目录结构

```text
gcp_watchdog/
├── app.py
├── config.py
├── mailer.py
├── monitor.py
├── storage.py
├── watchdog.py
├── requirements.txt
├── .env.example
├── systemd/
│   ├── gcp-watchdog.service
│   ├── gcp-watchdog.timer
│   └── gcp-watchdog-web.service
├── templates/
│   └── index.html
└── static/
    └── main.js
```

## 1. 安装

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

## 2. 配置

```bash
cp .env.example .env
nano .env
chmod 600 .env
```

重点配置：

```env
QQ_MAIL_USER=你的QQ邮箱@qq.com
QQ_MAIL_AUTH=你的QQ邮箱授权码
QQ_MAIL_TO=你的接收邮箱@qq.com
```

QQ 邮箱授权码不是 QQ 密码，需要在 QQ 邮箱网页端开启 SMTP 服务后生成。

## 3. 测试发信

```bash
source venv/bin/activate
python watchdog.py --test-mail
```

看到 `mail sent` 并收到邮件说明成功。

## 4. 手动运行一次检测

```bash
source venv/bin/activate
python watchdog.py --once
```

## 5. 启动 Web 面板

```bash
source venv/bin/activate
python app.py
```

默认监听：

```text
http://127.0.0.1:8765
```

可以用宝塔/Nginx 反向代理到这个地址。

默认 Web 登录密码在 `.env`：

```env
WEB_PASSWORD=change-me
```

## 6. 安装 systemd 定时监控

```bash
sudo cp systemd/gcp-watchdog.service /etc/systemd/system/
sudo cp systemd/gcp-watchdog.timer /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now gcp-watchdog.timer
```

查看定时器：

```bash
systemctl list-timers | grep gcp-watchdog
```

查看日志：

```bash
journalctl -u gcp-watchdog.service -n 100 --no-pager
```

## 7. 安装 Web 面板服务

```bash
sudo cp systemd/gcp-watchdog-web.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now gcp-watchdog-web.service
```

查看：

```bash
systemctl status gcp-watchdog-web.service
```

## 8. 宝塔/Nginx 反向代理建议

目标地址：

```text
http://127.0.0.1:8765
```

建议不要直接开放 8765 端口到公网。可以通过宝塔反向代理、Cloudflare Access 或只允许内网访问。

## 9. 阈值说明

默认配置：

```env
TRAFFIC_WARN_MB=500
TRAFFIC_CRITICAL_MB=700
TRAFFIC_SHUTDOWN_MB=900
AUTO_SHUTDOWN=false
```

建议先保持 `AUTO_SHUTDOWN=false`，确认告警稳定后再改为 `true`。

## 10. 注意事项

- 统计的是服务器网卡 TX/RX，不完全等于 GCP 账单口径。
- 适合作为防爆流量保护，不替代 GCP Billing。
- 不要把 `.env` 发给别人。
- 不要把 Web 面板裸露公网。
