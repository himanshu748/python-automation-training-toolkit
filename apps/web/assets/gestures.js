import {
  FilesetResolver,
  GestureRecognizer,
} from "https://cdn.jsdelivr.net/npm/@mediapipe/tasks-vision@0.10.18";

const video = document.getElementById("gesture-video");
const canvas = document.getElementById("gesture-canvas");
const ctx = canvas.getContext("2d");
const startButton = document.getElementById("gesture-start");
const stopButton = document.getElementById("gesture-stop");
const emptyState = document.getElementById("gesture-empty");
const statusEl = document.getElementById("gesture-status");
const handCountEl = document.getElementById("gesture-hand-count");
const fpsEl = document.getElementById("gesture-fps");
const listEl = document.getElementById("gesture-list");
const outputEl = document.getElementById("gesture-output");

const HAND_CONNECTIONS = [
  [0, 1], [1, 2], [2, 3], [3, 4],
  [0, 5], [5, 6], [6, 7], [7, 8],
  [5, 9], [9, 10], [10, 11], [11, 12],
  [9, 13], [13, 14], [14, 15], [15, 16],
  [13, 17], [0, 17], [17, 18], [18, 19], [19, 20],
];

let recognizer;
let stream;
let rafId;
let running = false;
let lastVideoTime = -1;
let lastFrameTime = performance.now();

function setStatus(text, detail = "") {
  statusEl.textContent = text;
  outputEl.textContent = detail || text;
}

function resizeCanvas() {
  const rect = canvas.getBoundingClientRect();
  const width = Math.max(1, Math.round(rect.width * window.devicePixelRatio));
  const height = Math.max(1, Math.round(rect.height * window.devicePixelRatio));
  if (canvas.width !== width || canvas.height !== height) {
    canvas.width = width;
    canvas.height = height;
  }
}

function drawLandmarks(landmarks) {
  const width = canvas.width;
  const height = canvas.height;
  ctx.lineCap = "round";
  ctx.lineJoin = "round";

  for (const [start, end] of HAND_CONNECTIONS) {
    const a = landmarks[start];
    const b = landmarks[end];
    if (!a || !b) continue;
    ctx.beginPath();
    ctx.moveTo(a.x * width, a.y * height);
    ctx.lineTo(b.x * width, b.y * height);
    ctx.strokeStyle = "rgba(34, 211, 238, 0.9)";
    ctx.lineWidth = Math.max(3, width / 360);
    ctx.stroke();
  }

  for (const point of landmarks) {
    ctx.beginPath();
    ctx.arc(point.x * width, point.y * height, Math.max(4, width / 220), 0, Math.PI * 2);
    ctx.fillStyle = "rgba(232, 121, 249, 0.95)";
    ctx.fill();
    ctx.lineWidth = 2;
    ctx.strokeStyle = "rgba(255,255,255,.85)";
    ctx.stroke();
  }
}

function renderResults(results) {
  resizeCanvas();
  ctx.clearRect(0, 0, canvas.width, canvas.height);
  const landmarks = results.landmarks || [];
  const gestures = results.gestures || [];
  handCountEl.textContent = String(landmarks.length);

  landmarks.forEach(drawLandmarks);

  if (!landmarks.length) {
    listEl.textContent = "No hands detected. Raise one or both hands into view.";
    return;
  }

  listEl.innerHTML = gestures.map((items, index) => {
    const best = items[0];
    const label = best?.categoryName || "Unknown";
    const score = Math.round((best?.score || 0) * 100);
    return `
      <div class="rounded-lg border border-fuchsia-100 bg-fuchsia-50 px-3 py-2">
        <div class="flex items-center justify-between gap-3">
          <span class="font-semibold text-slate-950">Hand ${index + 1}</span>
          <span class="rounded-md bg-white px-2 py-1 text-xs font-medium text-fuchsia-700">${score}%</span>
        </div>
        <div class="mt-1 text-lg font-semibold text-fuchsia-800">${label}</div>
      </div>`;
  }).join("");

  const summary = gestures
    .map((items, index) => `Hand ${index + 1}: ${items[0]?.categoryName || "Unknown"} (${Math.round((items[0]?.score || 0) * 100)}%)`)
    .join("\n");
  outputEl.textContent = `Status: tracking\n\n${summary}`;
}

async function ensureRecognizer() {
  if (recognizer) return recognizer;
  setStatus("Loading", "Loading MediaPipe gesture model...");
  const vision = await FilesetResolver.forVisionTasks(
    "https://cdn.jsdelivr.net/npm/@mediapipe/tasks-vision@0.10.18/wasm"
  );
  recognizer = await GestureRecognizer.createFromOptions(vision, {
    baseOptions: {
      modelAssetPath:
        "https://storage.googleapis.com/mediapipe-models/gesture_recognizer/gesture_recognizer/float16/1/gesture_recognizer.task",
      delegate: "GPU",
    },
    runningMode: "VIDEO",
    numHands: 2,
  });
  return recognizer;
}

async function predict() {
  if (!running) return;
  if (video.currentTime !== lastVideoTime) {
    lastVideoTime = video.currentTime;
    const now = performance.now();
    const results = recognizer.recognizeForVideo(video, now);
    renderResults(results);
    const elapsed = now - lastFrameTime;
    lastFrameTime = now;
    fpsEl.textContent = elapsed > 0 ? String(Math.round(1000 / elapsed)) : "0";
  }
  rafId = requestAnimationFrame(predict);
}

async function startCamera() {
  try {
    startButton.disabled = true;
    await ensureRecognizer();
    stream = await navigator.mediaDevices.getUserMedia({
      video: { width: { ideal: 1280 }, height: { ideal: 720 }, facingMode: "user" },
      audio: false,
    });
    video.srcObject = stream;
    await video.play();
    emptyState.classList.add("hidden");
    running = true;
    lastFrameTime = performance.now();
    setStatus("Tracking", "Camera is live. Show one or both hands.");
    predict();
  } catch (error) {
    setStatus("Failed", `Could not start browser camera.\n\n${error.message}`);
    startButton.disabled = false;
  }
}

function stopCamera() {
  running = false;
  if (rafId) cancelAnimationFrame(rafId);
  if (stream) {
    stream.getTracks().forEach((track) => track.stop());
  }
  stream = undefined;
  video.srcObject = null;
  ctx.clearRect(0, 0, canvas.width, canvas.height);
  emptyState.classList.remove("hidden");
  startButton.disabled = false;
  handCountEl.textContent = "0";
  fpsEl.textContent = "0";
  listEl.textContent = "No hands detected yet.";
  setStatus("Idle", "Camera stopped.");
}

startButton.addEventListener("click", startCamera);
stopButton.addEventListener("click", stopCamera);
window.addEventListener("resize", resizeCanvas);
resizeCanvas();
