import asyncio, json, cv2, numpy as np
from quart import Quart, jsonify, abort, Response
from quart_cors import cors
from ultralytics import YOLO
import aiohttp

# ---------------- Config ----------------
MODEL_PATH = "yolov8s.pt"
FRAME_W, FRAME_H = 1280, 720
POLL_INTERVAL = 10 
API_BASE = "http://127.0.0.1:5001"

# ---------------- App ----------------
app = Quart(__name__)
app = cors(app)
lot_workers = {}
session: aiohttp.ClientSession | None = None

# ---------------- Helpers ----------------
async def get_json(url):
    try:
        async with session.get(url, timeout=5) as r:
            if r.status == 200:
                return await r.json()
    except Exception as e:
        print("GET failed:", url, e)
    return None


async def put_json(url, data):
    try:
        async with session.put(url, json=data, timeout=3) as r:
            await r.read()
    except Exception as e:
        print("PUT failed:", url, e)


async def load_polygons_from_db(lot_id):
    polygons, spot_ids = [], []
    spots = await get_json(f"{API_BASE}/lots/{lot_id}/spots")
    if not spots:
        return polygons, spot_ids
    for s in spots:
        sid = s["id"]
        spot_ids.append(sid)
        poly = await get_json(f"{API_BASE}/spots/{sid}/polygon")
        polygons.append(poly.get("points") if poly else [])
    return polygons, spot_ids


async def get_is_upside_down(lot_id):
    lot = await get_json(f"{API_BASE}/lots/{lot_id}")
    return bool(lot.get("is_video_upside_down", False)) if lot else False


# ---------------- Async Worker ----------------
async def lot_worker(lot_id, live_url):
    print(f"[LOT {lot_id}] Starting async worker for {live_url}")

    state = {
        "latest_counts": {"free": 0, "full": 0, "total": 0},
        "latest_jpeg": None,
        "lock": asyncio.Lock(),
        "running": True
    }
    lot_workers[lot_id] = state

    model = YOLO(MODEL_PATH)
    cap = cv2.VideoCapture(live_url)

    while not cap.isOpened():
        print(f"[LOT {lot_id}] Waiting for stream...")
        await asyncio.sleep(5)
        cap.open(live_url)

    is_upside_down = await get_is_upside_down(lot_id)
    polygons, spot_ids = await load_polygons_from_db(lot_id)
    last_poly_check = asyncio.get_event_loop().time()

    DETECTION_INTERVAL = 30.0  
    last_detection = 0.0

    while state["running"]:
        ok, frame = cap.read()
        if not ok:
            await asyncio.sleep(0.02)
            continue

        # Rotate if needed
        if is_upside_down:
            frame = cv2.rotate(frame, cv2.ROTATE_180)
        frame = cv2.resize(frame, (FRAME_W, FRAME_H))

        now = asyncio.get_event_loop().time()

        if now - last_poly_check > 10:
            polygons, spot_ids = await load_polygons_from_db(lot_id)
            is_upside_down = await get_is_upside_down(lot_id)
            last_poly_check = now

        if now - last_detection >= DETECTION_INTERVAL:
            total_spots = len(polygons)
            filled_status = ["empty"] * total_spots

            results = model.track(frame, persist=True, classes=[2, 7], conf=0.25)
            if results and results[0].boxes.id is not None:
                boxes = results[0].boxes.xyxy.cpu().numpy().astype(int)
                for (x1, y1, x2, y2) in boxes:
                    corners = [(x1, y1), (x2, y1), (x2, y2),
                               (x1, y2), ((x1+x2)//2, (y1+y2)//2)]
                    for i, poly in enumerate(polygons):
                        if not poly:
                            continue
                        pts = np.array(poly, np.int32).reshape((-1, 1, 2))
                        if any(cv2.pointPolygonTest(pts, (float(px), float(py)), False) >= 0 for (px, py) in corners):
                            filled_status[i] = "full"
                            break

            free_count = filled_status.count("empty")
            full_count = filled_status.count("full")
            counts = {"free": free_count, "full": full_count, "total": total_spots}

            # Async DB updates
            tasks = [
                put_json(f"{API_BASE}/spots/{sid}/status", {"status": status})
                for sid, status in zip(spot_ids, filled_status)
            ]
            await asyncio.gather(*tasks, return_exceptions=True)

            # Update state
            async with state["lock"]:
                state["filled_status"] = filled_status
                state["spot_ids"] = spot_ids
                state["latest_counts"] = counts

            last_detection = now  # reset timer

        ok, jpg = cv2.imencode(".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), 80])
        if ok:
            async with state["lock"]:
                state["latest_jpeg"] = jpg.tobytes()

       
        await asyncio.sleep(0.05)  # ~20 FPS feed, regardless of detection load

    cap.release()


# ---------------- Orchestrator ----------------
async def orchestrator():
    """Continuously polls API for lots, launching async workers."""
    while True:
        lots = await get_json(f"{API_BASE}/lots")
        if lots:
            for lot in lots:
                lot_id = lot["id"]
                live_url = lot["live_feed_url"]
                if lot_id not in lot_workers:
                    asyncio.create_task(lot_worker(lot_id, live_url))
        await asyncio.sleep(POLL_INTERVAL)


# ---------------- Routes ----------------
@app.route("/")
async def index():
    links = "".join(
        f"<li><a href='/video_feed/{lid}'>Video Feed {lid}</a> "
        f"<a href='/stats/{lid}'>Stats {lid}</a></li>"
        for lid in lot_workers.keys()
    )
    return f"<h2>EasyLot Async Orchestrator</h2><ul>{links}</ul>"


@app.route("/video_feed/<int:lot_id>")
async def video_feed(lot_id):
    if lot_id not in lot_workers:
        abort(404, "Lot not found")
    state = lot_workers[lot_id]

    async def gen():
        while True:
            async with state["lock"]:
                buf = state.get("latest_jpeg")
            if buf:
                yield b"--frame\r\nContent-Type: image/jpeg\r\n\r\n" + buf + b"\r\n"
            await asyncio.sleep(0.02)
    return Response(gen(), mimetype="multipart/x-mixed-replace; boundary=frame")


@app.route("/stats/<int:lot_id>")
async def stats(lot_id):
    if lot_id not in lot_workers:
        abort(404, "Lot not found")
    state = lot_workers[lot_id]
    async with state["lock"]:
        spots = [
            {"spot_id": sid, "status": st}
            for sid, st in zip(state.get("spot_ids", []), state.get("filled_status", []))
        ]
        counts = state.get("latest_counts", {"free": 0, "full": 0, "total": 0})
    return jsonify({"spots": spots, "counts": counts})


# ---------------- Main ----------------
if __name__ == "__main__":
    import uvicorn

    async def main():
        global session
        session = aiohttp.ClientSession()
        asyncio.create_task(orchestrator())
        await app.run_task(host="127.0.0.1", port=5000)
        await session.close()

    asyncio.run(main())
