"""
Requirements:
    pip install opencv-python numpy
    Download model files (see bottom of this file for instructions).
"""

import cv2
import numpy as np

# ── Config ────────────────────────────────────────────────────────────────────
CONFIDENCE_THRESHOLD = 0.5   # Only show detections above this confidence
CAMERA_INDEX = 0             # 0 = default webcam; change for USB/Pi cam

# MobileNet SSD class labels
CLASSES = [
    "background", "aeroplane", "bicycle", "bird", "boat",
    "bottle", "bus", "car", "cat", "chair", "cow", "diningtable",
    "dog", "horse", "motorbike", "person", "pottedplant",
    "sheep", "sofa", "train", "tvmonitor"
]

# Colours per class (BGR)
COLORS = np.random.uniform(0, 255, size=(len(CLASSES), 3))


def load_model(prototxt="MobileNetSSD_deploy.prototxt",
               weights="MobileNetSSD_deploy.caffemodel"):
    """Load the pre-trained MobileNet SSD model."""
    print("[INFO] Loading model...")
    net = cv2.dnn.readNetFromCaffe(prototxt, weights)
    print("[INFO] Model loaded.")
    return net


def detect_objects(frame, net):
    """Run detection on a single frame. Returns list of (label, confidence, box)."""
    h, w = frame.shape[:2]

    # Pre-process frame → blob
    blob = cv2.dnn.blobFromImage(
        cv2.resize(frame, (300, 300)),
        scalefactor=0.007843,
        size=(300, 300),
        mean=127.5
    )
    net.setInput(blob)
    detections = net.forward()

    results = []
    for i in range(detections.shape[2]):
        confidence = detections[0, 0, i, 2]
        if confidence < CONFIDENCE_THRESHOLD:
            continue

        class_id = int(detections[0, 0, i, 1])
        label = CLASSES[class_id]

        # Bounding box in pixel coords
        box = detections[0, 0, i, 3:7] * np.array([w, h, w, h])
        x1, y1, x2, y2 = box.astype("int")

        results.append((label, confidence, (x1, y1, x2, y2)))

    return results


def draw_detections(frame, detections):
    """Draw bounding boxes and labels on the frame."""
    for label, confidence, (x1, y1, x2, y2) in detections:
        class_id = CLASSES.index(label)
        color = COLORS[class_id]

        # Box
        cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)

        # Label with confidence
        text = f"{label}: {confidence:.0%}"
        y_text = y1 - 10 if y1 > 20 else y1 + 20
        cv2.putText(frame, text, (x1, y_text),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)

    return frame


def announce(detections):
    """
    Simple text announcement of what's detected.
    Later: swap print() for text-to-speech (e.g. pyttsx3).
    """
    if not detections:
        return

    # Group by label
    seen = {}
    for label, confidence, _ in detections:
        seen[label] = max(seen.get(label, 0), confidence)

    parts = [f"{label} ({conf:.0%})" for label, conf in seen.items()]
    print("[DETECTED]", ", ".join(parts))


def main():
    net = load_model()

    print("[INFO] Starting camera...")
    cap = cv2.VideoCapture(CAMERA_INDEX)

    if not cap.isOpened():
        print("[ERROR] Cannot open camera.")
        return

    frame_count = 0

    while True:
        ret, frame = cap.read()
        if not ret:
            print("[ERROR] Failed to grab frame.")
            break

        # Run detection every frame (reduce to every 2-3 frames for speed)
        detections = detect_objects(frame, net)

        # Print to console every 30 frames (~1 sec at 30fps)
        frame_count += 1
        if frame_count % 30 == 0:
            announce(detections)

        # Draw and show
        frame = draw_detections(frame, detections)
        cv2.imshow("Vision Assistant", frame)

        # Press 'q' to quit
        if cv2.waitKey(1) & 0xFF == ord("q"):
            break

    cap.release()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()


# ── Model Download Instructions ───────────────────────────────────────────────
# You need two files in the same folder as this script:
#
# 1. MobileNetSSD_deploy.prototxt
#    https://raw.githubusercontent.com/chuanqi305/MobileNet-SSD/master/deploy.prototxt
#
# 2. MobileNetSSD_deploy.caffemodel
#    https://drive.google.com/open?id=0B3gersZ2cHIxRm5PMWRoTkdHdHc
#    (or search "MobileNetSSD_deploy.caffemodel" on GitHub)
#
# Quick download with wget:
#   wget https://raw.githubusercontent.com/chuanqi305/MobileNet-SSD/master/deploy.prototxt \
#        -O MobileNetSSD_deploy.prototxt
#
# Install dependencies:
#   pip install opencv-python numpy