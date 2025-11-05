import os, json, time
from dotenv import load_dotenv
from flask import Flask, request, jsonify
from flask_cors import CORS
from sqlalchemy import (Boolean, create_engine, Column, Integer, String, Text, DateTime, Enum,
                        Float, ForeignKey, UniqueConstraint, func)
from sqlalchemy.orm import declarative_base, sessionmaker, relationship
from sqlalchemy.sql import expression
from dotenv import load_dotenv

load_dotenv()

DB_USER = os.getenv("DB_USER")
DB_PASS = os.getenv("DB_PASS")
DB_HOST = os.getenv("DB_HOST")
DB_PORT = os.getenv("DB_PORT")
DB_NAME = os.getenv("DB_NAME")

DATABASE_URL = f"mysql+pymysql://{DB_USER}:{DB_PASS}@{DB_HOST}:{DB_PORT}/{DB_NAME}?charset=utf8mb4"

app = Flask(__name__)
CORS(app)
engine = create_engine(DATABASE_URL, pool_pre_ping=True)
Session = sessionmaker(bind=engine)
Base = declarative_base()

class Lot(Base):
    __tablename__ = "lots"
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(120), nullable=False)
    live_feed_url = Column(Text, nullable=False)
    is_video_upside_down = Column(Boolean, nullable=False, server_default=expression.false())
    created_at = Column(DateTime, server_default=func.now())
    spots = relationship("Spot", back_populates="lot", cascade="all,delete")
    plain_slots = relationship("PlainSlot", back_populates="lot", cascade="all,delete")

    

class Spot(Base):
    __tablename__ = "spots"
    __table_args__ = (
        UniqueConstraint("lot_id", "spot_number", name="uq_lot_spotnum"),
    )
    id = Column(Integer, primary_key=True, autoincrement=True)
    lot_id = Column(Integer, ForeignKey("lots.id"), nullable=False)
    spot_number = Column(Integer, nullable=False)  # <— sequential display number
    status = Column(Enum('empty','full','unknown'), nullable=False, server_default='unknown')
    last_update = Column(DateTime, server_default=func.now())
    lot = relationship("Lot", back_populates="spots")
    polygon = relationship("Polygon", back_populates="spot", uselist=False, cascade="all,delete")
class Polygon(Base):
    __tablename__ = "polygons"
    id = Column(Integer, primary_key=True, autoincrement=True)
    spot_id = Column(Integer, ForeignKey("spots.id"), nullable=False, unique=True)
    points_json = Column(Text, nullable=False, server_default='[]')
    spot = relationship("Spot", back_populates="polygon")

class PlainSlot(Base):
    __tablename__ = "plain_lot_slots"
    __table_args__ = (UniqueConstraint("lot_id", "spot_id", name="uq_plain_lot_spot"),)

    id          = Column(Integer, primary_key=True, autoincrement=True)
    lot_id      = Column(Integer, ForeignKey("lots.id"), nullable=False, index=True)
    spot_id     = Column(Integer, ForeignKey("spots.id"), nullable=False, index=True)
    slot_number = Column(Integer, nullable=True)  # label/order (optional)
    x           = Column(Float, nullable=False)
    y           = Column(Float, nullable=False)
    rotation    = Column(Float, nullable=False, server_default="0")
    updated_at  = Column(DateTime, server_default=func.now(), onupdate=func.now())

    lot = relationship("Lot", back_populates="plain_slots")




# LOTS

# get all lots info
@app.get("/lots")
def list_lots():
    with Session() as s:
        rows = s.query(Lot).all()
        return jsonify([{
            "id": r.id, "name": r.name,
            "live_feed_url": r.live_feed_url,
            "is_video_upside_down": bool(r.is_video_upside_down),
            "created_at": r.created_at.isoformat() if r.created_at else None
        } for r in rows])

# get a single lots info
@app.get("/lots/<int:lot_id>")
def get_lot(lot_id):
    with Session() as s:
        lot = s.query(Lot).filter(Lot.id == lot_id).first()
        if not lot:
            return jsonify({"message": f"Lot {lot_id} not found"}), 404
        
        return jsonify({
            "id": lot.id,
            "name": lot.name,
            "live_feed_url": lot.live_feed_url,
            "is_video_upside_down": bool(lot.is_video_upside_down),
            "created_at": lot.created_at.isoformat() if lot.created_at else None
        }), 200

# add a lot
@app.post("/lots")
def create_lot():
    data = request.get_json() or {}

    # require all three
    for k in ("name", "live_feed_url", "is_video_upside_down"):
        if k not in data:
            return jsonify({"message": f"{k} required"}), 400

    with Session() as s:
        lot = Lot(
            name=data["name"].strip(),
            live_feed_url=data["live_feed_url"].strip(),
            is_video_upside_down=data["is_video_upside_down"],
        )
        s.add(lot)
        s.commit()
        s.refresh(lot)
        return jsonify({"id": lot.id}), 201

# delete a lot
@app.delete("/lots/<int:lot_id>")
def delete_lot(lot_id):
    with Session.begin() as s:
        lot = s.query(Lot).filter(Lot.id == lot_id).first()
        if not lot:
            return jsonify({"message": f"Lot {lot_id} not found"}), 404

        # ORM cascades will remove spots, polygons, and plain_slots
        s.delete(lot)

    return jsonify({"message": "Lot deleted", "id": lot_id}), 200


# update a lots live feed url
@app.post("/lots/<int:lot_id>/update_url")
def update_live_feed_url(lot_id):
    data = request.get_json() or {}

    new_url = data.get("live_feed_url")
    is_video_upside_down = data.get("is_video_upside_down")

    if new_url is None or is_video_upside_down is None:
        return jsonify({"message": "live_feed_url and is_video_upside_down required"}), 400

    with Session() as s:
        lot = s.query(Lot).filter(Lot.id == lot_id).first()
        if not lot:
            return jsonify({"message": f"Lot {lot_id} not found"}), 404
        
        lot.live_feed_url = new_url.strip()
        lot.is_video_upside_down = bool(is_video_upside_down)

        s.commit()
        s.refresh(lot)

        return jsonify({
            "message": "Live feed URL and flag updated successfully",
            "id": lot.id,
            "live_feed_url": lot.live_feed_url,
            "is_video_upside_down": lot.is_video_upside_down
        }), 200


   # get lots spot information
@app.get("/lots/<int:lot_id>/spots")
def list_spots(lot_id):
    with Session() as s:
        rows = (
            s.query(Spot, Polygon)
             .outerjoin(Polygon, Polygon.spot_id == Spot.id)
             .filter(Spot.lot_id == lot_id)
             .order_by(Spot.spot_number.asc())
             .all()
        )
        return jsonify([
            {
              "id": sp.id,
              "spot_number": sp.spot_number,
              "status": sp.status,
              "last_update": sp.last_update.isoformat() if sp.last_update else None,
              "polygon": json.loads(pg.points_json) if pg and pg.points_json else None
            }
            for sp, pg in rows
        ])

# add lot spot info
@app.put("/lots/<int:lot_id>/spots_sync")
def sync_spots(lot_id):
    data = request.get_json() or {}
    req_polys = data.get("polygons", [])
    req_stats = data.get("statuses", [])
    prune = request.args.get("prune", "false").lower() == "true"

    def clean_poly(poly):
        out = []
        for pt in (poly or []):
            if isinstance(pt, (list, tuple)) and len(pt) == 2 and all(isinstance(n, (int, float)) for n in pt):
                out.append([float(pt[0]), float(pt[1])])
            elif isinstance(pt, dict) and "x" in pt and "y" in pt:
                out.append([float(pt["x"]), float(pt["y"])])
        return out

    def same_poly(a_list, b_list):
        # exact compare on numbers (adjust if you want tolerance)
        return a_list == b_list

    added = updated = deleted = unchanged = 0

    with Session.begin() as s:
        # Load current spots+polys ordered by spot_number
        rows = (
            s.query(Spot, Polygon)
             .outerjoin(Polygon, Polygon.spot_id == Spot.id)
             .filter(Spot.lot_id == lot_id)
             .order_by(Spot.spot_number.asc())
             .all()
        )

        # Ensure we have mutable arrays
        db_spots = [sp for sp, _ in rows]
        db_polys = [json.loads(pg.points_json) if pg and pg.points_json else [] for _, pg in rows]
        db_pg_rows = [pg for _, pg in rows]

        # Iterate target length
        target_len = len(req_polys)
        for i in range(target_len):
            target_num = i + 1
            target_pts = clean_poly(req_polys[i])
            target_status = None
            if isinstance(req_stats, list) and i < len(req_stats) and req_stats[i] in ("empty", "full", "unknown"):
                target_status = req_stats[i]

            if i < len(db_spots):
                # Existing spot at this index: update if changed
                sp = db_spots[i]
                pg = db_pg_rows[i]

                # status compare/update (optional)
                if target_status and sp.status != target_status:
                    sp.status = target_status

                # polygon compare/update
                existing_pts = clean_poly(db_polys[i])
                if pg is None:
                    # add new polygon row
                    pg = Polygon(spot_id=sp.id, points_json=json.dumps(target_pts))
                    s.add(pg)
                    updated += 1 if target_pts else unchanged  # if empty, nothing really changed
                else:
                    if not same_poly(existing_pts, target_pts):
                        pg.points_json = json.dumps(target_pts)
                        updated += 1
                    else:
                        unchanged += 1
            else:
                # Need to append a new spot
                st = target_status if target_status else "unknown"
                sp = Spot(lot_id=lot_id, spot_number=target_num, status=st)
                s.add(sp)
                s.flush()
                s.add(Polygon(spot_id=sp.id, points_json=json.dumps(target_pts)))
                added += 1

        if prune and len(db_spots) > target_len:
            for j in range(target_len, len(db_spots)):
                s.delete(db_spots[j])
                deleted += 1


    return jsonify({"ok": True, "added": added, "updated": updated, "deleted": deleted, "unchanged": unchanged}), 200

    
# POLYGONS

# get a spots location
@app.get("/spots/<int:spot_id>/polygon")
def get_polygon(spot_id):
    with Session() as s:
        poly = s.query(Polygon).filter_by(spot_id=spot_id).one_or_none()
        pts = json.loads(poly.points_json) if (poly and poly.points_json) else None
        return jsonify({"points": pts})
    
# LOT STATUS

# add a spots status (full/empty, unknown)
@app.put("/spots/<int:spot_id>/status")
def update_spot_status(spot_id):
    data = request.get_json() or {}
    status = data.get("status")
    if status not in ("empty","full","unknown"):
        return jsonify({"message":"status must be empty|full|unknown"}), 400
    with Session() as s:
        spot = s.get(Spot, spot_id)
        if not spot: return jsonify({"message":"not found"}), 404
        spot.status = status
        spot.last_update = func.now()
        s.commit()
        return jsonify({"ok": True})

# get a spots status (full, empty, unknown)
@app.get("/lots/<int:lot_id>/status")
def lot_status(lot_id):
    with Session() as s:
        total = s.query(Spot).filter_by(lot_id=lot_id).count()
        full  = s.query(Spot).filter_by(lot_id=lot_id, status='full').count()
        free  = s.query(Spot).filter_by(lot_id=lot_id, status='empty').count()
        return jsonify({"free": free, "full": full, "total": total})

#plain lot
@app.get("/lots/<int:lot_id>/plain_slots")
def get_plain_slots(lot_id):
    with Session() as s:
        rows = (
            s.query(
                PlainSlot,
                Spot.spot_number.label("spotnum")   # pull the real spot_number
            )
            .join(Spot, Spot.id == PlainSlot.spot_id)
            .filter(PlainSlot.lot_id == lot_id)
            # MySQL-safe ordering: by the actual spot_number, then by id
            .order_by(Spot.spot_number.asc(), PlainSlot.id.asc())
            .all()
        )
        return jsonify([{
            "id": ps.id,
            "spot_id": ps.spot_id,
            # prefer explicit slot_number if set, else fall back to Spot.spot_number
            "slot_number": ps.slot_number if ps.slot_number is not None else spotnum,
            "x": ps.x, "y": ps.y,
            "rotation": ps.rotation,
            "updated_at": ps.updated_at.isoformat() if ps.updated_at else None
        } for ps, spotnum in rows]), 200

@app.put("/lots/<int:lot_id>/plain_slots")
def put_plain_slots(lot_id):
    data = request.get_json(silent=True) or {}
    slots = data.get("slots", [])
    if not isinstance(slots, list):
        return jsonify({"message": "'slots' must be a list"}), 400

    with Session.begin() as s:
        # build slot_number->spot_id lookup in case payload has only slot_number
        spot_rows = s.query(Spot).filter(Spot.lot_id == lot_id).all()
        by_num = {sp.spot_number: sp.id for sp in spot_rows}

        s.query(PlainSlot).filter(PlainSlot.lot_id == lot_id).delete()

        for i, sl in enumerate(slots):
            spot_id = sl.get("spot_id")
            slot_number = sl.get("slot_number")
            if spot_id is None:
                if slot_number is None:
                    return jsonify({"message": f"slot[{i}] needs spot_id or slot_number"}), 400
                spot_id = by_num.get(int(slot_number))
                if spot_id is None:
                    return jsonify({"message": f"slot[{i}] unknown slot_number {slot_number} for lot {lot_id}"}), 400
            x, y = sl.get("x"), sl.get("y")
            if x is None or y is None:
                return jsonify({"message": f"slot[{i}] needs x and y"}), 400
            s.add(PlainSlot(
                lot_id=lot_id,
                spot_id=int(spot_id),
                slot_number=int(slot_number) if slot_number is not None else None,
                x=float(x), y=float(y),
                rotation=float(sl.get("rotation", 0)),
            ))
    return jsonify({"ok": True, "count": len(slots)}), 200



if __name__ == "__main__":

    app.run(host="127.0.0.1", port=5001, debug=True)