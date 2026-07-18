'use strict';

const MAX_POINTS = 60; // rolling history window

// ── Chart factory ────────────────────────────────────────────────────────────

function makeChart(id, datasets, yMax = 100) {
  const ctx = document.getElementById(id);
  if (!ctx) return null;
  return new Chart(ctx, {
    type: 'line',
    data: {
      labels: Array(MAX_POINTS).fill(''),
      datasets: datasets.map(ds => ({
        label: ds.label,
        data: Array(MAX_POINTS).fill(null),
        borderColor: ds.color,
        backgroundColor: ds.color + '22',
        borderWidth: 2,
        pointRadius: 0,
        fill: true,
        tension: 0.3,
      })),
    },
    options: {
      animation: false,
      responsive: true,
      maintainAspectRatio: false,
      scales: {
        x: { display: false },
        y: {
          min: 0, max: yMax,
          grid: { color: '#21262d' },
          ticks: { color: '#8b949e', font: { size: 10 } },
        },
      },
      plugins: {
        legend: { labels: { color: '#8b949e', boxWidth: 12, font: { size: 11 } } },
      },
    },
  });
}

function pushPoint(chart, datasetIdx, value) {
  if (!chart) return;
  chart.data.datasets[datasetIdx].data.push(value);
  chart.data.datasets[datasetIdx].data.shift();
  chart.update('none');
}

// ── Initialise charts ─────────────────────────────────────────────────────────

const cpuChart  = makeChart('cpu-chart',  [{ label: 'CPU Usage %', color: '#3fb950' }]);
const memChart  = makeChart('mem-chart',  [{ label: 'RAM Usage %', color: '#58a6ff' }]);
const gpuChart  = makeChart('gpu-chart',  [{ label: 'GPU Usage %', color: '#bc8cff' }, { label: 'GPU Temp C', color: '#f85149' }], 110);
const netChart  = makeChart('net-chart',  [{ label: 'Up KB/s', color: '#39d353' }, { label: 'Down KB/s', color: '#58a6ff' }], null);

// ── Helpers ───────────────────────────────────────────────────────────────────

function row(label, value) {
  return `<span class="label">${label}</span><span class="value">${value ?? 'N/A'}</span>`;
}

function bar(pct) {
  const v = pct ?? 0;
  const cls = v < 70 ? 'green' : v < 90 ? 'yellow' : 'red';
  return `<div class="bar-wrap"><div class="bar-fill ${cls}" style="width:${v}%"></div></div>`;
}

function tempBadge(c) {
  if (c === null || c === undefined) return 'N/A';
  const cls = c < 60 ? 'cool' : c < 80 ? 'warm' : 'hot';
  return `<span class="temp-badge ${cls}">${c} C</span>`;
}

function fmtMHz(mhz) {
  if (!mhz) return 'N/A';
  return mhz >= 1000 ? (mhz / 1000).toFixed(2) + ' GHz' : mhz + ' MHz';
}

function fmtTime() {
  return new Date().toLocaleTimeString();
}

// ── Render functions ──────────────────────────────────────────────────────────

function renderAlerts(alerts) {
  const el = document.getElementById('alerts-container');
  if (!alerts || alerts.length === 0) { el.innerHTML = ''; return; }
  el.innerHTML = alerts.map(a => {
    const cls = a.toLowerCase().includes('[critical]') ? 'critical' : 'warning';
    return `<div class="alert-banner ${cls}">${a}</div>`;
  }).join('');
}

function renderCPU(cpu) {
  if (!cpu) return;
  const el = document.getElementById('cpu-info');
  el.innerHTML = [
    row('Model', cpu.model),
    row('Cores', `${cpu.physical_cores} physical / ${cpu.logical_cores} logical`),
    row('Frequency', fmtMHz(cpu.frequency_mhz)),
    row('Max Freq', fmtMHz(cpu.frequency_max_mhz)),
    row('Usage', `${cpu.usage_percent ?? 'N/A'}%`),
    row('L2 Cache', cpu.cache_l2_kb ? cpu.cache_l2_kb + ' KB' : 'N/A'),
    row('L3 Cache', cpu.cache_l3_kb ? cpu.cache_l3_kb + ' KB' : 'N/A'),
  ].join('');
  if (cpu.usage_percent !== undefined) pushPoint(cpuChart, 0, cpu.usage_percent);
}

function renderMemory(mem) {
  if (!mem) return;
  const el = document.getElementById('mem-info');
  el.innerHTML = [
    row('Total', (mem.total_gb ?? 'N/A') + ' GB'),
    row('Used', (mem.used_gb ?? 'N/A') + ' GB'),
    row('Available', (mem.available_gb ?? 'N/A') + ' GB'),
    row('Usage', `${mem.usage_percent ?? 'N/A'}% ${bar(mem.usage_percent)}`),
    row('Type', mem.type ?? 'N/A'),
    row('Speed', mem.speed_mhz ? mem.speed_mhz + ' MHz' : 'N/A'),
    row('Slots', `${mem.slots_used ?? 'N/A'} / ${mem.slots_total ?? 'N/A'}`),
    row('Swap', `${mem.swap_used_gb ?? 0} / ${mem.swap_total_gb ?? 0} GB`),
  ].join('');
  if (mem.usage_percent !== undefined) pushPoint(memChart, 0, mem.usage_percent);
}

function renderGPU(gpus) {
  const el = document.getElementById('gpu-info');
  if (!gpus || gpus.length === 0) {
    el.innerHTML = '<em>No GPU detected.</em>';
    return;
  }
  el.innerHTML = gpus.map((g, i) => `
    <div class="info-grid" style="margin-bottom:8px">
      ${row('GPU ' + i, g.name)}
      ${row('Vendor', g.vendor)}
      ${row('Driver', g.driver)}
      ${row('VRAM', g.vram_total_mb ? g.vram_used_mb + ' / ' + g.vram_total_mb + ' MB' : 'N/A')}
      ${row('Load', (g.load_percent ?? 'N/A') + '%')}
      ${row('Temperature', tempBadge(g.temperature_c))}
      ${row('Fan Speed', g.fan_speed_percent != null ? g.fan_speed_percent + '%' : 'N/A')}
    </div>`).join('<hr style="border-color:#30363d;margin:8px 0">');

  const first = gpus[0];
  pushPoint(gpuChart, 0, first.load_percent);
  pushPoint(gpuChart, 1, first.temperature_c);
}

function renderThermal(thermal) {
  if (!thermal) return;
  const el = document.getElementById('thermal-info');
  const temps = thermal.temperatures ?? {};
  const fans = thermal.fans ?? {};

  let html = '';

  const allTemps = Object.entries(temps).flatMap(([sensor, entries]) =>
    entries.map(e => ({ sensor, ...e }))
  );
  if (allTemps.length > 0) {
    html += '<table><thead><tr><th>Sensor</th><th>Label</th><th>Temp</th><th>High</th><th>Critical</th></tr></thead><tbody>';
    html += allTemps.map(e => `<tr>
      <td>${e.sensor}</td>
      <td>${e.label}</td>
      <td>${tempBadge(e.current_c)}</td>
      <td>${e.high_c ?? '-'}</td>
      <td>${e.critical_c ?? '-'}</td>
    </tr>`).join('');
    html += '</tbody></table>';
  }

  const allFans = Object.entries(fans).flatMap(([fan, entries]) =>
    entries.map(e => ({ fan, ...e }))
  );
  if (allFans.length > 0) {
    html += '<table style="margin-top:10px"><thead><tr><th>Fan</th><th>Label</th><th>RPM</th></tr></thead><tbody>';
    html += allFans.map(e => `<tr><td>${e.fan}</td><td>${e.label}</td><td>${e.rpm}</td></tr>`).join('');
    html += '</tbody></table>';
  }

  if (!allTemps.length && !allFans.length) html = '<em>No sensor data available.</em>';
  el.innerHTML = html;
}

function renderStorage(disks) {
  const el = document.getElementById('storage-info');
  if (!disks || disks.length === 0) { el.innerHTML = '<em>No disks found.</em>'; return; }
  el.innerHTML = '<table><thead><tr><th>Device</th><th>Mount</th><th>Total</th><th>Used</th><th>Usage</th><th>SMART</th><th>Temp</th></tr></thead><tbody>' +
    disks.map(d => {
      const pct = d.usage_percent ?? 0;
      const smartCls = d.smart_health === 'PASSED' ? 'passed' : d.smart_health === 'FAILED' ? 'failed' : '';
      return `<tr>
        <td>${d.device}</td>
        <td>${d.mountpoint}</td>
        <td>${d.total_gb ?? 'N/A'} GB</td>
        <td>${d.used_gb ?? 'N/A'} GB</td>
        <td>${pct}% ${bar(pct)}</td>
        <td><span class="tag ${smartCls}">${d.smart_health ?? '-'}</span></td>
        <td>${d.smart_temperature_c ?? '-'}</td>
      </tr>`;
    }).join('') + '</tbody></table>';
}

function renderNetwork(ifaces) {
  const el = document.getElementById('net-info');
  if (!ifaces || ifaces.length === 0) { el.innerHTML = '<em>No interfaces found.</em>'; return; }
  el.innerHTML = '<table><thead><tr><th>Interface</th><th>Status</th><th>IPv4</th><th>Up KB/s</th><th>Down KB/s</th><th>Sent MB</th><th>Recv MB</th></tr></thead><tbody>' +
    ifaces.map(n => {
      const cls = n.is_up ? 'up' : 'down';
      return `<tr>
        <td>${n.name}</td>
        <td><span class="tag ${cls}">${n.is_up ? 'UP' : 'DOWN'}</span></td>
        <td>${n.ipv4 ?? '-'}</td>
        <td>${n.send_rate_kbps ?? '-'}</td>
        <td>${n.recv_rate_kbps ?? '-'}</td>
        <td>${n.bytes_sent_mb ?? '-'}</td>
        <td>${n.bytes_recv_mb ?? '-'}</td>
      </tr>`;
    }).join('') + '</tbody></table>';

  const active = ifaces.find(n => n.is_up && n.send_rate_kbps != null);
  if (active) {
    pushPoint(netChart, 0, active.send_rate_kbps);
    pushPoint(netChart, 1, active.recv_rate_kbps);
  }
}

function renderBattery(bat) {
  const el = document.getElementById('bat-info');
  if (!bat) { el.innerHTML = '<em>No battery detected.</em>'; return; }
  const pct = bat.percent ?? 0;
  el.innerHTML = `<div class="info-grid">
    ${row('Charge', pct + '%')}
    ${row('', bar(100 - pct))}
    ${row('Status', bat.status)}
    ${row('Time Remaining', bat.time_remaining ?? 'N/A')}
  </div>`;
}

function renderMotherboard(mobo) {
  if (!mobo) return;
  const el = document.getElementById('mobo-info');
  el.innerHTML = [
    row('Manufacturer', mobo.manufacturer),
    row('Product', mobo.product),
    row('Version', mobo.version),
    row('BIOS Vendor', mobo.bios_vendor),
    row('BIOS Version', mobo.bios_version),
    row('BIOS Date', mobo.bios_date),
  ].join('');
}

// ── SocketIO ──────────────────────────────────────────────────────────────────

const socket = io();
const dot = document.getElementById('status-dot');
const lastUpdate = document.getElementById('last-update');

socket.on('connect', () => {
  dot.className = 'dot green';
  lastUpdate.textContent = 'Connected — waiting for data...';
});

socket.on('disconnect', () => {
  dot.className = 'dot red';
  lastUpdate.textContent = 'Disconnected';
});

socket.on('hardware_update', ({ data, alerts }) => {
  renderAlerts(alerts);
  renderCPU(data.cpu);
  renderMemory(data.memory);
  renderGPU(data.gpu);
  renderThermal(data.thermal);
  renderStorage(data.storage);
  renderNetwork(data.network);
  renderBattery(data.battery);
  renderMotherboard(data.motherboard);
  lastUpdate.textContent = 'Last update: ' + fmtTime();
});

// ── Initial load via REST ─────────────────────────────────────────────────────

fetch('/api/snapshot')
  .then(r => r.json())
  .then(({ data, alerts }) => {
    renderAlerts(alerts);
    renderCPU(data.cpu);
    renderMemory(data.memory);
    renderGPU(data.gpu);
    renderThermal(data.thermal);
    renderStorage(data.storage);
    renderNetwork(data.network);
    renderBattery(data.battery);
    renderMotherboard(data.motherboard);
    lastUpdate.textContent = 'Last update: ' + fmtTime();
  })
  .catch(() => {});
