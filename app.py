from flask import Flask, render_template, request, jsonify, send_from_directory
import os
import random
import sqlite3
import uuid
from pathlib import Path
from typing import Optional
from datetime import datetime, timezone
from ultralytics import YOLO, YOLOWorld
import cv2
import numpy as np
from PIL import Image

app = Flask(__name__)
UPLOAD_FOLDER = "uploads"
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER

TARGET_CLASSES = ["pangolin", "masked palm civet"]
CLASS_VI_MAP = {
    "pangolin": "Tê Tê",
    "masked palm civet": "Cầy Vòi Mốc",
    "tete": "Tê Tê",
    "te_te": "Tê Tê",
    "cầy vòi mốc": "Cầy Vòi Mốc",
    "cay_voi_moc": "Cầy Vòi Mốc"
}

# 1. Initialize YOLO-World model for open-vocabulary detection
yolo_world_model = None
try:
    yolo_world_model = YOLOWorld("yolov8s-worldv2.pt")
    yolo_world_model.set_classes(TARGET_CLASSES)
    print("YOLO-World model initialized with classes:", TARGET_CLASSES)
except Exception as e:
    print(f"Warning: Could not initialize YOLO-World model: {e}")
    yolo_world_model = None

# 2. YOLO fine-tuned models
# 2a. manhnd_best_model.pt (mô hình gốc PyTorch không nén để kiểm tra độ chính xác)
manhnd_model_path = os.path.join(app.root_path, "static", "onxx_model", "manhnd_best_model.pt")
manhnd_model = None
try:
    if os.path.exists(manhnd_model_path):
        manhnd_model = YOLO(manhnd_model_path)
        print("Loaded manhnd_best_model.pt successfully. Classes:", manhnd_model.names)
    else:
        print(f"Warning: File not found at {manhnd_model_path}")
except Exception as e:
    print(f"Warning: Could not load manhnd_best_model.pt: {e}")
    manhnd_model = None

# 2b. Legacy / fine-tuned YOLOv8 model fallback
yolo_model_path = os.path.join(app.root_path, "static", "my_model", "best.pt")
try:
    yolo_model = YOLO(yolo_model_path)
    print("YOLOv8 best.pt loaded. Classes:", yolo_model.names)
except Exception as e:
    print(f"Warning: Could not load YOLOv8 model: {e}")
    yolo_model = None

# 3. Initialize CLIP zero-shot classification pipeline
clip_classifier = None
try:
    from transformers import pipeline
    clip_classifier = pipeline("zero-shot-image-classification", model="openai/clip-vit-base-patch32")
    print("CLIP zero-shot classifier initialized.")
except Exception as e:
    print(f"Warning: Could not initialize CLIP classifier: {e}")


if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

# Dashboard/event storage
DETECTIONS_DIR = os.path.join(app.root_path, "static", "detections")
DETECTIONS_IMG_DIR = os.path.join(DETECTIONS_DIR, "images")
DETECTIONS_VIDEO_DIR = os.path.join(DETECTIONS_DIR, "videos")
DB_PATH = os.path.join(app.root_path, "detections.db")
GAMEMAKER_DIR = os.path.join(app.root_path, "templates", "TeTe_game")

for folder in (DETECTIONS_DIR, DETECTIONS_IMG_DIR, DETECTIONS_VIDEO_DIR):
    os.makedirs(folder, exist_ok=True)


def _db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _init_db():
    with _db() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_type TEXT NOT NULL,
                probability REAL,
                source TEXT,
                created_at TEXT NOT NULL,
                image_path TEXT,
                video_path TEXT
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS feedbacks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                email TEXT,
                role TEXT,
                message TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS visits (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ip_address TEXT,
                user_agent TEXT,
                browser TEXT,
                os_name TEXT,
                device_type TEXT,
                page_path TEXT,
                page_name TEXT,
                referrer TEXT,
                created_at TEXT NOT NULL
            )
            """
        )


def _utc_now_iso():
    return datetime.now(timezone.utc).isoformat()


def _save_upload(file_storage, folder, ext_fallback):
    if not file_storage:
        return None

    _, ext = os.path.splitext(file_storage.filename or "")
    ext = (ext or ext_fallback).lower()
    filename = f"{uuid.uuid4().hex}{ext}"
    abs_path = os.path.join(folder, filename)
    file_storage.save(abs_path)

    rel = os.path.relpath(abs_path, os.path.join(app.root_path, "static"))
    return rel.replace("\\", "/")


def _safe_unlink_under(base_dir: str, rel_path: Optional[str]) -> bool:
    if not rel_path:
        return False

    base = Path(base_dir).resolve()
    target = (Path(app.root_path) / "static" / rel_path).resolve()

    try:
        target.relative_to(base)
    except ValueError:
        return False

    try:
        target.unlink(missing_ok=True)
        return True
    except OSError:
        return False


_init_db()

PAGE_NAME_MAP = {
    "/": "Trang chủ",
    "/about": "Giới thiệu",
    "/species": "Sổ tay Tê Tê",
    "/notes": "Sổ tay Tê Tê",
    "/tete-notes": "Sổ tay Tê Tê",
    "/scan": "Import Card ID",
    "/cctv": "Camera AI",
    "/hunter_spot": "Hunter Spot",
    "/map": "Bản đồ sinh thái",
    "/game": "Mini Game Tê Tê",
    "/login": "Đăng nhập",
    "/register": "Đăng ký",
    "/visitors": "Thống kê truy cập",
    "/traffic": "Thống kê truy cập",
}


def _get_page_name(path: str) -> str:
    return PAGE_NAME_MAP.get(path, path)


def _get_client_ip():
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.remote_addr or "127.0.0.1"


def _parse_ua(ua_str: str):
    ua_lower = (ua_str or "").lower()

    if "mobile" in ua_lower or "android" in ua_lower or "iphone" in ua_lower:
        device = "Điện thoại"
    elif "tablet" in ua_lower or "ipad" in ua_lower:
        device = "Máy tính bảng"
    else:
        device = "Máy tính"

    if "windows" in ua_lower:
        os_name = "Windows"
    elif "android" in ua_lower:
        os_name = "Android"
    elif "iphone" in ua_lower or "ipad" in ua_lower or "ipod" in ua_lower:
        os_name = "iOS"
    elif "macintosh" in ua_lower or "mac os" in ua_lower:
        os_name = "macOS"
    elif "linux" in ua_lower:
        os_name = "Linux"
    else:
        os_name = "Khác"

    if "edg/" in ua_lower:
        browser = "Edge"
    elif "opr/" in ua_lower or "opera" in ua_lower:
        browser = "Opera"
    elif "chrome/" in ua_lower and "chromium" not in ua_lower:
        browser = "Chrome"
    elif "safari/" in ua_lower and "chrome/" not in ua_lower:
        browser = "Safari"
    elif "firefox/" in ua_lower:
        browser = "Firefox"
    else:
        browser = "Khác"

    return browser, os_name, device


@app.before_request
def _track_visitor():
    if request.method != "GET":
        return
    path = request.path
    if (
        path.startswith("/static")
        or path.startswith("/api")
        or path.startswith("/html5game")
        or path.startswith("/TeTe_game")
        or path == "/favicon.ico"
        or any(
            path.endswith(ext)
            for ext in [
                ".css",
                ".js",
                ".png",
                ".jpg",
                ".jpeg",
                ".svg",
                ".ico",
                ".woff",
                ".woff2",
                ".ttf",
                ".map",
                ".mp4",
                ".pt",
            ]
        )
    ):
        return

    try:
        ip = _get_client_ip()
        ua_str = request.headers.get("User-Agent", "")
        browser, os_name, device = _parse_ua(ua_str)
        page_name = _get_page_name(path)
        referrer = request.referrer or ""
        created_at = _utc_now_iso()

        with _db() as conn:
            conn.execute(
                """
                INSERT INTO visits (ip_address, user_agent, browser, os_name, device_type, page_path, page_name, referrer, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (ip, ua_str[:250], browser, os_name, device, path, page_name, referrer[:250], created_at),
            )
    except Exception as e:
        print(f"Error logging visit: {e}")

# ===== AI GIẢ LẬP =====
def analyze_audio(file_path):
    # Sau này thay bằng model TensorFlow/PyTorch
    return random.choice(["normal", "danger"])

@app.route("/")
def home():
    return render_template("index.html")

@app.route("/login")
def login():
    return render_template("login.html")

@app.route("/cctv")
def cctv():
    mode = request.args.get("mode", "animal")
    return render_template("camera.html", mode=mode)

@app.route("/map")
def map_view():
    # Default camera location (edit these values to match your real CCTV position)
    camera = {
        "id": "cctv-1",
        "name": "CCTV / AI CAM",
        "lat": 10.8231,   # Ho Chi Minh City (example)
        "lng": 106.6297,  # Ho Chi Minh City (example)
        "url": "/cctv",
        # Same stream used in templates/camera.html
        "stream_url": "http://192.168.1.3:8080/video",
    }
    return render_template("map.html", camera=camera)

@app.route("/register")
def goRegister():
    return render_template("register.html")

@app.route("/game")
def game():
    return render_template("TeTe_game/index.html")


@app.route("/scan")
def scan():
    return render_template("scan.html")

@app.route("/about")
def about():
    return render_template("about.html")


@app.route("/species")
@app.route("/notes")
@app.route("/tete-notes")
def species():
    return render_template("species_guide.html")


@app.route("/api/feedback", methods=["GET"])
def get_feedback():
    try:
        with _db() as conn:
            rows = conn.execute(
                """
                SELECT id, name, email, role, message, created_at
                FROM feedbacks
                ORDER BY id DESC
                LIMIT 30
                """
            ).fetchall()
        feedbacks = [
            {
                "id": r["id"],
                "name": r["name"],
                "email": r["email"],
                "role": r["role"] or "Cộng tác viên yêu thiên nhiên",
                "message": r["message"],
                "created_at": r["created_at"],
            }
            for r in rows
        ]
        return jsonify({"feedbacks": feedbacks})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/feedback", methods=["POST"])
def post_feedback():
    data = request.get_json(silent=True) or request.form
    name = (data.get("name") or "").strip()
    email = (data.get("email") or "").strip()
    role = (data.get("role") or "").strip()
    message = (data.get("message") or "").strip()

    if not name or not message:
        return jsonify({"error": "Vui lòng nhập tên và lời nhắn của bạn."}), 400

    created_at = _utc_now_iso()
    try:
        with _db() as conn:
            cur = conn.execute(
                """
                INSERT INTO feedbacks (name, email, role, message, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (name, email or None, role or "Khách truy cập", message, created_at),
            )
            feedback_id = cur.lastrowid
        return jsonify({
            "success": True,
            "message": "Cảm ơn bạn! Bình luận và lời nhắn của bạn đã được gửi thành công đến đội ngũ phát triển.",
            "feedback": {
                "id": feedback_id,
                "name": name,
                "email": email,
                "role": role or "Khách truy cập",
                "message": message,
                "created_at": created_at,
            }
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/visits/stats", methods=["GET"])
def get_visit_stats():
    try:
        today_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        today_prefix = f"{today_date}%"

        with _db() as conn:
            total_visits = conn.execute("SELECT COUNT(*) FROM visits").fetchone()[0]
            unique_visitors = conn.execute("SELECT COUNT(DISTINCT ip_address) FROM visits").fetchone()[0]
            today_visits = conn.execute(
                "SELECT COUNT(*) FROM visits WHERE created_at LIKE ?", (today_prefix,)
            ).fetchone()[0]
            today_unique = conn.execute(
                "SELECT COUNT(DISTINCT ip_address) FROM visits WHERE created_at LIKE ?", (today_prefix,)
            ).fetchone()[0]

            last_row = conn.execute(
                "SELECT created_at, browser, os_name, device_type, page_name FROM visits ORDER BY id DESC LIMIT 1"
            ).fetchone()

            last_visit = None
            if last_row:
                last_visit = {
                    "created_at": last_row["created_at"],
                    "browser": last_row["browser"],
                    "os_name": last_row["os_name"],
                    "device_type": last_row["device_type"],
                    "page_name": last_row["page_name"],
                }

            rows = conn.execute(
                """
                SELECT id, browser, os_name, device_type, page_path, page_name, created_at
                FROM visits
                ORDER BY id DESC
                LIMIT 50
                """
            ).fetchall()

            recent_visits = [
                {
                    "id": r["id"],
                    "browser": r["browser"],
                    "os_name": r["os_name"],
                    "device_type": r["device_type"],
                    "page_path": r["page_path"],
                    "page_name": r["page_name"] or r["page_path"],
                    "created_at": r["created_at"],
                }
                for r in rows
            ]

        return jsonify({
            "total_visits": total_visits,
            "unique_visitors": unique_visitors,
            "today_visits": today_visits,
            "today_unique": today_unique,
            "last_visit": last_visit,
            "recent_visits": recent_visits,
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/visits/clear", methods=["POST"])
def clear_visits():
    try:
        with _db() as conn:
            conn.execute("DELETE FROM visits")
        return jsonify({"ok": True, "message": "Đã xóa toàn bộ lịch sử truy cập."})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/visitors")
@app.route("/traffic")
def visitors_page():
    return render_template("visitors.html")


@app.route("/hunter_spot")
def hunter_spot():
    return render_template("camera.html", mode="hunter")

@app.route("/html5game/<path:filename>")
def gamemaker_html5game(filename):
    return send_from_directory(os.path.join(GAMEMAKER_DIR, "html5game"), filename)


@app.route("/TeTe_game/<path:filename>")
def gamemaker_root_files(filename):
    return send_from_directory(GAMEMAKER_DIR, filename)


@app.route("/api/events", methods=["GET"])
def list_events():
    try:
        limit = int(request.args.get("limit", "50"))
    except ValueError:
        limit = 50
    limit = max(1, min(limit, 200))

    with _db() as conn:
        rows = conn.execute(
            """
            SELECT id, event_type, probability, source, created_at, image_path, video_path
            FROM events
            ORDER BY id DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()

    events = []
    for r in rows:
        events.append(
            {
                "id": r["id"],
                "event_type": r["event_type"],
                "probability": r["probability"],
                "source": r["source"],
                "created_at": r["created_at"],
                "image_url": f"/static/{r['image_path']}" if r["image_path"] else None,
                "video_url": f"/static/{r['video_path']}" if r["video_path"] else None,
            }
        )

    return jsonify({"events": events})


@app.route("/api/events", methods=["POST"])
def create_event():
    event_type = (request.form.get("event_type") or "").strip()
    source = (request.form.get("source") or "").strip() or None

    prob_raw = request.form.get("probability")
    probability = None
    if prob_raw is not None and prob_raw != "":
        try:
            probability = float(prob_raw)
        except ValueError:
            probability = None

    if event_type not in {"TeTe", "CayVoiMoc", "Nguy hiem"}:
        return jsonify({"error": "event_type must be TeTe, CayVoiMoc, or Nguy hiem"}), 400

    snapshot = request.files.get("snapshot")
    video = request.files.get("video")

    image_path = _save_upload(snapshot, DETECTIONS_IMG_DIR, ".jpg")
    video_path = _save_upload(video, DETECTIONS_VIDEO_DIR, ".webm")

    created_at = _utc_now_iso()

    with _db() as conn:
        cur = conn.execute(
            """
            INSERT INTO events (event_type, probability, source, created_at, image_path, video_path)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (event_type, probability, source, created_at, image_path, video_path),
        )
        event_id = cur.lastrowid

    return jsonify(
        {
            "id": event_id,
            "event_type": event_type,
            "probability": probability,
            "source": source,
            "created_at": created_at,
            "image_url": f"/static/{image_path}" if image_path else None,
            "video_url": f"/static/{video_path}" if video_path else None,
        }
    )


@app.route("/api/events/clear", methods=["POST"])
def clear_events():
    with _db() as conn:
        rows = conn.execute("SELECT image_path, video_path FROM events").fetchall()
        conn.execute("DELETE FROM events")

    deleted_files = 0
    for r in rows:
        if _safe_unlink_under(DETECTIONS_DIR, r["image_path"]):
            deleted_files += 1
        if _safe_unlink_under(DETECTIONS_DIR, r["video_path"]):
            deleted_files += 1

    return jsonify({"ok": True, "deleted_files": deleted_files})

@app.route("/analyze", methods=["POST"])
def analyze():
    audio = request.files["audio"]
    latitude = request.form.get("latitude")
    longitude = request.form.get("longitude")

    filepath = os.path.join(app.config["UPLOAD_FOLDER"], audio.filename)
    audio.save(filepath)

    result = analyze_audio(filepath)

    return jsonify({
        "status": result,
        "latitude": latitude,
        "longitude": longitude
    })

@app.route("/api/predict", methods=["POST"])
def predict_api():
    if "image" not in request.files and "file" not in request.files:
        return jsonify({"error": "No image file provided"}), 400
        
    file = request.files.get("image") or request.files.get("file")
    img_bytes = file.read()
    
    nparr = np.frombuffer(img_bytes, np.uint8)
    img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    
    if img is None:
        return jsonify({"error": "Invalid image format"}), 400
        
    h, w, _ = img.shape
    detections = []
    
    # 1. Primary open-vocabulary detection with YOLO-World
    if yolo_world_model is not None:
        try:
            results = yolo_world_model(img, conf=0.15)
            for r in results:
                boxes = r.boxes
                for box in boxes:
                    x1, y1, x2, y2 = box.xyxy[0].tolist()
                    conf = float(box.conf[0])
                    cls_id = int(box.cls[0])
                    raw_cls = r.names[cls_id] if hasattr(r, 'names') and cls_id in r.names else TARGET_CLASSES[cls_id if cls_id < len(TARGET_CLASSES) else 0]
                    
                    cls_name = raw_cls.lower()
                    if "civet" in cls_name or "masked" in cls_name:
                        standard_name = "masked palm civet"
                    elif "pangolin" in cls_name or "tete" in cls_name:
                        standard_name = "pangolin"
                    else:
                        standard_name = raw_cls
                        
                    label_vi = CLASS_VI_MAP.get(standard_name.lower(), standard_name)
                    detections.append({
                        "box": [round(x1, 1), round(y1, 1), round(x2, 1), round(y2, 1)],
                        "confidence": round(conf, 3),
                        "class": standard_name,
                        "label_vi": label_vi,
                        "source": "YOLO-World"
                    })
        except Exception as e:
            print("YOLO-World prediction error:", e)
            
    # 2. Fallback detection with YOLOv8 best.pt if needed
    if not detections and yolo_model is not None:
        try:
            results = yolo_model(img, conf=0.2)
            for r in results:
                boxes = r.boxes
                for box in boxes:
                    x1, y1, x2, y2 = box.xyxy[0].tolist()
                    conf = float(box.conf[0])
                    cls_id = int(box.cls[0])
                    raw_name = str(r.names[cls_id]) if hasattr(r, 'names') and cls_id in r.names else str(cls_id)
                    lower_name = raw_name.lower()
                    
                    if any(k in lower_name for k in ["tete", "te_te", "pangolin", "0"]):
                        standard_name = "pangolin"
                    elif any(k in lower_name for k in ["civet", "cay_voi_moc", "masked"]):
                        standard_name = "masked palm civet"
                    else:
                        standard_name = raw_name
                        
                    label_vi = CLASS_VI_MAP.get(standard_name.lower(), standard_name)
                    detections.append({
                        "box": [round(x1, 1), round(y1, 1), round(x2, 1), round(y2, 1)],
                        "confidence": round(conf, 3),
                        "class": standard_name,
                        "label_vi": label_vi,
                        "source": "YOLOv8"
                    })
        except Exception as e:
            print("YOLOv8 prediction error:", e)

    # 3. CLIP zero-shot classification evaluation & proposal fallback
    clip_result = None
    if clip_classifier is not None:
        try:
            pil_img = Image.fromarray(cv2.cvtColor(img, cv2.COLOR_BGR2RGB))
            clip_res = clip_classifier(
                pil_img, 
                candidate_labels=["a photo of a pangolin", "a photo of a masked palm civet", "a photo of an empty forest or background"]
            )
            top_pred = clip_res[0]
            label = top_pred["label"]
            score = top_pred["score"]
            
            if "pangolin" in label and score >= 0.35:
                clip_result = {"class": "pangolin", "label_vi": "Tê Tê", "confidence": round(score, 3)}
            elif "masked palm civet" in label and score >= 0.35:
                clip_result = {"class": "masked palm civet", "label_vi": "Cầy Vòi Mốc", "confidence": round(score, 3)}
                
            if not detections and clip_result:
                detections.append({
                    "box": [round(w * 0.15, 1), round(h * 0.15, 1), round(w * 0.85, 1), round(h * 0.85, 1)],
                    "confidence": clip_result["confidence"],
                    "class": clip_result["class"],
                    "label_vi": clip_result["label_vi"],
                    "source": "CLIP"
                })
        except Exception as e:
            print("CLIP classification error:", e)
            
    return jsonify({
        "detections": detections,
        "clip_info": clip_result,
        "image_size": [w, h]
    })


@app.route("/api/predict_pt", methods=["POST"])
def predict_pt_api():
    """Endpoint suy luận trực tiếp với file model PyTorch gốc (manhnd_best_model.pt) không nén."""
    if manhnd_model is None:
        return jsonify({"error": "Model manhnd_best_model.pt chưa được khởi tạo hoặc không tìm thấy."}), 500

    if "image" not in request.files and "file" not in request.files:
        return jsonify({"error": "No image file provided"}), 400

    file = request.files.get("image") or request.files.get("file")
    img_bytes = file.read()
    nparr = np.frombuffer(img_bytes, np.uint8)
    img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

    if img is None:
        return jsonify({"error": "Invalid image format"}), 400

    h, w, _ = img.shape
    detections = []
    conf_thresh = float(request.args.get("conf", 0.25))

    try:
        results = manhnd_model(img, conf=conf_thresh)
        for r in results:
            boxes = r.boxes
            for box in boxes:
                x1, y1, x2, y2 = box.xyxy[0].tolist()
                conf = float(box.conf[0])
                cls_id = int(box.cls[0])
                raw_name = str(r.names[cls_id]) if hasattr(r, 'names') and cls_id in r.names else str(cls_id)
                lower_name = raw_name.lower()

                if "pangolin" in lower_name or "tete" in lower_name or cls_id == 0:
                    standard_name = "pangolin"
                    result_type = "tete"
                elif "civet" in lower_name or "masked" in lower_name or cls_id == 1:
                    standard_name = "masked palm civet"
                    result_type = "civet"
                else:
                    standard_name = raw_name
                    result_type = "unknown"

                label_vi = CLASS_VI_MAP.get(standard_name.lower(), standard_name)
                detections.append({
                    "box": [round(x1, 1), round(y1, 1), round(x2, 1), round(y2, 1)],
                    "confidence": round(conf, 3),
                    "class": standard_name,
                    "label_vi": label_vi,
                    "type": result_type,
                    "source": "YOLO-PT (manhnd_best_model.pt)"
                })

        # Sắp xếp theo confidence giảm dần
        detections.sort(key=lambda d: d["confidence"], reverse=True)

        type_detected = "unknown"
        has_tete = any(d["type"] == "tete" for d in detections)
        has_civet = any(d["type"] == "civet" for d in detections)
        if has_tete and has_civet:
            type_detected = detections[0]["type"]
        elif has_tete:
            type_detected = "tete"
        elif has_civet:
            type_detected = "civet"

        max_conf = detections[0]["confidence"] if detections else 0.0
        all_scores = [
            {"className": f"{d['label_vi']} ({d['class']})", "probability": d["confidence"]}
            for d in detections
        ]

        return jsonify({
            "success": True,
            "type": type_detected,
            "confidence": max_conf,
            "detections": detections,
            "allScores": all_scores,
            "image_size": [w, h],
            "model": "manhnd_best_model.pt (PyTorch Uncompressed)"
        })

    except Exception as e:
        print("manhnd_best_model.pt prediction error:", e)
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    app.run(debug=True)

