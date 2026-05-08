const $ = (selector) => document.querySelector(selector);

const fields = {
  visionMode: $("#visionMode"),
  profileSelect: $("#profileSelect"),
  cameraHotkey: $("#cameraHotkey"),
  controlHotkey: $("#controlHotkey"),
  featureScroll: $("#featureScroll"),
  featureCursor: $("#featureCursor"),
  featureZoom: $("#featureZoom"),
  featureAirMouse: $("#featureAirMouse"),
  featureDrag: $("#featureDrag"),
  featureFace: $("#featureFace"),
  featureBody: $("#featureBody"),
  scrollSpeed: $("#scrollSpeed"),
  scrollStep: $("#scrollStep"),
  cursorSpeed: $("#cursorSpeed"),
  trajectorySeconds: $("#trajectorySeconds"),
  faceBlink: $("#faceBlink"),
  faceSmile: $("#faceSmile"),
  bodySeconds: $("#bodySeconds"),
  cameraIndex: $("#cameraIndex"),
  mirror: $("#mirror"),
  controlStart: $("#controlStart"),
  actionOpenUp: $("#actionOpenUp"),
  actionOpenDown: $("#actionOpenDown"),
  actionOpenLeft: $("#actionOpenLeft"),
  actionOpenRight: $("#actionOpenRight"),
  actionPinch: $("#actionPinch"),
  actionBothPinch: $("#actionBothPinch"),
  actionFistCloser: $("#actionFistCloser"),
  actionFistAway: $("#actionFistAway"),
  actionTwoHandsApart: $("#actionTwoHandsApart"),
  actionTwoHandsTogether: $("#actionTwoHandsTogether"),
  actionSplitVertical: $("#actionSplitVertical"),
};

const labels = {
  status: $("#saveStatus"),
  runtime: $("#runtimeStatus"),
  scrollSpeed: $("#scrollSpeedValue"),
  scrollStep: $("#scrollStepValue"),
  cursorSpeed: $("#cursorSpeedValue"),
  trajectorySeconds: $("#trajectorySecondsValue"),
  faceBlink: $("#faceBlinkValue"),
  faceSmile: $("#faceSmileValue"),
  bodySeconds: $("#bodySecondsValue"),
};

const metrics = {
  gesture: $("#metricGesture"),
  action: $("#metricAction"),
  face: $("#metricFace"),
  body: $("#metricBody"),
  fps: $("#metricFps"),
};

let currentConfig = null;

const actionOptions = [
  ["none", "Sin accion"],
  ["scroll_up", "Scroll arriba"],
  ["scroll_down", "Scroll abajo"],
  ["scroll_left", "Scroll izquierda"],
  ["scroll_right", "Scroll derecha"],
  ["cursor_left", "Cursor izquierda"],
  ["cursor_right", "Cursor derecha"],
  ["cursor_up", "Cursor arriba"],
  ["cursor_down", "Cursor abajo"],
  ["cursor_up_left", "Cursor diagonal sup. izq."],
  ["cursor_up_right", "Cursor diagonal sup. der."],
  ["cursor_down_left", "Cursor diagonal inf. izq."],
  ["cursor_down_right", "Cursor diagonal inf. der."],
  ["click", "Click"],
  ["right_click", "Click derecho"],
  ["double_click", "Doble click"],
  ["drag", "Drag con pinza"],
  ["zoom_in", "Zoom in"],
  ["zoom_out", "Zoom out"],
  ["close_window", "Cerrar ventana"],
  ["show_desktop", "Ver escritorio"],
  ["alt_tab", "Cambiar ventana"],
  ["escape", "Escape"],
  ["enter", "Enter"],
  ["next_slide", "Siguiente slide"],
  ["prev_slide", "Anterior slide"],
  ["play_pause", "Play / pause"],
  ["volume_up", "Volumen +"],
  ["volume_down", "Volumen -"],
  ["mute", "Mute"],
  ["media_next", "Media siguiente"],
  ["media_prev", "Media anterior"],
];

for (const select of document.querySelectorAll(".actions-grid select")) {
  for (const [value, label] of actionOptions) {
    const option = document.createElement("option");
    option.value = value;
    option.textContent = label;
    select.append(option);
  }
}

async function loadConfig() {
  const response = await fetch("/api/config");
  currentConfig = await response.json();
  renderConfig(currentConfig);
  await refreshStatus();
}

function renderConfig(config) {
  fields.visionMode.value = config.vision_mode || "GESTURE";
  fields.profileSelect.value = config.current_profile || "navigation";
  fields.cameraHotkey.value = config.camera_hotkey || "E+R";
  fields.controlHotkey.value = config.control_hotkey || "D+F";
  fields.featureScroll.checked = Boolean(config.features?.scroll);
  fields.featureCursor.checked = Boolean(config.features?.cursor);
  fields.featureZoom.checked = Boolean(config.features?.zoom);
  fields.featureAirMouse.checked = Boolean(config.features?.air_mouse);
  fields.featureDrag.checked = Boolean(config.features?.drag);
  fields.featureFace.checked = Boolean(config.features?.face);
  fields.featureBody.checked = Boolean(config.features?.body);
  fields.scrollSpeed.value = config.scroll?.speed ?? 2112;
  fields.scrollStep.value = config.scroll?.max_step ?? 12;
  fields.cursorSpeed.value = config.cursor?.speed ?? 45;
  fields.trajectorySeconds.value = config.trajectory?.seconds ?? 4;
  fields.faceBlink.value = config.face?.blink_threshold ?? 0.018;
  fields.faceSmile.value = config.face?.smile_threshold ?? 3.2;
  fields.bodySeconds.value = config.body?.trajectory_seconds ?? 6;
  fields.cameraIndex.value = config.camera ?? 0;
  fields.mirror.checked = Boolean(config.mirror);
  fields.controlStart.checked = Boolean(config.control_enabled_on_start);
  fields.actionOpenUp.value = config.actions?.open_up || "scroll_up";
  fields.actionOpenDown.value = config.actions?.open_down || "scroll_down";
  fields.actionOpenLeft.value = config.actions?.open_left || "cursor_left";
  fields.actionOpenRight.value = config.actions?.open_right || "cursor_right";
  fields.actionPinch.value = config.actions?.pinch || "click";
  fields.actionBothPinch.value = config.actions?.both_pinch || "double_click";
  fields.actionFistCloser.value = config.actions?.fist_closer || "zoom_in";
  fields.actionFistAway.value = config.actions?.fist_away || "zoom_out";
  fields.actionTwoHandsApart.value = config.actions?.two_hands_apart || "zoom_in";
  fields.actionTwoHandsTogether.value = config.actions?.two_hands_together || "zoom_out";
  fields.actionSplitVertical.value = config.actions?.split_vertical || "show_desktop";
  updateLabels();
}

function readConfig() {
  return {
    ...currentConfig,
    app_name: "OPENGESTURE",
    vision_mode: fields.visionMode.value,
    current_profile: fields.profileSelect.value,
    camera_hotkey: normalizeHotkey(fields.cameraHotkey.value),
    control_hotkey: normalizeHotkey(fields.controlHotkey.value),
    camera: Number(fields.cameraIndex.value),
    mirror: fields.mirror.checked,
    control_enabled_on_start: fields.controlStart.checked,
    features: {
      ...(currentConfig.features || {}),
      scroll: fields.featureScroll.checked,
      cursor: fields.featureCursor.checked,
      zoom: fields.featureZoom.checked,
      air_mouse: fields.featureAirMouse.checked,
      drag: fields.featureDrag.checked,
      face: fields.featureFace.checked,
      body: fields.featureBody.checked,
      voice: true,
    },
    scroll: {
      ...(currentConfig.scroll || {}),
      speed: Number(fields.scrollSpeed.value),
      max_step: Number(fields.scrollStep.value),
    },
    cursor: {
      ...(currentConfig.cursor || {}),
      speed: Number(fields.cursorSpeed.value),
    },
    trajectory: {
      ...(currentConfig.trajectory || {}),
      seconds: Number(fields.trajectorySeconds.value),
      finger_trails: true,
      hand_trails: true,
      body_trails: true,
    },
    face: {
      ...(currentConfig.face || {}),
      enabled: fields.featureFace.checked,
      blink_threshold: Number(fields.faceBlink.value),
      smile_threshold: Number(fields.faceSmile.value),
    },
    body: {
      ...(currentConfig.body || {}),
      enabled: fields.featureBody.checked,
      trajectory_seconds: Number(fields.bodySeconds.value),
    },
    actions: {
      ...(currentConfig.actions || {}),
      open_up: fields.actionOpenUp.value,
      open_down: fields.actionOpenDown.value,
      open_left: fields.actionOpenLeft.value,
      open_right: fields.actionOpenRight.value,
      pinch: fields.actionPinch.value,
      both_pinch: fields.actionBothPinch.value,
      fist_closer: fields.actionFistCloser.value,
      fist_away: fields.actionFistAway.value,
      two_hands_apart: fields.actionTwoHandsApart.value,
      two_hands_together: fields.actionTwoHandsTogether.value,
      split_vertical: fields.actionSplitVertical.value,
    },
  };
}

function normalizeHotkey(value) {
  return value.toUpperCase().replace(/\s+/g, "");
}

function updateLabels() {
  labels.scrollSpeed.textContent = `${fields.scrollSpeed.value}/s`;
  labels.scrollStep.textContent = `${fields.scrollStep.value}/frame`;
  labels.cursorSpeed.textContent = `${fields.cursorSpeed.value}px/s`;
  labels.trajectorySeconds.textContent = `${fields.trajectorySeconds.value}s`;
  labels.faceBlink.textContent = fields.faceBlink.value;
  labels.faceSmile.textContent = fields.faceSmile.value;
  labels.bodySeconds.textContent = `${fields.bodySeconds.value}s`;
}

async function saveConfig() {
  labels.status.textContent = "Guardando";
  const response = await fetch("/api/config", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(readConfig()),
  });
  const result = await response.json();
  if (!response.ok) {
    labels.status.textContent = "Error";
    alert(result.error || "No se pudo guardar.");
    return;
  }
  currentConfig = result.config;
  renderConfig(currentConfig);
  labels.status.textContent = "Guardado";
  setTimeout(() => (labels.status.textContent = "Listo"), 1300);
}

async function refreshStatus() {
  const response = await fetch("/api/status");
  const status = await response.json();
  const runtime = status.runtime || {};
  const face = runtime.face || {};
  const body = runtime.body || {};
  labels.runtime.textContent = `${status.visualizerRunning ? "Camara ON" : "Camara OFF"} · ${status.controlEnabled ? "Control ON" : "Control OFF"} · ${runtime.vision_mode || "GESTURE"}`;
  metrics.gesture.textContent = runtime.gesture || "NO_HAND";
  metrics.action.textContent = runtime.action || "waiting";
  metrics.face.textContent = face.detected ? `${face.gaze} · ${face.smile ? "smile" : "neutral"}` : "sin cara";
  metrics.body.textContent = body.detected ? body.motion : "idle";
  metrics.fps.textContent = `${runtime.fps || 0} FPS`;
  $("#toggleVisualizer").textContent = status.visualizerRunning ? "Apagar camara" : "Activar camara";
  $("#toggleControl").textContent = status.controlEnabled ? "Apagar control" : "Activar control";
}

async function postAction(url) {
  labels.runtime.textContent = "Aplicando";
  await fetch(url, { method: "POST" });
  await refreshStatus();
}

$("#saveButton").addEventListener("click", saveConfig);
$("#toggleVisualizer").addEventListener("click", () => postAction("/api/visualizer/toggle"));
$("#toggleControl").addEventListener("click", () => postAction("/api/control/toggle"));
$("#padClick").addEventListener("click", () => postAction("/api/mouse/click"));
$("#padRightClick").addEventListener("click", () => postAction("/api/mouse/right-click"));
$("#voiceButton").addEventListener("click", startVoiceCommand);
fields.visionMode.addEventListener("change", saveConfig);
fields.profileSelect.addEventListener("change", async () => {
  await fetch("/api/profile", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ profile: fields.profileSelect.value }),
  });
  await loadConfig();
});

document.querySelectorAll(".calibration").forEach((button) => {
  button.addEventListener("click", async () => {
    labels.status.textContent = "Calibrando";
    await fetch("/api/calibration/request", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ label: button.dataset.label }),
    });
    setTimeout(() => (labels.status.textContent = "Listo"), 1600);
  });
});

Object.values(fields).forEach((field) => field?.addEventListener("input", updateLabels));

const cameraPreview = $("#cameraPreview");
setInterval(() => {
  cameraPreview.src = `/api/frame.jpg?t=${Date.now()}`;
}, 250);

const touchPad = $("#touchPad");
let padPointer = null;
let lastPoint = null;
let lastMoveAt = 0;

touchPad.addEventListener("pointerdown", (event) => {
  padPointer = event.pointerId;
  lastPoint = { x: event.clientX, y: event.clientY };
  touchPad.setPointerCapture(padPointer);
  touchPad.classList.add("active");
});

touchPad.addEventListener("pointermove", (event) => {
  if (event.pointerId !== padPointer || !lastPoint) return;
  const now = performance.now();
  if (now - lastMoveAt < 18) return;
  const dx = Math.round((event.clientX - lastPoint.x) * 1.8);
  const dy = Math.round((event.clientY - lastPoint.y) * 1.8);
  lastPoint = { x: event.clientX, y: event.clientY };
  lastMoveAt = now;
  if (dx === 0 && dy === 0) return;
  fetch("/api/mouse/move", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ dx, dy }),
  }).catch(() => {});
});

touchPad.addEventListener("pointerup", endPad);
touchPad.addEventListener("pointercancel", endPad);

function endPad() {
  padPointer = null;
  lastPoint = null;
  touchPad.classList.remove("active");
}

function startVoiceCommand() {
  const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
  const voiceStatus = $("#voiceStatus");
  if (!SpeechRecognition) {
    voiceStatus.textContent = "Voz no disponible en este navegador. En movil suele funcionar mejor con Chrome.";
    return;
  }
  const recognition = new SpeechRecognition();
  recognition.lang = currentConfig?.voice?.language || "es-ES";
  recognition.interimResults = false;
  recognition.onstart = () => (voiceStatus.textContent = "Escuchando desde este dispositivo...");
  recognition.onresult = async (event) => {
    const text = event.results[0][0].transcript;
    voiceStatus.textContent = text;
    await fetch("/api/voice/command", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text }),
    });
    await loadConfig();
  };
  recognition.onerror = () => {
    voiceStatus.textContent = "No se pudo reconocer voz.";
  };
  recognition.start();
}

setInterval(refreshStatus, 1600);
loadConfig().catch((error) => {
  labels.status.textContent = "Error";
  console.error(error);
});
