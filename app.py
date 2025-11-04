import gradio_client.utils as gutils
import gradio as gr
import numpy as np
import json, os, math, cv2
from PIL import Image, ImageDraw
from ultralytics import YOLO
from formulas import calculate_formula, calculate_discrepancy
from utils import line_length, midpoint
from image import letterbox_image, draw_yolo_boxes

model = YOLO("best.pt")

if hasattr(gutils, "get_type"):
    old_get_type = gutils.get_type
    def safe_get_type(schema):
        if isinstance(schema, bool):
            return type(schema)
        return old_get_type(schema)
    gutils.get_type = safe_get_type

if hasattr(gutils, "_json_schema_to_python_type"):
    old_json_schema_to_python_type = gutils._json_schema_to_python_type
    def safe_json_schema_to_python_type(schema, defs=None):
        if isinstance(schema, bool):
            return "Any"
        try:
            return old_json_schema_to_python_type(schema, defs)
        except Exception:
            return "Any"
    gutils._json_schema_to_python_type = safe_json_schema_to_python_type


SAVE_DIR = "/data1/sandeep_projects/Dental/saved_v18_mm"
os.makedirs(SAVE_DIR, exist_ok=True)
for d in ["original", "resized", "annotated"]:
    os.makedirs(os.path.join(SAVE_DIR, d), exist_ok=True)
JSON_PATH = os.path.join(SAVE_DIR, "annotations.json")

segments, points, temp_points = [], [], []
base_image, original_image, pixel_per_mm = None, None, None
if os.path.exists(JSON_PATH):
    with open(JSON_PATH, "r") as f:
        all_annotations = json.load(f)
else:
    all_annotations = {}


def render_with_segments(show_measurements=True):
    global base_image, segments, pixel_per_mm, temp_points
    if base_image is None:
        return None
    img = Image.fromarray(base_image.copy())
    draw = ImageDraw.Draw(img)
    for i, ((x1, y1), (x2, y2)) in enumerate(segments):
        draw.line([(x1, y1), (x2, y2)], fill="red", width=3)
        px_len = line_length((x1, y1), (x2, y2))
        mx, my = midpoint((x1, y1), (x2, y2))
        if i == 0:
            draw.ellipse((mx-5, my-5, mx+5, my+5), fill="yellow")
            if show_measurements:
                draw.text((x2+6, y2), "5 mm (ref)", fill="yellow")
        elif show_measurements and pixel_per_mm:
            real_mm = px_len / pixel_per_mm
            draw.text((x2+6, y2), f"{real_mm:.1f} mm", fill="yellow")
    for (x, y) in temp_points:
        draw.ellipse((x-4, y-4, x+4, y+4), fill="blue")
    return np.array(img)

def preprocess_image(image):
    global base_image, original_image, segments, points, temp_points, pixel_per_mm
    points, segments, temp_points, pixel_per_mm = [], [], [], None
    if image is None:
        return None, "⚠️ Upload an image first."
    original_image = np.array(image)

    # Run YOLO detection first
    yolo_result = draw_yolo_boxes(image)

    # Resize and pad to 640x640 for consistent display
    resized, orig_shape, scale, left, top = letterbox_image(Image.fromarray(yolo_result), (640, 640))
    base_image = resized

    return base_image, f"📏 Original: {orig_shape}, Scale: {scale:.3f}, Padding: ({left},{top}) — YOLO boxes shown"

def mark_point(image, evt: gr.SelectData):
    global points, segments, temp_points, base_image, pixel_per_mm
    if base_image is None:
        return None, "⚠️ Upload an image first."
    x, y = evt.index
    points.append((x, y))
    temp_points = [(x, y)] if len(points) == 1 else temp_points
    msg = ""
    if len(points) == 2:
        p1, p2 = points
        seg_len = line_length(p1, p2)
        temp_points = []
        if len(segments) == 0:
            pixel_per_mm = seg_len / 5.0
            msg = f"📐 Calibration: {seg_len:.2f}px = 5 mm"
        else:
            real_mm = seg_len / pixel_per_mm if pixel_per_mm else None
            msg = f"🦷 Line {len(segments)}: {real_mm:.1f} mm"
        segments.append((p1, p2))
        points = []
    rendered = render_with_segments()
    return rendered, msg or "✅ Click next point."

def undo_last(image):
    global segments, pixel_per_mm, temp_points, points
    if not segments:
        temp_points, points = [], []
        return image, "⚠️ Nothing to undo."
    segments.pop()
    if len(segments) == 0:
        pixel_per_mm = None
    rendered = render_with_segments()
    return rendered, f"↩️ Undone. Remaining: {len(segments)}"


def calculate_only(image, formula_choice, gender):
    global segments, pixel_per_mm
    if base_image is None or not segments:
        return "⚠️ Upload and draw measurements first."
    lengths_mm = []
    for i, (p1, p2) in enumerate(segments):
        px_len = line_length(p1, p2)
        real_mm = 5.0 if i == 0 else (px_len / pixel_per_mm)
        lengths_mm.append(round(real_mm, 1))
    disc_data, _ = calculate_discrepancy(lengths_mm, formula_choice, gender)
    msg = f"🧮 Formula: {formula_choice}\n"
    for i, l in enumerate(lengths_mm[1:7]):
        msg += f"Tooth {i+1}: {l:.1f} mm\n"
    if disc_data:
        msg += (f"\nPredicted (per side): {disc_data['predicted_mm_per_side']} mm\n"
                f"Left Space: {disc_data['left_space_mm']} mm\n"
                f"Right Space: {disc_data['right_space_mm']} mm\n"
                f"Total Discrepancy: {disc_data['discrepancy_mm']} mm")
    return msg

def submit_and_save(image, name, formula_choice, gender):
    global segments, all_annotations, pixel_per_mm, original_image, base_image
    if not name.strip():
        return "⚠️ Enter a valid name."
    if base_image is None or original_image is None:
        return "⚠️ Upload first."
    if len(segments) < 2:
        return "⚠️ Draw calibration + at least one measurement."
    orig_path = os.path.join(SAVE_DIR, "original", f"{name}.jpg")
    resized_path = os.path.join(SAVE_DIR, "resized", f"{name}.jpg")
    annotated_path = os.path.join(SAVE_DIR, "annotated", f"{name}.jpg")
    Image.fromarray(original_image).save(orig_path)
    Image.fromarray(base_image).save(resized_path)
    annotated = render_with_segments()
    Image.fromarray(annotated).save(annotated_path)
    data = []
    for i, (p1, p2) in enumerate(segments):
        px_len = line_length(p1, p2)
        real_mm = 5.0 if i == 0 else (px_len / pixel_per_mm)
        data.append({"p1": p1, "p2": p2, "pixels": round(px_len, 2), "mm": round(real_mm, 1)})
    lengths_mm = [d["mm"] for d in data]
    disc_data, _ = calculate_discrepancy(lengths_mm, formula_choice, gender)
    all_annotations[name] = {
        "formula": formula_choice,
        "gender": gender,
        "pixel_per_mm": pixel_per_mm,
        "segments": data,
        "discrepancy_mm": disc_data,
        "paths": {"original": orig_path, "resized": resized_path, "annotated": annotated_path}
    }
    with open(JSON_PATH, "w") as f:
        json.dump(all_annotations, f, indent=4)
    msg = f"✅ Saved '{name}' — Formula: {formula_choice}\n"
    if disc_data:
        msg += (f"Predicted (per side): {disc_data['predicted_mm_per_side']} mm\n"
                f"Left Space: {disc_data['left_space_mm']} mm\n"
                f"Right Space: {disc_data['right_space_mm']} mm\n"
                f"Total Discrepancy: {disc_data['discrepancy_mm']} mm\n")
    msg += f"Files saved in {SAVE_DIR}"
    segments.clear()
    return msg

with gr.Blocks(title="🦷 Dental Annotation Studio v18 — YOLO Integration") as demo:
    gr.HTML("<h2 style='text-align:center;'>🦷 Dental Annotation Studio — with YOLO Bounding Boxes</h2>")
    with gr.Row():
        upload_img = gr.Image(label="Upload Image", type="numpy", interactive=True)
        canvas = gr.Image(label="Annotate + Measure (mm)", interactive=False)
    img_name = gr.Textbox(label="📝 File Name", placeholder="e.g. case_01")
    with gr.Row():
        formula_choice = gr.Dropdown(["Moyers", "Tanaka–Johnston"], label="🧮 Formula", value="Moyers")
        gender = gr.Dropdown(["Male", "Female"], label="⚧ Gender", value="Male")
    with gr.Row():
        calc_btn = gr.Button("🧮 Calculate Only (Preview)")
        save_btn = gr.Button("💾 Save + Submit")
        undo_btn = gr.Button("↩️ Undo Last Line")
    status = gr.Textbox(label="Status", interactive=False, lines=10)

    upload_img.upload(preprocess_image, upload_img, [canvas, status])
    canvas.select(mark_point, [canvas], [canvas, status])
    undo_btn.click(undo_last, [canvas], [canvas, status])
    calc_btn.click(calculate_only, [canvas, formula_choice, gender], [status])
    save_btn.click(submit_and_save, [canvas, img_name, formula_choice, gender], [status])

demo.queue()
demo.launch(server_name="0.0.0.0", server_port=7860, share=True)
