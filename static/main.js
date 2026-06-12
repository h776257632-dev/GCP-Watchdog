let chart;

function fmtTime(ts) {
  const d = new Date(ts * 1000);
  return d.toLocaleString();
}

function fmtUptime(seconds) {
  const d = Math.floor(seconds / (3600 * 24));
  const h = Math.floor((seconds % (3600 * 24)) / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  const s = seconds % 60;
  let res = '';
  if (d > 0) res += d + '天 ';
  if (h > 0 || d > 0) res += h + '时 ';
  if (m > 0 || h > 0 || d > 0) res += m + '分 ';
  res += s + '秒';
  return res;
}

function getPercentClass(v) {
  if (v >= 90) return 'danger';
  if (v >= 75) return 'warn';
  return 'ok';
}

function showToast(title, body, isError = false) {
  const toast = document.getElementById('toast');
  const tTitle = document.getElementById('toast-title');
  const tBody = document.getElementById('toast-body');
  
  tTitle.innerText = title;
  tBody.innerText = body;
  toast.style.borderLeftColor = isError ? 'var(--danger)' : 'var(--primary)';
  toast.style.display = 'block';
  
  setTimeout(() => {
    toast.style.display = 'none';
  }, 4000);
}

function switchTab(tabId) {
  document.querySelectorAll('.tab-content').forEach(el => el.classList.remove('active'));
  document.querySelectorAll('.tab-btn').forEach(el => el.classList.remove('active'));
  
  document.getElementById(tabId).classList.add('active');
  const btn = Array.from(document.querySelectorAll('.tab-btn')).find(b => b.getAttribute('onclick').includes(tabId));
  if (btn) btn.classList.add('active');
  
  if (tabId === 'settings-tab') {
    loadSettings();
  }
}

async function loadStatus() {
  try {
    const r = await fetch('/api/status');
    const s = await r.json();

    const pct = Math.min(100, (s.tx_used_mb / s.thresholds.shutdown) * 100).toFixed(1);
    
    document.getElementById('cards').innerHTML = `
      <div class="card">
        <div class="card-title">本月发送</div>
        <div class="card-value ${s.tx_used_mb >= s.thresholds.critical ? 'danger' : s.tx_used_mb >= s.thresholds.warn ? 'warn' : 'ok'}">${s.tx_used_mb} MB</div>
        <div class="card-desc">${pct}% / 关机阈值 ${s.thresholds.shutdown} MB</div>
      </div>
      <div class="card">
        <div class="card-title">本月接收</div>
        <div class="card-value">${s.rx_used_mb} MB</div>
        <div class="card-desc">双向累计监控中</div>
      </div>
      <div class="card">
        <div class="card-title">实时网络速率</div>
        <div class="card-value" style="font-size:20px; display:flex; flex-direction:column; gap:4px; align-items:flex-start;">
          <span style="color:#60a5fa;">↑ ${s.tx_speed_kbps} KB/s</span>
          <span style="color:#a78bfa;">↓ ${s.rx_speed_kbps} KB/s</span>
        </div>
        <div class="card-desc">接口: ${s.iface}</div>
      </div>
      <div class="card">
        <div class="card-title">系统负载</div>
        <div class="card-value ${getPercentClass(s.cpu_percent)}">${s.cpu_percent}%</div>
        <div class="card-desc">CPU负载: ${s.load1}</div>
      </div>
      <div class="card">
        <div class="card-title">内存占用</div>
        <div class="card-value ${getPercentClass(s.mem_percent)}">${s.mem_percent}%</div>
        <div class="card-desc">VM 资源消耗统计</div>
      </div>
      <div class="card">
        <div class="card-title">磁盘剩余空间</div>
        <div class="card-value ${getPercentClass(s.disk_percent)}">${s.disk_percent}%</div>
        <div class="card-desc">根目录盘符使用率</div>
      </div>
      <div class="card" style="grid-column: span 2;">
        <div class="card-title">运行状态</div>
        <div class="card-value" style="font-size: 20px;">运行时间: ${fmtUptime(s.uptime_seconds)}</div>
        <div class="card-desc">自动关机保护: ${s.auto_shutdown ? '已开启' : '已关闭'}</div>
      </div>
    `;

    document.getElementById('urlChecks').innerHTML = s.url_checks.map(x => 
      `<div class="probe-item">
        <div class="probe-info">
          <span class="probe-target">${x.target}</span>
          <span class="probe-meta">状态代码: ${x.status || '-'} | 延迟: ${x.elapsed ? x.elapsed.toFixed(2) + 's' : '-'} ${x.error ? '| ' + x.error : ''}</span>
        </div>
        <span class="badge ${x.ok ? 'badge-ok' : 'badge-danger'}">${x.ok ? '正常' : '故障'}</span>
      </div>`
    ).join('') || '<p style="color: var(--text-muted); font-size:14px; padding:10px;">未配置 HTTP 检查点</p>';

    document.getElementById('tcpChecks').innerHTML = s.tcp_checks.map(x =>
      `<div class="probe-item">
        <div class="probe-info">
          <span class="probe-target">${x.target}</span>
          <span class="probe-meta">延迟: ${x.elapsed ? x.elapsed.toFixed(2) + 's' : '-'} ${x.error ? '| ' + x.error : ''}</span>
        </div>
        <span class="badge ${x.ok ? 'badge-ok' : 'badge-danger'}">${x.ok ? '正常' : '故障'}</span>
      </div>`
    ).join('') || '<p style="color: var(--text-muted); font-size:14px; padding:10px;">未配置 TCP 检查点</p>';
  } catch (e) {
    showToast('获取实时状态失败', e.message, true);
  }
}

async function loadHistory() {
  try {
    const r = await fetch('/api/history?limit=288');
    const rows = await r.json();
    const labels = rows.map(x => new Date(x.ts * 1000).toLocaleTimeString());
    const tx = rows.map(x => x.tx_speed_kbps);
    const rx = rows.map(x => x.rx_speed_kbps);

    const ctx = document.getElementById('trafficChart');
    if (!chart) {
      chart = new Chart(ctx, {
        type: 'line',
        data: {
          labels,
          datasets: [
            {
              label: '上传速度 (KB/s)',
              data: tx,
              borderColor: '#3b82f6',
              backgroundColor: 'rgba(59, 130, 246, 0.1)',
              fill: true,
              tension: 0.3,
              borderWidth: 2,
              pointRadius: 0,
              pointHoverRadius: 5
            },
            {
              label: '下载速度 (KB/s)',
              data: rx,
              borderColor: '#a78bfa',
              backgroundColor: 'rgba(167, 139, 250, 0.1)',
              fill: true,
              tension: 0.3,
              borderWidth: 2,
              pointRadius: 0,
              pointHoverRadius: 5
            }
          ]
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          plugins: {
            legend: {
              labels: { color: '#f3f4f6', font: { family: 'Outfit' } }
            }
          },
          scales: {
            x: {
              grid: { color: 'rgba(255, 255, 255, 0.05)' },
              ticks: { color: '#9ca3af', font: { family: 'Outfit' } }
            },
            y: {
              grid: { color: 'rgba(255, 255, 255, 0.05)' },
              ticks: { color: '#9ca3af', font: { family: 'Outfit' } },
              beginAtZero: true
            }
          }
        }
      });
    } else {
      chart.data.labels = labels;
      chart.data.datasets[0].data = tx;
      chart.data.datasets[1].data = rx;
      chart.update();
    }
  } catch (e) {
    showToast('获取历史记录失败', e.message, true);
  }
}

async function loadAlerts() {
  try {
    const r = await fetch('/api/alerts?limit=30');
    const rows = await r.json();
    document.getElementById('alerts').innerHTML = rows.map(x => {
      let badgeClass = 'badge-info';
      let levelText = '信息';
      if (x.level === 'warning') { badgeClass = 'badge-warn'; levelText = '警告'; }
      else if (x.level === 'critical' || x.level === 'danger') { badgeClass = 'badge-danger'; levelText = '严重'; }
      
      return `
        <tr>
          <td>${fmtTime(x.ts)}</td>
          <td><span class="badge ${badgeClass}">${levelText}</span></td>
          <td><code>${x.type}</code></td>
          <td style="font-weight: 600;">${x.title}</td>
          <td><span class="badge ${x.sent ? 'badge-ok' : 'badge-danger'}">${x.sent ? '已发' : '未发'}</span></td>
        </tr>
      `;
    }).join('') || '<tr><td colspan="5" style="text-align: center; color: var(--text-muted);">暂无告警记录</td></tr>';
  } catch (e) {
    showToast('获取告警日志失败', e.message, true);
  }
}

async function loadSettings() {
  try {
    const r = await fetch('/api/settings');
    const s = await r.json();
    
    document.getElementById('smtp_host').value = s.smtp_host || '';
    document.getElementById('smtp_port').value = s.smtp_port || 465;
    document.getElementById('smtp_user').value = s.smtp_user || '';
    document.getElementById('smtp_auth').value = s.smtp_auth || '';
    document.getElementById('smtp_to').value = s.smtp_to || '';
    document.getElementById('smtp_ssl').checked = !!s.smtp_ssl;
    
    document.getElementById('traffic_warn_mb').value = s.traffic_warn_mb || 500;
    document.getElementById('traffic_critical_mb').value = s.traffic_critical_mb || 700;
    document.getElementById('traffic_shutdown_mb').value = s.traffic_shutdown_mb || 900;
    document.getElementById('mem_warn_pct').value = s.mem_warn_pct || 90;
    document.getElementById('disk_warn_pct').value = s.disk_warn_pct || 85;
    document.getElementById('alert_cooldown_seconds').value = s.alert_cooldown_seconds || 1800;
    document.getElementById('daily_mail_limit').value = s.daily_mail_limit || 20;
    document.getElementById('auto_shutdown').checked = !!s.auto_shutdown;
  } catch (e) {
    showToast('加载配置失败', e.message, true);
  }
}

async function saveSettings(e) {
  e.preventDefault();
  const data = {
    smtp_host: document.getElementById('smtp_host').value,
    smtp_port: parseInt(document.getElementById('smtp_port').value),
    smtp_user: document.getElementById('smtp_user').value,
    smtp_auth: document.getElementById('smtp_auth').value,
    smtp_to: document.getElementById('smtp_to').value,
    smtp_ssl: document.getElementById('smtp_ssl').checked,
    
    traffic_warn_mb: parseInt(document.getElementById('traffic_warn_mb').value),
    traffic_critical_mb: parseInt(document.getElementById('traffic_critical_mb').value),
    traffic_shutdown_mb: parseInt(document.getElementById('traffic_shutdown_mb').value),
    mem_warn_pct: parseInt(document.getElementById('mem_warn_pct').value),
    disk_warn_pct: parseInt(document.getElementById('disk_warn_pct').value),
    alert_cooldown_seconds: parseInt(document.getElementById('alert_cooldown_seconds').value),
    daily_mail_limit: parseInt(document.getElementById('daily_mail_limit').value),
    auto_shutdown: document.getElementById('auto_shutdown').checked
  };
  
  try {
    const r = await fetch('/api/settings', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data)
    });
    const res = await r.json();
    if (res.ok) {
      showToast('成功', '配置保存成功！');
    } else {
      showToast('失败', res.message, true);
    }
  } catch(err) {
    showToast('保存配置出错', err.message, true);
  }
}

async function testEmail() {
  showToast('正在发送...', '正在向配置的邮箱发送测试邮件，请稍候...');
  try {
    const r = await fetch('/api/settings/test', { method: 'POST' });
    const res = await r.json();
    if (res.ok) {
      showToast('发送成功', '测试邮件已发送，请检查收件箱！');
    } else {
      showToast('发送失败', res.error || '未知错误', true);
    }
  } catch (err) {
    showToast('网络错误', err.message, true);
  }
}

async function refresh() {
  if (document.getElementById('dashboard').classList.contains('active')) {
    await loadStatus();
    await loadHistory();
    await loadAlerts();
  }
}

refresh();
setInterval(refresh, 15000);
