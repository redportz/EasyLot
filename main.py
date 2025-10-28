import os, time, threading, json
import cv2, numpy as np, cvzone
from flask import Flask, jsonify, request, abort, Response
from flask_cors import CORS
from ultralytics import YOLO

# ---------------- Config ----------------
POLYGON_FILE = "polygon.json"
MODEL_PATH   = "yolov8s.pt"   # or your best.pt
FRAME_W, FRAME_H = 1280, 720  # reduce if you need more FPS

# ---------------- App ----------------
app = Flask(__name__)
CORS(app)

# ---------------- State ----------------
polygons = []
latest_counts = {"free": 0, "full": 0, "total": 0}
latest_jpeg = None
jpeg_lock = threading.Lock()
running = True

# ---------------- Load/save polygons ----------------
def load_polygons():
    global polygons
    try:
        with open(POLYGON_FILE, "r") as f:
            polygons = json.load(f)
    except Exception:
        polygons = []
        with open(POLYGON_FILE, "w") as f:
            json.dump(polygons, f)

def save_polygons():
    with open(POLYGON_FILE, "w") as f:
        json.dump(polygons, f)

load_polygons()

# ---------------- YOLO + camera ----------------
model = YOLO(MODEL_PATH)

LIVE_STREAM_URL = "https://taco-about-python.com/video_feed"

print(f"Opening live stream from: {LIVE_STREAM_URL}")
cap = cv2.VideoCapture(LIVE_STREAM_URL)

if not cap.isOpened():
    raise RuntimeError(f"Unable to open live stream: {LIVE_STREAM_URL}")

# ---------------- Worker: process frames continuously ----------------
def worker():
    last_poly_check = 0
    last_detection_time = 0
    encode_params = [int(cv2.IMWRITE_JPEG_QUALITY), 80]

    # variables for certainty
    CONF_CERTAIN = 0.2       # YOLO confidence minimum for a certain detection
    EMPTY_CONFIDENCE = 0.2   # If average confidence of detections is below this, assume the spots are full
    CHECK_INTERVAL = 5       # seconds between YOLO detections

    results = None  # store last YOLO result to reuse between intervals

    while running:
        ok, frame = cap.read()
        if not ok:
            time.sleep(0.5)
            continue

        frame = cv2.resize(frame, (FRAME_W, FRAME_H))
        now = time.time()

        # reload polygons every 5s 
        if now - last_poly_check > 5.0:
            load_polygons()
            last_poly_check = now

        # Only run YOLO detection every CHECK_INTERVAL seconds
        if now - last_detection_time > CHECK_INTERVAL:
            results = model.track(frame, persist=True, classes=[2], conf=CONF_CERTAIN)
            last_detection_time = now
            print(f"YOLO checked at {time.strftime('%H:%M:%S')}")

        overlay = frame.copy()
        full_spots = 0
        total_spots = len(polygons)
        filled_status = [False] * total_spots
        avg_conf = 0.0

        # --- Only process if we have detection  ---
        if results and results[0].boxes is not None:
            boxes = results[0].boxes
            xyxy = boxes.xyxy.cpu().numpy().astype(int)
            confs = boxes.conf.cpu().numpy()
            avg_conf = float(np.mean(confs)) if len(confs) > 0 else 0.0

            for (x1, y1, x2, y2), conf in zip(xyxy, confs):
                cx, cy = int((x1 + x2) / 2), int((y1 + y2) / 2)
                corners = [(x1, y1), (x2, y1), (x2, y2), (x1, y2), (cx, cy)]
                for i, poly in enumerate(polygons):
                    pts = np.array(poly, np.int32).reshape((-1, 1, 2))

                    # Check overlap between detection and polygon
                    overlap = any(cv2.pointPolygonTest(pts, (float(px), float(py)), False) >= 0 
                                  for (px, py) in corners)

                    if overlap and conf >= CONF_CERTAIN:
                        filled_status[i] = True
                        break

        # --- Safety rule: assume full unless sure its empty ---
        if avg_conf < EMPTY_CONFIDENCE:
            filled_status = [True] * total_spots

        full_spots = sum(1 for x in filled_status if x)

        # --- Draw polygons ---
        for i, poly in enumerate(polygons):
            pts = np.array(poly, np.int32).reshape((-1,1,2))
            color = (0,255,0) if not filled_status[i] else (0,0,255)
            cv2.fillPoly(overlay, [pts], color)
            cv2.polylines(frame, [pts], True, (255,255,255), 2)

            #numbering drawn parking spots
            M = cv2.moments(pts)
            if M["m00"] != 0:
                cX = int(M["m10"] / M["m00"])
                cY = int(M["m01"] / M["m00"])
                cv2.putText(frame, str(i+1), (cX-10, cY+10), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (255,255,255), 2)

        frame = cv2.addWeighted(overlay, 0.5, frame, 0.5, 0)

        # --- Update stats ---
        free_spots = max(0, total_spots - full_spots)
        latest_counts["free"] = int(free_spots)
        latest_counts["full"] = int(full_spots)
        latest_counts["total"] = int(total_spots)
        latest_counts["filled_status"] = filled_status  #for the free spots root call


        ok, jpg = cv2.imencode(".jpg", frame, encode_params)
        if ok:
            with jpeg_lock:
                global latest_jpeg
                latest_jpeg = jpg.tobytes()

        time.sleep(0.1)  # short pause for stability


t = threading.Thread(target=worker, daemon=True)
t.start()

# ---------------- HTTP endpoints ----------------
@app.route("/")
def index():
    return (
        "<h2>EasyLot API</h2>"
        "<ul>"
        "<li><a href='/video_feed'>/video_feed</a> (MJPEG)</li>"
        "<li><a href='/stats'>/stats</a></li>"
        "<li><a href='/polygons'>/polygons</a> (GET / POST)</li>"
        "</ul>"
    )

@app.route("/video_feed")
def video_feed():
    def gen():
        boundary = b"--frame"
        while True:
            with jpeg_lock:
                buf = latest_jpeg
            if buf is None:
                time.sleep(0.5)
                continue
            yield boundary + b"\r\nContent-Type: image/jpeg\r\n\r\n" + buf + b"\r\n"
    return Response(gen(), mimetype="multipart/x-mixed-replace; boundary=frame",
                    headers={"Cache-Control": "no-cache, no-store, must-revalidate"})

@app.route("/stats")
def stats():
    return jsonify(latest_counts)

@app.route("/polygons", methods=["GET"])
def get_polygons():
    return jsonify({"polygons": polygons})

@app.route("/polygons", methods=["POST"])
def set_polygons():
    body = request.get_json(force=True, silent=True) or {}
    new_polys = body.get("polygons")
    if not isinstance(new_polys, list):
        abort(400, "polygons must be a list of quads: [[[x,y],...4],[...]]")
    for p in new_polys:
        if not (isinstance(p, list) and len(p) == 4 and all(isinstance(pt, list) and len(pt) == 2 for pt in p)):
            abort(400, "each polygon must have 4 [x,y] points")
    with open(POLYGON_FILE, "w") as f:
        json.dump(new_polys, f)
    load_polygons()
    return jsonify({"ok": True, "total": len(polygons)})

@app.route("/free_spots")
def free_spots():
    # Numbers start at 1, returns empty if none are open
    empty_spots = [i+1 for i, filled in enumerate(latest_counts.get("filled_status", [])) if not filled]
    return jsonify({"empty_spots": empty_spots})


# ---------------- Main ----------------
if __name__ == "__main__":
    # For LAN access change host to "0.0.0.0"
    app.run(host="127.0.0.1", port=5000, threaded=True)
