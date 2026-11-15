
"""AI accident detection: YOLOv8 vehicle tracking + collision heuristics."""

import cv2
import numpy as np
from collections import defaultdict, deque
from ultralytics import YOLO

VEHICLES = [2, 3, 5, 7]  # car, motorcycle, bus, truck
_model = None


def get_model():
    global _model
    if _model is None:
        _model = YOLO("yolov8n.pt")
    return _model


def iou(a, b):
    x1, y1 = max(a[0], b[0]), max(a[1], b[1])
    x2, y2 = min(a[2], b[2]), min(a[3], b[3])

    inter = max(0, x2 - x1) * max(0, y2 - y1)

    union = (
        (a[2] - a[0]) * (a[3] - a[1])
        + (b[2] - b[0]) * (b[3] - b[1])
        - inter
    )

    return inter / union if union > 0 else 0.0


def analyze_video(in_path, out_path, snap_dir, job_id, on_progress=lambda p: None):
    model = get_model()
    cap = cv2.VideoCapture(in_path)

    if not cap.isOpened():
        raise ValueError("Unable to open input video")

    fps = cap.get(cv2.CAP_PROP_FPS) or 25
    W = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    H = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT)) or 1

    writer = None

    for codec in ("avc1", "mp4v"):
        w = cv2.VideoWriter(
            out_path,
            cv2.VideoWriter_fourcc(*codec),
            fps,
            (W, H)
        )

        if w.isOpened():
            writer = w
            break
        w.release()

    centers = defaultdict(lambda: deque(maxlen=6))
    speeds = defaultdict(lambda: deque(maxlen=max(10, int(fps * 2))))
    overlap = defaultdict(int)
    last_alert = {}

    events = []
    frame_i = 0

    while True:
        ok, frame = cap.read()

        if not ok:
            break

        frame_i += 1

        # Track vehicles using ByteTrack
        res = model.track(
            frame,
            persist=True,
            tracker="bytetrack.yaml",
            classes=VEHICLES,
            conf=0.35,
            verbose=False
        )[0]

        boxes = {}

        if res.boxes is not None and res.boxes.id is not None:
            for b, tid in zip(
                res.boxes.xyxy.cpu().numpy(),
                res.boxes.id.int().cpu().tolist()
            ):
                boxes[tid] = b

        # Calculate vehicle movement
        for tid, b in boxes.items():
            c = (
                (b[0] + b[2]) / 2,
                (b[1] + b[3]) / 2
            )

            diag = np.hypot(
                b[2] - b[0],
                b[3] - b[1]
            ) or 1

            hist = centers[tid]

            if hist:
                movement = np.hypot(
                    c[0] - hist[-1][0],
                    c[1] - hist[-1][1]
                ) / diag

                speeds[tid].append(movement)

            hist.append(c)

        alerts = []
        ids = list(boxes)

        # Detect possible collisions
        for i in range(len(ids)):
            for j in range(i + 1, len(ids)):
                a, b = ids[i], ids[j]
                key = tuple(sorted((a, b)))

                ov = iou(boxes[a], boxes[b])

                overlap[key] = (
                    overlap[key] + 1 if ov > 0.12 else 0
                )

                if overlap[key] < max(3, int(fps * 0.2)):
                    continue

                # Detect sudden stopping
                def drop(t):
                    s = list(speeds[t])

                    if len(s) < 10:
                        return 0

                    peak = max(s[:-3])
                    now = np.mean(s[-3:])

                    return (
                        (peak - now) / peak
                        if peak > 0.04 else 0
                    )

                d = max(drop(a), drop(b))

                if (
                    d > 0.6
                    and frame_i - last_alert.get(key, -10**9) > fps * 5
                ):
                    last_alert[key] = frame_i

                    confidence = float(
                        min(0.99, 0.5 + ov + d * 0.3)
                    )

                    alerts.append((key, confidence))

        annotated = res.plot()

        # Save accident snapshots
        for key, confidence in alerts:
            t = frame_i / fps
            fname = f"{job_id}_{frame_i}.jpg"

            snap = annotated.copy()

            cv2.putText(
                snap,
                "ACCIDENT",
                (20, 50),
                cv2.FONT_HERSHEY_SIMPLEX,
                1.4,
                (0, 0, 255),
                4
            )

            cv2.imwrite(f"{snap_dir}/{fname}", snap)

            events.append({
                "time": round(t, 1),
                "frame": frame_i,
                "confidence": round(confidence, 2),
                "vehicles": list(key),
                "snapshot": f"/outputs/{fname}"
            })

        # Display accident alert banner
        if any(
            frame_i - f < fps * 2
            for f in last_alert.values()
        ):
            cv2.rectangle(
                annotated,
                (0, 0),
                (W, 70),
                (0, 0, 200),
                -1
            )

            cv2.putText(
                annotated,
                "ACCIDENT DETECTED",
                (20, 48),
                cv2.FONT_HERSHEY_SIMPLEX,
                1.3,
                (255, 255, 255),
                3
            )

        if writer:
            writer.write(annotated)

        if frame_i % 5 == 0:
            on_progress(
                min(99, int(frame_i / total * 100))
            )

    cap.release()

    if writer:
        writer.release()

    return {
        "events": events,
        "frames": frame_i,
        "duration": round(frame_i / fps, 1)
    }
