/* Map + dashboard for Smart Bins KG. Reads /bins from the same origin
   (nginx proxies the API) or from ?api=http://localhost:8000 during dev. */

const API_BASE = new URLSearchParams(location.search).get("api") || "";
const REFRESH_MS = 10000;
const COLORS = {
  green: "#22a06b",
  yellow: "#e0a100",
  red: "#d64545",
  needs_review: "#9aa3ab",
  unknown: "#9aa3ab",
};
const LABELS = {
  green: "пусто",
  yellow: "наполовину",
  red: "полно",
  needs_review: "на проверку",
  unknown: "нет данных",
};

const state = { bins: [], offline: new Set(), onlyRed: false, onlyOffline: false };

const map = L.map("map").setView([42.87, 74.59], 12);
L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
  maxZoom: 19,
  attribution: "&copy; OpenStreetMap",
}).addTo(map);

const markers = new Map();

function api(path) {
  return fetch(`${API_BASE}${path}`).then((response) => {
    if (!response.ok) throw new Error(`${path}: HTTP ${response.status}`);
    return response.json();
  });
}

function formatTime(value) {
  if (!value) return "нет данных";
  const date = new Date(`${value}Z`);
  return date.toLocaleString("ru-RU", { dateStyle: "short", timeStyle: "short" });
}

function visibleBins() {
  return state.bins.filter((bin) => {
    if (state.onlyRed && bin.status !== "red") return false;
    if (state.onlyOffline && bin.device_status !== "offline") return false;
    return true;
  });
}

function popupHtml(bin) {
  const photo = bin.last_snapshot_at
    ? `<img class="popup-photo" src="${API_BASE}${bin.image_url || ""}" alt="последнее фото" onerror="this.remove()" />`
    : "";
  return `
    <strong>${bin.name}</strong><br />
    Статус: ${LABELS[bin.status] || bin.status}<br />
    Заполненность: ${bin.fill_ratio == null ? "—" : Math.round(bin.fill_ratio * 100) + "%"}<br />
    Обновлено: ${formatTime(bin.last_snapshot_at)}<br />
    Устройство: ${bin.device_status === "online" ? "на связи" : "нет связи"}
    ${photo}`;
}

function render() {
  const bins = visibleBins();
  const seen = new Set();

  for (const bin of bins) {
    seen.add(bin.id);
    const color = COLORS[bin.status] || COLORS.unknown;
    if (!markers.has(bin.id)) {
      const marker = L.circleMarker([bin.lat, bin.lon], {
        radius: 11,
        color: "#fff",
        weight: 2,
        fillColor: color,
        fillOpacity: 0.95,
      }).addTo(map);
      markers.set(bin.id, marker);
    }
    const marker = markers.get(bin.id);
    marker.setStyle({ fillColor: color });
    marker.bindPopup(popupHtml(bin));
    marker.bindTooltip(bin.name);
  }

  for (const [id, marker] of markers.entries()) {
    if (!seen.has(id)) {
      marker.remove();
      markers.delete(id);
    }
  }

  const counts = state.bins.reduce(
    (acc, bin) => {
      acc[bin.status] = (acc[bin.status] || 0) + 1;
      return acc;
    },
    {}
  );
  document.getElementById("summary").textContent =
    `Всего: ${state.bins.length} · красных: ${counts.red || 0} · жёлтых: ${counts.yellow || 0} · зелёных: ${counts.green || 0}`;
  document.getElementById("updated").textContent =
    `обновлено ${new Date().toLocaleTimeString("ru-RU")}`;

  const list = document.getElementById("bin-list");
  list.innerHTML = "";
  for (const bin of bins) {
    const item = document.createElement("li");
    item.className = `bin-card ${bin.status}`;
    item.innerHTML = `
      <strong>${bin.name}</strong>
      <div class="meta">${LABELS[bin.status] || bin.status} · ${formatTime(bin.last_snapshot_at)}</div>
      <div class="meta ${bin.device_status === "offline" ? "warn" : ""}">
        ${bin.device_status === "offline" ? "нет связи" : bin.device_status === "online" ? "на связи" : "устройство не подключено"}
      </div>`;
    item.addEventListener("click", () => {
      map.setView([bin.lat, bin.lon], 16);
      markers.get(bin.id)?.openPopup();
    });
    list.appendChild(item);
  }

  if (!bins.length) {
    list.innerHTML = '<li class="meta">Нет баков под выбранным фильтром.</li>';
  }
}

async function refresh() {
  try {
    const [bins, offline] = await Promise.all([
      api("/bins").catch((error) => {
        console.warn(error);
        return [];
      }),
      api("/devices/offline").catch(() => []),
    ]);
    const details = await Promise.all(
      bins.slice(0, 30).map((bin) =>
        api(`/bins/${bin.id}`)
          .then((detail) => ({ ...bin, last_snapshot: detail.last_snapshot }))
          .catch(() => bin)
      )
    );
    state.bins = details.map((bin) => ({
      ...bin,
      image_url: bin.last_snapshot?.image_url,
    }));
    state.offline = new Set(offline.map((item) => item.bin_id));
    render();
  } catch (error) {
    document.getElementById("summary").textContent = "API недоступен";
    console.error(error);
  }
}

document.getElementById("only-red").addEventListener("change", (event) => {
  state.onlyRed = event.target.checked;
  render();
});
document.getElementById("only-offline").addEventListener("change", (event) => {
  state.onlyOffline = event.target.checked;
  render();
});

refresh();
setInterval(refresh, REFRESH_MS);
