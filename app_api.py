import os, json, time
from dotenv import load_dotenv
from flask import Flask, request, jsonify
from flask_cors import CORS
from sqlalchemy import (create_engine, Column, Integer, String, Text, DateTime, Enum,
                        Float, ForeignKey, func)
from sqlalchemy.orm import declarative_base, sessionmaker, relationship
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
    folder = Column(String(120), nullable=False)
    live_feed_url = Column(Text, nullable=False)
    created_at = Column(DateTime)

    spots = relationship("Spot", back_populates="lot", cascade="all,delete")

class Spot(Base):
    __tablename__ = "spots"
    id = Column(Integer, primary_key=True, autoincrement=True)
    lot_id = Column(Integer, ForeignKey("lots.id"), nullable=False)
    spot_number = Column(String(20))
    status = Column(Enum('empty','full','unknown'), default='unknown')
    last_update = Column(DateTime)

    lot = relationship("Lot", back_populates="spots")
    polygon = relationship("Polygon", back_populates="spot", uselist=False, cascade="all,delete")

class Polygon(Base):
    __tablename__ = "polygons"
    id = Column(Integer, primary_key=True, autoincrement=True)
    spot_id = Column(Integer, ForeignKey("spots.id"), nullable=False)
    points_json = Column(Text)

    spot = relationship("Spot", back_populates="polygon")


# LOTS
@app.get("/lots")
def list_lots():
    with Session() as s:
        rows = s.query(Lot).all()
        return jsonify([{
            "id": r.id, "name": r.name, "folder": r.folder,
            "live_feed_url": r.live_feed_url,
            "created_at": r.created_at.isoformat() if r.created_at else None
        } for r in rows])
    
@app.post("/lots")
def create_lot():
    data = request.get_json() or {}
    for k in ("name","folder","live_feed_url"):
        if not data.get(k): return jsonify({"message": f"{k} required"}), 400
    with Session() as s:
        lot = Lot(name=data["name"].strip(),
                  folder=data["folder"].strip(),
                  live_feed_url=data["live_feed_url"].strip())
        s.add(lot); s.commit(); s.refresh(lot)
        return jsonify({"id": lot.id}), 201
    
@app.get("/lots/<int:lot_id>/spots")
def list_spots(lot_id):
    with Session() as s:
        rows = s.query(Spot).filter(Spot.lot_id==lot_id).all()
        return jsonify([{
            "id": r.id, "spot_number": r.spot_number,
            "status": r.status, "last_update": r.last_update.isoformat() if r.last_update else None
        } for r in rows])


@app.post("/lots/<int:lot_id>/spots")
def create_spot(lot_id):
    data = request.get_json() or {}
    num = (data.get("spot_number") or "").strip()
    with Session() as s:
        spot = Spot(lot_id=lot_id, spot_number=num, status="unknown")
        s.add(spot); s.commit(); s.refresh(spot)
        return jsonify({"id": spot.id}), 201

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
    
# POLYGONS
@app.get("/spots/<int:spot_id>/polygon")
def get_polygon(spot_id):
    with Session() as s:
        poly = s.query(Polygon).filter_by(spot_id=spot_id).one_or_none()
        pts = json.loads(poly.points_json) if (poly and poly.points_json) else None
        return jsonify({"points": pts})

@app.put("/spots/<int:spot_id>/polygon")
def put_polygon(spot_id):
    data = request.get_json() or {}
    points = data.get("points")
    if not isinstance(points, list):
        return jsonify({"message":"points must be a list"}), 400
    with Session() as s:
        poly = s.query(Polygon).filter_by(spot_id=spot_id).one_or_none()
        if not poly:
            poly = Polygon(spot_id=spot_id, points_json=json.dumps(points))
            s.add(poly)
        else:
            poly.points_json = json.dumps(points)
        s.commit()
        return jsonify({"ok": True})
    
# LOT STATUS
@app.get("/lots/<int:lot_id>/status")
def lot_status(lot_id):
    with Session() as s:
        total = s.query(Spot).filter_by(lot_id=lot_id).count()
        full  = s.query(Spot).filter_by(lot_id=lot_id, status='full').count()
        free  = s.query(Spot).filter_by(lot_id=lot_id, status='empty').count()
        return jsonify({"free": free, "full": full, "total": total})


if __name__ == "__main__":

    app.run(host="127.0.0.1", port=5001, debug=True)