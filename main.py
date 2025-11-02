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

# ---------------- Helpers ----------------
def load_polygons_from_db(lot_id):
    polygons = []
    spot_ids = []
    try:
        # Get spots
        r = requests.get(f"{API_BASE}/lots/{lot_id}/spots")
        r.raise_for_status()
        spots = r.json()

        for spot in spots:
            spot_id = spot["id"]
            spot_ids.append(spot_id)
            r2 = requests.get(f"{API_BASE}/spots/{spot_id}/polygon")
            if r2.status_code == 200:
                pts = r2.json().get("points")
                if pts:
                    polygons.append(pts)
                else:
                    polygons.append([])
    except Exception as e:
        print(f"[LOT {lot_id}] Error loading polygons:", e)
    return polygons, spot_ids


def update_spot_status(spot_id, status):
    #Push the detected spot status back into DB.
    try:
        requests.put(f"{API_BASE}/spots/{spot_id}/status", json={"status": status}, timeout=3)
    except Exception as e:
        print(f"Failed to update spot {spot_id}: {e}")

# ---------------- Worker ----------------
# Monitors a single parking lot's live video feed in a dedicated thread.
# Detects cars and trucks, checks which parking spots are occupied based
# on predefined polygons, updates each spot's status in the database, and
# maintains the latest counts and images for the /stats and /video_feed endpoints.

def lot_worker(lot_id, live_url):
    print(f"[LOT {lot_id}] Starting worker for {live_url}")
    
    # Ensure state exists before starting the worker
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
    
    state = lot_workers[lot_id]["state"]

    model = YOLO(MODEL_PATH)
    cap = cv2.VideoCapture(live_url)
    
    # Retry opening the stream if it fails
    retry_interval = 5
    while not cap.isOpened() and state["running"]:
        print(f"[LOT {lot_id}] Failed to open stream. Retrying in {retry_interval}s...")
        time.sleep(retry_interval)
        cap.open(live_url)

    encode_params = [int(cv2.IMWRITE_JPEG_QUALITY), 80]
    polygons, spot_ids = load_polygons_from_db(lot_id)
    last_poly_check = 0

    while state["running"]:
        ok, frame = cap.read()
        if not ok:
            time.sleep(0.02)
            continue

        frame = cv2.resize(frame, (FRAME_W, FRAME_H))
        now = time.time()

        # Reload polygons every 10s
        if now - last_poly_check > 10:
            polygons, spot_ids = load_polygons_from_db(lot_id)
            last_poly_check = now

        # Initialize counts and statuses in case detection fails
        total_spots = len(polygons)
        full_spots = 0
        filled_status = ["empty"] * total_spots
        latest_counts = {
            "free": total_spots,
            "full": 0,
            "total": total_spots
        }

        # detect/track cars and trucks (2 and 7)
        results = model.track(frame, persist=True, classes=[2,7], conf=0.25)
        overlay = frame.copy()

        if results and results[0].boxes.id is not None:
            boxes = results[0].boxes.xyxy.cpu().numpy().astype(int)
            for (x1,y1,x2,y2) in boxes:
                corners = [(x1,y1),(x2,y1),(x2,y2),(x1,y2),((x1+x2)//2,(y1+y2)//2)]
                for i, poly in enumerate(polygons):
                    if not poly:
                        continue
                    pts = np.array(poly, np.int32).reshape((-1,1,2))
                    if any(cv2.pointPolygonTest(pts, (float(px), float(py)), False) >= 0 for (px,py) in corners):
                        if filled_status[i] == "empty":
                            filled_status[i] = "full"  # <- mark as full
                            full_spots += 1
                        break

        # Update counts after detection
        free_spots = filled_status.count("empty")
        full_count = filled_status.count("full")
        latest_counts = {
            "free": free_spots,
            "full": full_count,
            "total": total_spots
        }

        # Update DB spot statuses
        for i, spot_id in enumerate(spot_ids):
            update_spot_status(spot_id, filled_status[i])  # still "empty" or "full"

        # Save latest state for /stats endpoint
        with state["jpeg_lock"]:
            ok, jpg = cv2.imencode(".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), 80])
            if ok:
                state["latest_jpeg"] = jpg.tobytes()
            state["filled_status"] = filled_status
            state["spot_ids"] = spot_ids
            state["latest_counts"] = latest_counts


# ---------------- Orchestrator ----------------
# Continuously polls the API for parking lots and starts a worker thread
# for any new lot. Each worker monitors the lot's video feed, detects cars,
# and updates the state. Runs in a background thread to manage all lots.
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
    return "<h2>EasyLot Orchestrator</h2><ul>" + \
           "".join([f"<li><a href='/video_feed/{lid}'>Video Feed {lid}</a></li>"
                    f"<li><a href='/stats/{lid}'>Stats {lid}</a></li>"
                    for lid in lot_workers.keys()]) + "</ul>"

@app.route("/video_feed/<int:lot_id>")
def video_feed(lot_id):
    if lot_id not in lot_workers:
        abort(404, "Lot not found")
    state = lot_workers[lot_id]["state"]

    # Wait until the worker has initialized the lock
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

    # Wait until worker state has spot_ids & filled_status
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
