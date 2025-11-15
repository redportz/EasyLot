import os, time, threading, json
import cv2, numpy as np
from flask import Flask, jsonify, abort, Response
from flask_cors import CORS
from ultralytics import YOLO
import requests

# ---------------- Config ----------------
MODEL_PATH = "yolov8s.pt"
FRAME_W, FRAME_H = 1280, 720
POLL_INTERVAL = 10  # seconds between DB checks
API_BASE = "http://127.0.0.1:5001"  # DB API

# ---------------- App ----------------
app = Flask(__name__)
CORS(app)

# ---------------- State ----------------
lot_workers = {}

# ---------------- Threaded Camera ----------------
class ThreadedCamera:
    """Background thread that keeps the latest frame from a VideoCapture object."""
    def __init__(self, src, fps=30):
        self.capture = cv2.VideoCapture(src)
        self.capture.set(cv2.CAP_PROP_BUFFERSIZE, 2)
        self.FPS = 1 / fps
        self.frame = None
        self.status = False
        t = threading.Thread(target=self.update, daemon=True)
        t.start()

    def update(self):
        while True:
            if self.capture.isOpened():
                self.status, self.frame = self.capture.read()
            time.sleep(self.FPS)

    def get_frame(self):
        return self.frame if self.status else None

# ---------------- Helpers ----------------
def load_polygons_from_db(lot_id):
    polygons = []
    spot_ids = []
    try:
        r = requests.get(f"{API_BASE}/lots/{lot_id}/spots")
        r.raise_for_status()
        spots = r.json()
        for spot in spots:
            spot_id = spot["id"]
            spot_ids.append(spot_id)
            r2 = requests.get(f"{API_BASE}/spots/{spot_id}/polygon")
            if r2.status_code == 200:
                pts = r2.json().get("points")
                polygons.append(pts if pts else [])
            else:
                polygons.append([])
    except Exception as e:
        print(f"[LOT {lot_id}] Error loading polygons:", e)
    return polygons, spot_ids


def update_spot_status(spot_id, status):
    """Push the detected spot status back into DB."""
    try:
        requests.put(
            f"{API_BASE}/spots/{spot_id}/status",
            json={"status": status},
            timeout=3
        )
    except Exception as e:
        print(f"Failed to update spot {spot_id}: {e}")

# ---------------- Worker ----------------
def get_is_upside_down(lot_id):
    """Fetch whether the given lot's video should be flipped upside down."""
    try:
        r = requests.get(f"{API_BASE}/lots/{lot_id}")
        r.raise_for_status()
        lot = r.json()
        return bool(lot.get("is_video_upside_down", False))
    except Exception as e:
        print(f"[LOT {lot_id}] Could not fetch is_video_upside_down: {e}")
        return False

def lot_worker(lot_id, live_url):
    print(f"[LOT {lot_id}] Starting worker for {live_url}")

    if lot_id not in lot_workers:
        lot_workers[lot_id] = {
            "thread": None,
            "state": {
                "latest_counts": {"free": 0, "full": 0, "total": 0},
                "latest_jpeg": None,
                "latest_frame": None,
                "jpeg_lock": threading.Lock(),
                "running": True
            }
        }

    state = lot_workers[lot_id]["state"]
    model = YOLO(MODEL_PATH)
    cam = ThreadedCamera(live_url, fps=30)

    is_upside_down = get_is_upside_down(lot_id)
    encode_params = [int(cv2.IMWRITE_JPEG_QUALITY), 80]
    polygons, spot_ids = load_polygons_from_db(lot_id)
    last_poly_check = 0
    last_detection = 0
    detection_interval = 30  # seconds

    while state["running"]:
        frame = cam.get_frame()
        if frame is None:
            time.sleep(0.02)
            continue

        if is_upside_down:
            frame = cv2.rotate(frame, cv2.ROTATE_180)
        frame_resized = cv2.resize(frame, (FRAME_W, FRAME_H))

        # Always store the latest frame for the video feed
        with state["jpeg_lock"]:
            ok, jpg = cv2.imencode(".jpg", frame_resized, encode_params)
            if ok:
                state["latest_jpeg"] = jpg.tobytes()
            state["latest_frame"] = frame_resized.copy()

        now = time.time()
        # Update polygons every 10s
        if now - last_poly_check > 10:
            polygons, spot_ids = load_polygons_from_db(lot_id)
            is_upside_down = get_is_upside_down(lot_id)
            last_poly_check = now

        # Run YOLO only every detection_interval
        if now - last_detection > detection_interval and state["latest_frame"] is not None:
            frame_for_detection = state["latest_frame"].copy()
            total_spots = len(polygons)
            filled_status = ["empty"] * total_spots

            results = model.track(frame_for_detection, persist=True, classes=[2, 7], conf=0.25)
            if results and results[0].boxes.id is not None:
                boxes = results[0].boxes.xyxy.cpu().numpy().astype(int)
                for (x1, y1, x2, y2) in boxes:
                    corners = [(x1, y1), (x2, y1), (x2, y2), (x1, y2), ((x1+x2)//2, (y1+y2)//2)]
                    for i, poly in enumerate(polygons):
                        if not poly:
                            continue
                        pts = np.array(poly, np.int32).reshape((-1, 1, 2))
                        if any(cv2.pointPolygonTest(pts, (float(px), float(py)), False) >= 0 for (px, py) in corners):
                            if filled_status[i] == "empty":
                                filled_status[i] = "full"
                            break

            # Update DB
            for i, spot_id in enumerate(spot_ids):
                update_spot_status(spot_id, filled_status[i])

            with state["jpeg_lock"]:
                state["filled_status"] = filled_status
                state["spot_ids"] = spot_ids
                state["latest_counts"] = {
                    "free": filled_status.count("empty"),
                    "full": filled_status.count("full"),
                    "total": total_spots
                }

            last_detection = now

# ---------------- Orchestrator ----------------
def orchestrator():
    while True:
        try:
            lots = requests.get(f"{API_BASE}/lots").json()
            for lot in lots:
                lot_id = lot["id"]
                live_url = lot["live_feed_url"]
                if lot_id not in lot_workers:
                    lot_workers[lot_id] = {
                        "thread": None,
                        "state": {
                            "latest_counts": {"free": 0, "full": 0, "total": 0},
                            "latest_jpeg": None,
                            "jpeg_lock": threading.Lock(),
                            "running": True
                        }
                    }
                    t = threading.Thread(target=lot_worker, args=(lot_id, live_url), daemon=True)
                    t.start()
                    lot_workers[lot_id]["thread"] = t
        except Exception as e:
            print("Orchestrator error:", e)
        time.sleep(POLL_INTERVAL)

threading.Thread(target=orchestrator, daemon=True).start()

# ---------------- Endpoints ----------------
@app.route("/")
def index():
    return (
        "<h2>EasyLot Orchestrator</h2><ul>"
        + "".join([
            f"<li><a href='/video_feed/{lid}'>Video Feed {lid}</a></li>"
            f"<li><a href='/stats/{lid}'>Stats {lid}</a></li>"
            for lid in lot_workers.keys()
        ])
        + "</ul>"
    )

@app.route("/video_feed/<int:lot_id>")
def video_feed(lot_id):
    if lot_id not in lot_workers:
        abort(404, "Lot not found")

    state = lot_workers[lot_id]["state"]
    while "jpeg_lock" not in state:
        time.sleep(0.05)

    def gen():
        while True:
            with state["jpeg_lock"]:
                buf = state["latest_jpeg"]
                if buf is None:
                    time.sleep(0.02)
                    continue
                yield b"--frame\r\nContent-Type: image/jpeg\r\n\r\n" + buf + b"\r\n"

    return Response(gen(), mimetype="multipart/x-mixed-replace; boundary=frame")

@app.route("/stats/<int:lot_id>")
def stats(lot_id):
    if lot_id not in lot_workers:
        abort(404, "Lot not found")

    state = lot_workers[lot_id]["state"]
    if "spot_ids" not in state or "filled_status" not in state:
        return jsonify({"spots": [], "counts": state.get("latest_counts", {})})

    response_spots = [
        {"spot_id": spot_id, "status": filled}
        for spot_id, filled in zip(state["spot_ids"], state["filled_status"])
    ]
    counts = state.get("latest_counts", {"free": 0, "full": 0, "total": 0})
    return jsonify({"spots": response_spots, "counts": counts})

# ---------------- Main ----------------
if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, threaded=True)
