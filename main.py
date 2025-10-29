import os, time, threading, json
import cv2, numpy as np, cvzone
from flask import Flask, jsonify, request, abort, Response
from flask_cors import CORS
from ultralytics import YOLO

# ---------------- Config ----------------
POLYGON_FILE = "polygon.json"
MODEL_PATH   = "yolov8s.pt"
FRAME_W, FRAME_H = 1280, 720

# ---------------- App ----------------
app = Flask(__name__)
CORS(app)

# ---------------- State ----------------
polygons = []
latest_counts = {"free": 0, "full": 0, "total": 0, "free_spaces":[], "full_spaces":[]}
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

#LIVE_STREAM_URL = "https://taco-about-python.com/video_feed"

LIVE_STREAM_URL = "http://170.249.152.2:8080/video.mjpg"

print(f"Opening live stream from: {LIVE_STREAM_URL}")
cap = cv2.VideoCapture(LIVE_STREAM_URL)

if not cap.isOpened():
    raise RuntimeError(f"Unable to open live stream: {LIVE_STREAM_URL}")

# ---------------- Worker: process frames continuously ----------------
def worker():
    last_poly_check = 0
    encode_params = [int(cv2.IMWRITE_JPEG_QUALITY), 80]

    while running:
        ok, frame = cap.read()
        if not ok:
            time.sleep(0.02)
            continue

        frame = cv2.resize(frame, (FRAME_W, FRAME_H))

        # hot-reload polygons every 2s
        now = time.time()
        if now - last_poly_check > 2.0:
            load_polygons()
            last_poly_check = now

        # detect/track cars and trucks (2 and 7)
        results = model.track(frame, persist=True, classes=[2, 7], conf=0.25)

        overlay = frame.copy()
        full_spots = 0
        total_spots = len(polygons)
        filled_status = [False] * total_spots

        if results and results[0].boxes.id is not None:
            boxes = results[0].boxes.xyxy.cpu().numpy().astype(int)
            for (x1, y1, x2, y2) in boxes:
                cx, cy = int((x1+x2)/2), int((y1+y2)/2)
                corners = [(x1,y1),(x2,y1),(x2,y2),(x1,y2),(cx,cy)]
                for i, poly in enumerate(polygons):
                    pts = np.array(poly, np.int32).reshape((-1,1,2))
                    if any(cv2.pointPolygonTest(pts, (float(px), float(py)), False) >= 0 for (px,py) in corners):
                        if not filled_status[i]:
                            filled_status[i] = True
                            full_spots += 1
                        break

        # draw polygons + numbering 
        for i, poly in enumerate(polygons):
            pts = np.array(poly, np.int32).reshape((-1,1,2))
            color = (0,255,0) if not filled_status[i] else (0,0,255)
            cv2.fillPoly(overlay, [pts], color)
            cv2.polylines(frame, [pts], True, (255,255,255), 2)
            
            M = cv2.moments(pts)
            if M["m00"] != 0:
                cX = int(M["m10"] / M["m00"])
                cY = int(M["m01"] / M["m00"])
                cv2.putText(frame, str(i+1), (cX-10, cY+10), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (255,255,255), 2)

        frame = cv2.addWeighted(overlay, 0.5, frame, 0.5, 0)

        free_spots = max(0, total_spots - full_spots)

        #tracks which space numbers are free/full

        free_spaces = [i + 1 for i, filled in enumerate(filled_status) if not filled]
        full_spaces = [i + 1 for i, filled in enumerate(filled_status) if filled]
        
        # update stats
        latest_counts["free"] = int(free_spots)
        latest_counts["full"] = int(full_spots)
        latest_counts["total"] = int(total_spots)
        latest_counts["free_spaces"] = free_spaces
        latest_counts["full_spaces"] = full_spaces

        ok, jpg = cv2.imencode(".jpg", frame, encode_params)
        if ok:
            with jpeg_lock:
                global latest_jpeg
                latest_jpeg = jpg.tobytes()

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
                time.sleep(0.02)
                continue
            yield boundary + b"\r\nContent-Type: image/jpeg\r\n\r\n" + buf + b"\r\n"
    return Response(gen(), mimetype="multipart/x-mixed-replace; boundary=frame",
                    headers={"Cache-Control": "no-cache, no-store, must-revalidate"})

@app.route("/stats")
def stats():
    return jsonify(latest_counts)
    #number of free spaces
    #number id of free spaces
    #number of full spaces
    #number id of full spaces
    #total number of drawn spaces

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

# ---------------- Main ----------------
if __name__ == "__main__":
    # For LAN access change host to "0.0.0.0"
    app.run(host="127.0.0.1", port=5000, threaded=True)
