import os, time, threading, json
import cv2, numpy as np, cvzone
from flask import Flask, jsonify, request, abort, Response
from flask_cors import CORS
from ultralytics import YOLO

# ---------------- Config ----------------
POLYGON_FILE = "polygon.json"
MODEL_PATH = "yolov8s.pt"
HOMOGRAPHY_FILE = "homography.json"  # new
FRAME_W, FRAME_H = 1280, 720

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

# ---------------- Load Homography ----------------
H = None
H_WIDTH, H_HEIGHT = 1600, 1200  # output warped size
if os.path.exists(HOMOGRAPHY_FILE):
    try:
        with open(HOMOGRAPHY_FILE, "r") as f:
            data = json.load(f)
            src = np.array(data["src"], np.float32)
            dst = np.array(data["dst"], np.float32)
            H, _ = cv2.findHomography(src, dst)
            print("Homography loaded successfully.")
    except Exception as e:
        print("Failed to load homography:", e)
else:
    print("No homography.json found, using raw camera frames.")

# ---------------- YOLO + camera ----------------
model = YOLO(MODEL_PATH)
cap = cv2.VideoCapture(0)
if not cap.isOpened():
    print("Cannot open camera, using test image instead")
    cap = None
    TEST_IMAGE = cv2.imread("tester.jpg")
    if TEST_IMAGE is None:
        raise RuntimeError("No camera and test image not found")

# ---------------- Worker ----------------
def worker():
    last_poly_check = 0
    encode_params = [int(cv2.IMWRITE_JPEG_QUALITY), 80]

    while running:
        if cap is not None:
            ok, frame = cap.read()
            if not ok:
                time.sleep(0.02)
                continue
        else:
            frame = TEST_IMAGE.copy()

        # Apply homography warp if available
        if H is not None:
            frame = cv2.warpPerspective(frame, H, (H_WIDTH, H_HEIGHT))
        else:
            frame = cv2.resize(frame, (FRAME_W, FRAME_H))

        # Hot reload polygons
        now = time.time()
        if now - last_poly_check > 2.0:
            load_polygons()
            last_poly_check = now

        # YOLO detection
        results = model.track(frame, persist=True, classes=[2], conf=0.25)

        overlay = frame.copy()
        full_spots = 0
        total_spots = len(polygons)
        filled_status = [False] * total_spots

        if results and results[0].boxes.id is not None:
            boxes = results[0].boxes.xyxy.cpu().numpy().astype(int)
            for (x1, y1, x2, y2) in boxes:
                cx, cy = int((x1 + x2) / 2), int((y1 + y2) / 2)
                corners = [(x1, y1), (x2, y1), (x2, y2), (x1, y2), (cx, cy)]
                for i, poly in enumerate(polygons):
                    pts = np.array(poly, np.int32).reshape((-1, 1, 2))
                    if any(cv2.pointPolygonTest(pts, (float(px), float(py)), False) >= 0 for (px, py) in corners):
                        if not filled_status[i]:
                            filled_status[i] = True
                            full_spots += 1
                        break

        # Draw polygons
        for i, poly in enumerate(polygons):
            pts = np.array(poly, np.int32).reshape((-1, 1, 2))
            color = (0, 255, 0) if not filled_status[i] else (0, 0, 255)
            cv2.fillPoly(overlay, [pts], color)
            cv2.polylines(frame, [pts], True, (255, 255, 255), 2)

        frame = cv2.addWeighted(overlay, 0.5, frame, 0.5, 0)

        free_spots = max(0, total_spots - full_spots)
        latest_counts.update({"free": free_spots, "full": full_spots, "total": total_spots})

        # Encode frame for streaming
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
    app.run(host="127.0.0.1", port=5000, threaded=True)
