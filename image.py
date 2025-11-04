import numpy as np
import json, os, math, cv2
from PIL import Image, ImageDraw
from ultralytics import YOLO

def letterbox_image(image, new_size=(640, 640)):
    img = np.array(image)
    h, w = img.shape[:2]
    scale = min(new_size[0] / w, new_size[1] / h)
    nw, nh = int(w * scale), int(h * scale)
    img_resized = cv2.resize(img, (nw, nh), interpolation=cv2.INTER_LINEAR)
    new_img = np.full((new_size[1], new_size[0], 3), 114, dtype=np.uint8)
    top, left = (new_size[1] - nh) // 2, (new_size[0] - nw) // 2
    new_img[top:top+nh, left:left+nw] = img_resized
    return new_img, (w, h), scale, left, top

def draw_yolo_boxes(image):
    """Runs YOLO detection and overlays bounding boxes on the image."""
    model = YOLO("best.pt")
    results = model(image, verbose=False)
    img = np.array(image).copy()

    for r in results:
        boxes = r.boxes.xyxy.cpu().numpy()
        confs = r.boxes.conf.cpu().numpy()
        cls = r.boxes.cls.cpu().numpy()
        names = r.names

        for (x1, y1, x2, y2), c, cl in zip(boxes, confs, cls):
            if c>0.6:
                label = f"{names[int(cl)]} {c:.2f}"
                print(label)
                cv2.rectangle(img, (int(x1), int(y1)), (int(x2), int(y2)), (0, 255, 0), 2)
                cv2.putText(img, label, (int(x1), int(y1) - 5),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1)
    return img