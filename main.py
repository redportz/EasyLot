import cv2
import json
import os
import cvzone
import numpy as np
from ultralytics import YOLO
import time

# ---------------- YOLO Model ----------------
model = YOLO('yolov8s.pt')
names = model.names

# ---------------- Input ----------------
input_source = "0" #change from 0 to file name if reading a file
is_image = isinstance(input_source, str) and input_source.lower().endswith(('.png', '.jpg', '.jpeg', '.bmp', '.tiff'))

if is_image:
    frame = cv2.imread(input_source)
    if frame is None:
        raise FileNotFoundError(f"{input_source} not found in current directory.")
else:
    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        raise ValueError(f"Cannot open video source {input_source}")

# ---------------- Polygon Setup ----------------
polygon_points = []
polygons = []
polygon_file = "polygon.json"
drawing_mode = False  # A pressed → editing enabled

# ---------------- Popup System ----------------
popup_message = ""
popup_time = 0

def show_popup(message, duration=2):
    global popup_message, popup_time
    popup_message = message
    popup_time = time.time() + duration

# Load saved polygons
if os.path.exists(polygon_file):
    try:
        with open(polygon_file, 'r') as f:
            polygons = json.load(f)
    except (json.JSONDecodeError, ValueError):
        polygons = []
        with open(polygon_file, 'w') as f:
            json.dump(polygons, f)

def save_polygons():
    with open(polygon_file, 'w') as f:
        json.dump(polygons, f)

# ---------------- Mouse Callback ----------------
def RGB(event, x, y, flags, param):
    global polygon_points, polygons
    if not drawing_mode:  # Only allow adding points if A was pressed
        return
    if event == cv2.EVENT_LBUTTONDOWN:
        polygon_points.append((x, y))
        if len(polygon_points) == 4:
            polygons.append(polygon_points.copy())
            save_polygons()
            polygon_points.clear()
            show_popup("Polygon Added")

# ---------------- Load Logo ----------------
logo = cv2.imread("raw.PNG", cv2.IMREAD_UNCHANGED)
if logo is None:
    raise FileNotFoundError("raw.PNG not found")
logo = cv2.resize(logo, (190, 190))

def overlay_logo(frame, logo, margin=10):
    h_logo, w_logo = logo.shape[:2]
    h_frame, w_frame = frame.shape[:2]
    x = w_frame - w_logo - margin
    y = h_frame - h_logo - margin
    if logo.shape[2] == 4:
        b, g, r, a = cv2.split(logo)
        overlay_color = cv2.merge((b, g, r))
        mask = cv2.merge((a, a, a)) / 255.0
        roi = frame[y:y+h_logo, x:x+w_logo]
        frame[y:y+h_logo, x:x+w_logo] = (overlay_color * mask + roi * (1 - mask)).astype(np.uint8)
    else:
        frame[y:y+h_logo, x:x+w_logo] = logo

# ---------------- Create Resizable Window ----------------
cv2.namedWindow('RGB Camera 1', cv2.WINDOW_NORMAL)
cv2.resizeWindow('RGB Camera 1', 2000, 1300)
cv2.setMouseCallback('RGB Camera 1', RGB)

# ---------------- Main Loop ----------------
paused_frame = None  # Store a single frame when drawing

while True:
    if drawing_mode:
        # Pause live feed: use the last captured frame
        if paused_frame is None:
            if not is_image:
                ret, paused_frame = cap.read()
                if not ret:
                    break
                frame = cv2.resize(frame, (2000, 1300))  # resize immediately
            else:
                frame = cv2.resize(frame, (2000, 1300))
            paused_frame = frame.copy()
        frame = paused_frame.copy()
    else:
        paused_frame = None  # Reset paused frame when editing ends
        if not is_image:
            ret, frame = cap.read()
            if not ret:
                break
            frame = cv2.resize(frame, (2000, 1300))
        else:
            frame = cv2.resize(frame, (2000, 1300))

    # YOLO tracking only runs when not paused
    if not drawing_mode:
        results = model.track(frame, persist=True, classes=[2], conf=0.25)
    else:
        results = []  # Skip detection while drawing

    overlay = frame.copy()
    full_spots = 0
    filled_status = [False] * len(polygons)

    if not drawing_mode and results and results[0].boxes.id is not None:
        ids = results[0].boxes.id.cpu().numpy().astype(int)
        boxes = results[0].boxes.xyxy.cpu().numpy().astype(int)
        class_ids = results[0].boxes.cls.int().cpu().tolist()
        for track_id, box, class_id in zip(ids, boxes, class_ids):
            x1, y1, x2, y2 = box
            cx, cy = int((x1 + x2) / 2), int((y1 + y2) / 2)
            corners = [(x1, y1), (x2, y1), (x2, y2), (x1, y2), (cx, cy)]
            for i, poly in enumerate(polygons):
                pts = np.array(poly, np.int32).reshape((-1, 1, 2))
                if any(cv2.pointPolygonTest(pts, (float(c[0]), float(c[1])), False) >= 0 for c in corners):
                    filled_status[i] = True
                    full_spots += 1
                    break

    # Draw polygons and overlay, same as before
    for i, poly in enumerate(polygons):
        pts = np.array(poly, np.int32).reshape((-1, 1, 2))
        color = (0, 255, 0) if not filled_status[i] else (0, 0, 255)
        cv2.fillPoly(overlay, [pts], color)
        cv2.polylines(frame, [pts], True, (255, 255, 255), 2)

    frame = cv2.addWeighted(overlay, 0.5, frame, 0.5, 0)

    total_spots = len(polygons)
    free_spots = max(0, total_spots - full_spots)

    # ---------------- Print to Console ----------------
    print(f"Full Spots: {full_spots}, Free Spots: {free_spots}")

    cvzone.putTextRect(frame, f"Free Spots: {free_spots}", (30, 50), 2, 2, colorB=(0,0,0), colorR=(196,127,40))
    cvzone.putTextRect(frame, f"Full Spots: {full_spots}", (30, 120), 2, 2, colorB=(0,0,0), colorR=(196,127,40))

    # Draw polygon points while creating
    for pt in polygon_points:
        cv2.circle(frame, pt, 5, (0, 0, 255), thickness=-1)

    # ---------------- Label Key ----------------
    key_instructions = [
        "Controls:",
        "A - Enable Polygon Editing",
        "S - Disable Editing",
        "Left Click - Add Point",
        "U - Undo Polygon/Point",
        "X - Clear All Polygons",
        "Q - Quit Program"
    ]
    start_y = frame.shape[0] - (30 * len(key_instructions)) - 20
    for i, text in enumerate(key_instructions):
        cvzone.putTextRect(frame, text, pos=(30, start_y + i * 30), scale=1, thickness=1, colorB=(0,0,0), colorR=(196,127,40))

    # ---------------- Show Popup ----------------
    if popup_message and time.time() < popup_time:
        cvzone.putTextRect(frame, popup_message, (700, 120), scale=2, thickness=2, colorB=(0,0,0), colorR=(196,127,40))
    else:
        popup_message = ""

    overlay_logo(frame, logo, margin=10)
    cv2.imshow('RGB Camera 1', frame)

    # ---------------- Key Controls ----------------
    key = cv2.waitKey(1) & 0xFF
    if key == ord('q'):
        break
    elif key == ord('a'):
        drawing_mode = True
        show_popup("Drawing Enabled")
    elif key == ord('s'):
        drawing_mode = False
        show_popup("Editing Stopped")
    elif drawing_mode:  # Only allow these if drawing_mode is True
        if key == ord('x'):
            polygon_points.clear()
            polygons.clear()
            save_polygons()
            show_popup("All Polygons Removed")
        elif key == ord('u'):
            if polygon_points:
                polygon_points.pop()
                show_popup("Removed Last Point")
            elif polygons:
                polygons.pop()
                save_polygons()
                show_popup("Removed Last Polygon")

# ---------------- Cleanup ----------------
if not is_image:
    cap.release()
cv2.destroyAllWindows()
