let refreshTimer = null;
let currentEvents = [];
let activeTab = "tete";

function formatTime(iso) {
  if (!iso) return "—";
  const dt = new Date(iso);
  if (Number.isNaN(dt.getTime())) return iso;
  return dt.toLocaleString();
}

function eventLabel(eventType, source) {
  if (eventType === "TeTe") return "🐾 Ghi nhận Tê Tê";
  if (eventType === "CayVoiMoc") return "🐾 Ghi nhận Cầy Vòi Mốc";
  if (eventType === "Nguy hiem") {
    if (source === "Hunter Spot") return "⚠️ Phát hiện nguy cơ thợ săn";
    return "⚠️ Cảnh báo xâm nhập rừng";
  }
  return eventType ? `🌿 ${eventType}` : "—";
}

function pillClass(eventType) {
  if (eventType === "Nguy hiem") return "pill danger";
  if (eventType === "TeTe" || eventType === "CayVoiMoc") return "pill ok";
  return "pill";
}

async function fetchEvents(limit = 50) {
  const res = await fetch(`/api/events?limit=${encodeURIComponent(String(limit))}`, {
    headers: { Accept: "application/json" },
  });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}

async function clearAllHistory() {
  const btn = document.getElementById("clear-events");
  if (btn) btn.disabled = true;
  try {
    const res = await fetch("/api/events/clear", { method: "POST" });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
  } finally {
    if (btn) btn.disabled = false;
  }
}

function renderEvents(events) {
  const listEl = document.getElementById("events");
  const emptyEl = document.getElementById("events-empty");
  listEl.innerHTML = "";

  if (!events.length) {
    emptyEl.style.display = "block";
    return;
  }

  emptyEl.style.display = "none";

  for (const ev of events) {
    const probText =
      typeof ev.probability === "number" ? `${Math.round(ev.probability * 100)}%` : "—";

    const confidenceText = ev.event_type === "TeTe" ? "" : ` · Độ tin cậy: ${probText}`;

    const wrap = document.createElement("div");
    wrap.className = "event";

    wrap.innerHTML = `
      <div class="event-top">
        <div class="event-meta">
          <div class="event-title">${eventLabel(ev.event_type, ev.source)}</div>
          <div class="event-desc">
            Thời gian: ${formatTime(ev.created_at)}${confidenceText} · Nguồn: ${ev.source ?? "—"}
          </div>
        </div>
        <div class="${pillClass(ev.event_type)}">${ev.event_type}</div>
      </div>
      <div class="event-media">
        <div>
          ${
            ev.image_url
              ? `<img class="thumb" src="${ev.image_url}" alt="snapshot" loading="lazy" />`
              : `<div class="thumb" style="display:flex;align-items:center;justify-content:center;color:rgba(232,245,233,0.6);">Không có ảnh</div>`
          }
        </div>
        <div>
          ${
            ev.video_url
              ? `<video controls muted playsinline preload="metadata" src="${ev.video_url}"></video>`
              : `<div style="height:100%;min-height:120px;display:flex;align-items:center;justify-content:center;border:1px solid rgba(255,255,255,0.08);border-radius:12px;background:rgba(255,255,255,0.04);color:rgba(232,245,233,0.6);">Không có video</div>`
          }
        </div>
      </div>
    `;

    listEl.appendChild(wrap);
  }
}

function updateSummary(events) {
  const totalEl = document.getElementById("total-events");
  const lastEl = document.getElementById("last-seen");
  const lastSubEl = document.getElementById("last-seen-sub");
  const healthEl = document.getElementById("health-pill");
  const updatedAtEl = document.getElementById("updated-at");

  totalEl.textContent = String(events.length);
  updatedAtEl.textContent = `Cập nhật: ${new Date().toLocaleTimeString()}`;

  if (!events.length) {
    lastEl.textContent = "—";
    lastSubEl.textContent = "Mở CCTV để bắt đầu nhận dữ liệu.";
    healthEl.className = "pill";
    healthEl.textContent = "Chưa có dữ liệu";
    return;
  }

  const latest = events[0];
  lastEl.textContent = formatTime(latest.created_at);
  lastSubEl.textContent = `${eventLabel(latest.event_type, latest.source)} · ${latest.source ?? "camera"}`;
  healthEl.className = pillClass(latest.event_type);
  healthEl.textContent = latest.event_type;
}

function updateLatestVideo(events) {
  const videoEl = document.getElementById("latest-video");
  const emptyEl = document.getElementById("latest-video-empty");
  if (!videoEl || !emptyEl) return;

  if (!events.length || !events[0]?.video_url) {
    videoEl.pause?.();
    videoEl.removeAttribute("src");
    videoEl.load?.();
    videoEl.style.display = "none";
    emptyEl.style.display = "flex";
    return;
  }

  const url = events[0].video_url;
  if (videoEl.getAttribute("src") !== url) {
    videoEl.setAttribute("src", url);
    videoEl.load();
  }

  emptyEl.style.display = "none";
  videoEl.style.display = "block";
}

function renderFilteredEvents() {
  const filtered = currentEvents.filter((ev) => {
    if (activeTab === "tete") {
      return ev.event_type === "TeTe";
    } else if (activeTab === "hunter") {
      return ev.event_type === "Nguy hiem";
    }
    return true;
  });

  const emptyEl = document.getElementById("events-empty");
  if (emptyEl) {
    if (activeTab === "tete") {
      emptyEl.textContent = "Chưa phát hiện Tê tê. Hãy mở trang CCTV và để AI chạy.";
    } else {
      emptyEl.textContent = "Chưa phát hiện Thợ săn. Hãy mở trang CCTV và để AI chạy.";
    }
  }

  renderEvents(filtered);
}

async function refresh() {
  const btn = document.getElementById("refresh-now");
  btn.disabled = true;
  try {
    const data = await fetchEvents(50);
    currentEvents = Array.isArray(data.events) ? data.events : [];
    updateSummary(currentEvents);
    updateLatestVideo(currentEvents);
    renderFilteredEvents();
  } catch (e) {
    console.warn("Refresh failed:", e);
  } finally {
    btn.disabled = false;
  }
}

function startAutoRefresh() {
  if (refreshTimer) clearInterval(refreshTimer);
  refreshTimer = setInterval(refresh, 5000);
}

window.addEventListener("DOMContentLoaded", () => {
  document.getElementById("refresh-now").addEventListener("click", refresh);

  // Tab buttons click listeners
  const tabBtns = document.querySelectorAll(".tab-btn");
  tabBtns.forEach((btn) => {
    btn.addEventListener("click", () => {
      tabBtns.forEach((b) => b.classList.remove("active"));
      btn.classList.add("active");
      activeTab = btn.getAttribute("data-tab");
      renderFilteredEvents();
    });
  });

  const clearBtn = document.getElementById("clear-events");
  if (clearBtn) {
    clearBtn.addEventListener("click", async () => {
      if (!confirm("Xóa toàn bộ lịch sử (ảnh + video) và làm trống danh sách?")) return;
      try {
        await clearAllHistory();
        await refresh();
      } catch (e) {
        alert(e?.message || String(e));
      }
    });
  }

  refresh();
  startAutoRefresh();
});
