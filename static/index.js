let img;
let canvas;
let ctx;
let isModelLoaded = false;
let lastDetections = [];
let isPredicting = false;

// Audio alerts
const amThanhTeTe = new Audio("/static/sound/Phat_hien_te_te.mp3");
let dangPhatTeTe = false;

// Upload/throttle state
let isUploadingEvent = false;
const lastEventAtByType = new Map(); // event_type -> epoch ms

async function startIPCamera() {
  try {
    isModelLoaded = true;

    img = document.getElementById("ipcam");
    canvas = document.getElementById("canvas");
    ctx = canvas.getContext("2d");

    labelContainer = document.getElementById("label-container");
    labelContainer.innerHTML = "";

    // Start loops
    renderLoop();
    predictionLoop();
  } catch (error) {
    console.error("Khong the khoi dong camera:", error);
    const el = document.getElementById("label-container");
    if (el) el.textContent = "Loi: khong khoi dong duoc camera.";
  }
}

function renderLoop() {
  if (img && img.complete && img.naturalWidth !== 0) {
    ctx.drawImage(img, 0, 0, canvas.width, canvas.height);
    drawDetections();
  } else {
    // Clear canvas and show loading message if stream not active
    ctx.fillStyle = "#1a2e11";
    ctx.fillRect(0, 0, canvas.width, canvas.height);
    ctx.fillStyle = "white";
    ctx.font = "16px Arial";
    ctx.textAlign = "center";
    ctx.fillText("⏳ Đang tải luồng video...", canvas.width / 2, canvas.height / 2);
  }
  requestAnimationFrame(renderLoop);
}

async function predictionLoop() {
  if (isModelLoaded && !isPredicting) {
    isPredicting = true;
    try {
      await predict();
    } catch (e) {
      console.error("Loi khi chay du doan:", e);
    } finally {
      isPredicting = false;
    }
  }
  setTimeout(predictionLoop, 150); // ~7 FPS
}

async function predict() {
  if (!canvas) return;

  const blob = await new Promise((resolve) => {
    try {
      canvas.toBlob((b) => resolve(b), "image/jpeg", 0.85);
    } catch (e) {
      console.warn("Khong the capture canvas blob:", e);
      resolve(null);
    }
  });

  if (!blob) return;

  const formData = new FormData();
  formData.append("image", blob, "frame.jpg");

  const res = await fetch("/api/predict", {
    method: "POST",
    body: formData
  });

  if (!res.ok) {
    throw new Error(`HTTP error! status: ${res.status}`);
  }

  const data = await res.json();
  lastDetections = data.detections || [];
  processDetections(lastDetections);
}

function drawDetections() {
  if (!lastDetections || lastDetections.length === 0) return;

  ctx.lineWidth = 3;
  ctx.font = "bold 14px Arial";
  ctx.textBaseline = "top";
  ctx.textAlign = "left";

  lastDetections.forEach((det) => {
    const [x1, y1, x2, y2] = det.box;
    const conf = det.confidence;
    const label = det.label_vi || (det.class === "masked palm civet" ? "Cầy vòi mốc" : det.class === "pangolin" ? "Tê Tê" : det.class);
    const clsLower = (det.class || "").toLowerCase();
    const isCivet = clsLower.includes("civet") || clsLower.includes("masked") || clsLower.includes("cầy");

    // Colors: Green for Pangolin, Amber for Masked Palm Civet
    const strokeColor = isCivet ? "#ffb74d" : "#8bc34a";
    const bgColor = isCivet ? "rgba(255, 183, 77, 0.85)" : "rgba(139, 195, 74, 0.85)";

    ctx.strokeStyle = strokeColor;
    ctx.strokeRect(x1, y1, x2 - x1, y2 - y1);

    const text = `${label} (${Math.round(conf * 100)}%)`;
    const textWidth = ctx.measureText(text).width;
    ctx.fillStyle = bgColor;
    ctx.fillRect(x1 - 1, Math.max(0, y1 - 24), textWidth + 10, 22);

    ctx.fillStyle = "#0b1a03";
    ctx.fillText(text, x1 + 4, Math.max(4, y1 - 20));
  });
}

let dangPhatCivet = false;

function processDetections(detections) {
  const teteDets = detections.filter((d) => {
    const cls = (d.class || "").toLowerCase();
    return (
      cls.includes("tete") ||
      cls.includes("te_te") ||
      cls.includes("pangolin") ||
      cls.includes("tê tê") ||
      cls.includes("tê_tê") ||
      d.class === "0"
    );
  });

  const civetDets = detections.filter((d) => {
    const cls = (d.class || "").toLowerCase();
    return (
      cls.includes("civet") ||
      cls.includes("masked") ||
      cls.includes("cầy") ||
      cls.includes("cay_voi_moc")
    );
  });

  const labelContainer = document.getElementById("label-container");
  if (!labelContainer) return;

  let htmlParts = [];

  if (teteDets.length > 0) {
    const maxConf = Math.max(...teteDets.map((d) => d.confidence));
    htmlParts.push(`<span style="color: var(--accent-green); font-size: 18px; margin-right: 15px; text-shadow: 0 0 10px rgba(139, 195, 74, 0.5);">🌿 Phát hiện Tê Tê (${Math.round(maxConf * 100)}%)</span>`);
    playAudioOnce("tete");
    maybeCaptureAndUploadEvent("TeTe", maxConf);
  } else {
    dangPhatTeTe = false;
  }

  if (civetDets.length > 0) {
    const maxConf = Math.max(...civetDets.map((d) => d.confidence));
    htmlParts.push(`<span style="color: #ffb74d; font-size: 18px; text-shadow: 0 0 10px rgba(255, 183, 77, 0.5);">🦡 Phát hiện Cầy Vòi Mốc (${Math.round(maxConf * 100)}%)</span>`);
    playAudioOnce("civet");
    maybeCaptureAndUploadEvent("CayVoiMoc", maxConf);
  } else {
    dangPhatCivet = false;
  }

  labelContainer.innerHTML = htmlParts.join("");
}

function playAudioOnce(type) {
  if (type === "tete" && !dangPhatTeTe) {
    dangPhatTeTe = true;
    amThanhTeTe.play().catch(() => {});
    amThanhTeTe.onended = () => {
      dangPhatTeTe = false;
    };
  } else if (type === "civet" && !dangPhatCivet) {
    dangPhatCivet = true;
    amThanhTeTe.play().catch(() => {});
    amThanhTeTe.onended = () => {
      dangPhatCivet = false;
    };
  }
}

function canSendEventNow(eventType) {
  const now = Date.now();
  const last = lastEventAtByType.get(eventType) ?? 0;
  return now - last >= 15000; // throttle 15s per type
}

async function captureSnapshotBlob() {
  if (!canvas) return null;

  return new Promise((resolve) => {
    try {
      canvas.toBlob((blob) => resolve(blob), "image/jpeg", 0.9);
    } catch (e) {
      console.warn("Khong the chup anh (canvas bi taint?)", e);
      resolve(null);
    }
  });
}

async function recordClipBlob(durationMs = 8000) {
  if (!("MediaRecorder" in window) || !canvas?.captureStream) return null;

  let stream;
  try {
    stream = canvas.captureStream(15);
  } catch (e) {
    console.warn("Khong the captureStream()", e);
    return null;
  }

  let recorder;
  try {
    recorder = new MediaRecorder(stream);
  } catch (e) {
    console.warn("Khong the tao MediaRecorder", e);
    try {
      stream.getTracks().forEach((t) => t.stop());
    } catch (_) {}
    return null;
  }

  const chunks = [];
  recorder.ondataavailable = (ev) => {
    if (ev.data && ev.data.size > 0) chunks.push(ev.data);
  };

  const stopped = new Promise((resolve) => {
    recorder.onstop = () => resolve();
    recorder.onerror = () => resolve();
  });

  recorder.start();
  setTimeout(() => {
    try {
      recorder.stop();
    } catch (_) {}
    try {
      stream.getTracks().forEach((t) => t.stop());
    } catch (_) {}
  }, durationMs);

  await stopped;
  if (!chunks.length) return null;
  return new Blob(chunks, { type: recorder.mimeType || "video/webm" });
}

async function maybeCaptureAndUploadEvent(eventType, probability) {
  if (isUploadingEvent) return;
  if (!canSendEventNow(eventType)) return;

  isUploadingEvent = true;
  lastEventAtByType.set(eventType, Date.now());

  try {
    const snapshotBlob = await captureSnapshotBlob();
    const videoBlob = await recordClipBlob(8000);

    const form = new FormData();
    form.append("event_type", eventType);
    form.append("probability", String(probability ?? ""));
    form.append("source", "CCTV");

    if (snapshotBlob) form.append("snapshot", snapshotBlob, "snapshot.jpg");
    if (videoBlob) form.append("video", videoBlob, "clip.webm");

    const res = await fetch("/api/events", { method: "POST", body: form });
    if (!res.ok) console.warn("Upload event that bai:", res.status, await res.text());
  } catch (e) {
    console.warn("Loi khi upload event:", e);
  } finally {
    isUploadingEvent = false;
  }
}

// Browser audio often needs a user gesture
window.addEventListener(
  "click",
  () => {
    // no-op; just ensures user interaction happened
  },
  { once: true }
);

window.addEventListener("DOMContentLoaded", startIPCamera);
