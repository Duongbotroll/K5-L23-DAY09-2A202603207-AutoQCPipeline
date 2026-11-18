"""CHECK 6 — Ý kiến thứ hai: so nhãn với một model LỚN HƠN (yolo26l).   ★★★

Test:  pytest tests/test_second_opinion.py -q

Model cũng có thể sai, nên mọi issue ở đây đều là WARN: ảnh bị cờ vào hàng đợi cho NGƯỜI duyệt.

  P = dự đoán có conf >= conf  VÀ diện tích px >= min_area_px
  Với mỗi dự đoán r trong P: cands = nhãn (mọi lớp) có IoU(r, nhãn) >= iou_missing
   - cands rỗng                                            -> POSSIBLE_MISSING
   - có cands cùng lớp: IoU tốt nhất < iou_loose           -> POSSIBLE_LOOSE_BOX (ngược lại: không cờ)
   - không có cands cùng lớp: IoU tốt nhất khác lớp >= iou_match -> POSSIBLE_WRONG_CLASS
  Với mỗi dòng nhãn hợp lệ: IoU với mọi dự đoán (conf >= fp_conf) < iou_missing -> POSSIBLE_FALSE_POS
"""
from ..common import WARN, Issue, iou_xywh, parse_yolo_line
from ..model_cache import get_preds

NAME = "second_opinion"


def _label_lines(ds, stem):
    """[(số dòng gốc, lớp, box)] cho các dòng hợp lệ; dòng hỏng bị bỏ qua (label_format đã báo)."""
    out = []
    for ln, text in ds.read_label_lines(stem) or []:
        try:
            cls, x, y, w, h = parse_yolo_line(text)
        except ValueError:
            continue
        if 0 <= cls < len(ds.classes) and w > 0 and h > 0:
            out.append((ln, cls, (x, y, w, h)))
    return out


def run(ds, cfg, preds=None):
    s = cfg["second_opinion"]
    if preds is None:
        preds = get_preds(ds, cfg, "checker")
    issues = []

    for img in ds.image_files():
        stem = img.stem
        if stem not in preds or not ds.label_path(stem).exists():
            continue
        size = ds.image_size(stem)
        if not size:
            continue
        W, H = size
        labels = _label_lines(ds, stem)
        rows = preds[stem] or []

        # --- A. từ góc nhìn model: vật model thấy, nhãn có phủ đúng không?
        for r in rows:
            pcls, conf, box = int(r[0]), float(r[1]), tuple(r[2:6])
            if conf < s["conf"] or box[2] * W * box[3] * H < s["min_area_px"]:
                continue
            cands = [(iou_xywh(box, lbox), lcls) for _, lcls, lbox in labels]
            cands = [(iou, lcls) for iou, lcls in cands if iou >= s["iou_missing"]]
            same = [iou for iou, lcls in cands if lcls == pcls]
            other = [(iou, lcls) for iou, lcls in cands if lcls != pcls]
            cname = ds.classes[pcls] if 0 <= pcls < len(ds.classes) else str(pcls)

            if not cands:
                issues.append(Issue(NAME, WARN, "POSSIBLE_MISSING", stem,
                                    f"model thấy '{cname}' (conf {conf:.2f}) mà nhãn không có box",
                                    None, {"conf": round(conf, 4), "pred": [pcls, *box]}))
            elif same:
                best = max(same)
                if best < s["iou_loose"]:
                    issues.append(Issue(NAME, WARN, "POSSIBLE_LOOSE_BOX", stem,
                                        f"box '{cname}' lệch/lỏng so với model (IoU {best:.2f})",
                                        None, {"conf": round(conf, 4), "iou": round(best, 4)}))
            else:
                best_iou, best_cls = max(other)
                if best_iou >= s["iou_match"]:
                    lname = ds.classes[best_cls]
                    issues.append(Issue(NAME, WARN, "POSSIBLE_WRONG_CLASS", stem,
                                        f"nhãn '{lname}' nhưng model nói '{cname}' (IoU {best_iou:.2f})",
                                        None, {"conf": round(conf, 4), "iou": round(best_iou, 4)}))
                # IoU trong [iou_missing, iou_match): mơ hồ -> không cờ

        # --- B. từ góc nhìn nhãn: box nhãn không khớp vật nào model thấy
        fp_boxes = [tuple(r[2:6]) for r in rows if float(r[1]) >= s["fp_conf"]]
        for ln, lcls, lbox in labels:
            best = max((iou_xywh(lbox, b) for b in fp_boxes), default=0.0)
            if best < s["iou_missing"]:
                issues.append(Issue(NAME, WARN, "POSSIBLE_FALSE_POS", stem,
                                    f"box '{ds.classes[lcls]}' không khớp vật nào model thấy (IoU tốt nhất {best:.2f})",
                                    ln, {"iou": round(best, 4)}))

    return issues
