#!/usr/bin/env python3

html = '''<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>FloodWatch Nigeria | Decision Support</title>
  <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" crossorigin="">
  <style>
    :root { --navy: #071b35; --blue: #0b5cab; --ink: #142033; --muted: #607087; --line: #dfe6ee; --card: #fff; --low: #16803c; --moderate: #c78000; --high: #da5a00; --severe: #bd2434; }
    * { box-sizing: border-box; }
    body { margin: 0; background: #f4f7fb; color: var(--ink); font: 15px/1.5 system-ui, sans-serif; }
    .topbar { background: linear-gradient(110deg, #06172e, #093d73); color: #fff; padding: 20px; }
    h1 { margin: 0; font-size: 1.8rem; }
    .subtitle { margin: 4px 0 0; color: #c9ddf1; font-size: 0.9rem; }
    .notice { background: #eaf4ff; padding: 12px 16px; border-left: 4px solid #2182d0; margin: 20px; }
    .controls { display: flex; gap: 16px; flex-wrap: wrap; margin: 20px; align-items: center; }
    .controls label { font-weight: 700; }
    .controls select { padding: 8px 12px; border: 1px solid #dfe6ee; border-radius: 6px; }
    .metrics { display: grid; grid-template-columns: repeat(4, 1fr); gap: 15px; margin: 20px; }
    .metric { background: white; border: 1px solid #dfe6ee; padding: 16px; border-radius: 8px; }
    .metric-value { font-size: 1.5rem; font-weight: 800; }
    .grid { display: grid; grid-template-columns: 1.5fr 1fr; gap: 15px; margin: 20px; }
    .panel { background: white; border: 1px solid #dfe6ee; border-radius: 8px; padding: 16px; }
    .map-wrap { height: 400px; background: #e5e5e5; }
    .map { width: 100%; height: 100%; }
    .stations { list-style: none; padding: 0; }
    .station { border-left: 4px solid #c78000; padding: 12px; border-bottom: 1px solid #dfe6ee; }
    .station h3 { margin: 0 0 8px; }
    .station p { margin: 4px 0; }
  </style>
</head>
<body>
  <header class="topbar"><h1>FloodWatch Nigeria</h1><p class="subtitle">Early warning and decision support dashboard</p></header>
  <main>
    <section class="notice"><strong>Decision support, not an autonomous emergency system.</strong> Always follow official guidance.</section>
    <div class="controls">
      <label for="source-select">Data Source:</label>
      <select id="source-select"><option value="hybrid">Hybrid (all)</option><option value="simulated">Simulated only</option><option value="hardware">Hardware only</option></select>
      <label for="layer-select">Map Layer:</label>
      <select id="layer-select"><option value="osm">OpenStreetMap</option><option value="satellite">Google Satellite</option></select>
    </div>
    <section class="metrics">
      <div class="metric"><div style="color: #607087; font-size: 0.8rem; font-weight: 700; text-transform: uppercase; letter-spacing: 0.05em;">Monitored Stations</div><div class="metric-value" id="station-count">0</div></div>
      <div class="metric"><div style="color: #607087; font-size: 0.8rem; font-weight: 700; text-transform: uppercase; letter-spacing: 0.05em;">Highest Risk</div><div class="metric-value" id="highest-risk">—</div></div>
      <div class="metric"><div style="color: #607087; font-size: 0.8rem; font-weight: 700; text-transform: uppercase; letter-spacing: 0.05em;">Alert-Ready Stations</div><div class="metric-value" id="alert-count">0</div></div>
      <div class="metric"><div style="color: #607087; font-size: 0.8rem; font-weight: 700; text-transform: uppercase; letter-spacing: 0.05em;">Model Status</div><div class="metric-value" id="model-status">Standby</div></div>
    </section>
    <div class="grid">
      <div class="panel"><h2 style="margin: 0 0 12px;">Live Station Map</h2><div id="map" class="map-wrap"></div></div>
      <div class="panel"><h2 style="margin: 0 0 12px;">Station Status</h2><ul id="stations" class="stations"></ul></div>
    </div>
  </main>
  <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js" crossorigin=""></script>
  <script>
    var ranks = { Low: 1, Moderate: 2, High: 3, Severe: 4 };
    var currentSource = 'hybrid';
    var currentLayer = 'osm';
    var map = L.map('map', { scrollWheelZoom: false }).setView([9.08, 8.68], 6);
    var baseLayers = { osm: L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', { attribution: '&copy; OpenStreetMap', maxZoom: 18 }), satellite: L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}', { attribution: '&copy; Esri', maxZoom: 18 }) };
    baseLayers.osm.addTo(map);
    var markers = [];
    function setSummary(stations) { var highest = stations.reduce(function(b, i) { return !b || ranks[i.risk_level] > ranks[b.risk_level] ? i : b; }, null); document.getElementById('station-count').textContent = stations.length; document.getElementById('alert-count').textContent = stations.filter(function(i) { return i.risk_level !== 'Low'; }).length; document.getElementById('highest-risk').textContent = highest ? highest.risk_level : '—'; document.getElementById('model-status').textContent = stations.some(function(i) { return i.model_available; }) ? 'Ready' : 'Standby'; }
    function renderStations(stations) { var list = document.getElementById('stations'); list.innerHTML = stations.map(function(s) { var ch = [s.alert_channels.web ? 'web' : null, s.alert_channels.sms ? 'SMS' : null, s.alert_channels.email ? 'email' : null, s.alert_channels.whatsapp ? 'WhatsApp' : null].filter(Boolean).join(' · '); return '<li class="station" style="border-left-color: ' + s.color + '; color: #' + s.color.substring(1) + ';"><h3>' + s.station_name + '</h3><p><strong>' + s.risk_level + '</strong> - Water: ' + s.water_level_m + 'm / ' + s.danger_level_m + 'm</p><p>' + s.message + '</p><p style="font-size: 0.8rem; color: #607087;">Channels: ' + ch + '</p></li>'; }).join(''); }
    function renderMarkers(stations) { markers.forEach(function(m) { map.removeLayer(m); }); markers = []; stations.forEach(function(s) { var circle = L.circleMarker([s.lat, s.lon], { radius: 8, fillColor: s.color, color: s.color, weight: 2, opacity: 1, fillOpacity: 0.8 }).bindPopup(s.station_name + ' (' + s.risk_level + ')').addTo(map); markers.push(circle); }); }
    function loadStatus() { var url = '/api/risk-status'; if (currentSource !== 'hybrid') url += '?data_source=' + currentSource; fetch(url).then(function(r) { return r.json(); }).then(function(s) { setSummary(s); renderStations(s); renderMarkers(s); }).catch(function(e) { console.error(e); }); }
    document.getElementById('source-select').addEventListener('change', function(e) { currentSource = e.target.value; loadStatus(); });
    document.getElementById('layer-select').addEventListener('change', function(e) { if (e.target.value === 'osm') { map.removeLayer(baseLayers.satellite); map.addLayer(baseLayers.osm); } else { map.removeLayer(baseLayers.osm); map.addLayer(baseLayers.satellite); } });
    loadStatus();
    setInterval(loadStatus, 15000);
  </script>
</body>
</html>'''

with open('files/dashboard/index.html', 'w') as f:
    f.write(html)

print('Dashboard updated successfully with source and layer controls!')
