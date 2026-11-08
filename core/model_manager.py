"""
model_manager.py - Local Model Binary Resolution & Instantiation
Ensures 100% offline, air-gapped execution by loading all ONNX models directly
from the local 'models/' directory, supporting both Python and PyInstaller frozen builds.
"""

import sys
import os
from typing import Optional

_ocr_instance = None
_layout_instance = None
_table_instance = None


def get_base_dir() -> str:
    """Returns the base directory of the application, handling PyInstaller frozen bundles."""
    if getattr(sys, 'frozen', False):
        # Running inside PyInstaller frozen executable
        return getattr(sys, '_MEIPASS', os.path.dirname(sys.executable))
    # Running in standard Python workspace
    return os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))


def get_local_model_path(filename: str) -> str:
    """Resolves absolute path to a bundled ONNX model."""
    base_dir = get_base_dir()
    candidates = [
        os.path.join(base_dir, 'models', filename),
        os.path.join(base_dir, '_internal', 'models', filename),
        os.path.join(os.path.dirname(sys.executable), '_internal', 'models', filename),
        os.path.join(os.path.dirname(sys.executable), 'models', filename),
        os.path.join(os.getcwd(), 'models', filename)
    ]
    for c in candidates:
        if os.path.exists(c):
            return c

    return candidates[0]


def get_ocr_engine():
    """Initializes and returns cached offline RapidOCR engine."""
    global _ocr_instance
    if _ocr_instance is None:
        from rapidocr_onnxruntime import RapidOCR
        det_path = get_local_model_path("ch_PP-OCRv4_det_infer.onnx")
        rec_path = get_local_model_path("ch_PP-OCRv4_rec_infer.onnx")
        cls_path = get_local_model_path("ch_ppocr_mobile_v2.0_cls_infer.onnx")

        # Disable crop-level text_cls (use_cls=False): page-level orientation is already
        # handled by image_preprocessor.py, and crop-level cls falsely inverts English lines.
        kwargs = {"use_cls": False}
        if os.path.exists(det_path):
            kwargs["Det_model_path"] = det_path
        if os.path.exists(rec_path):
            kwargs["Rec_model_path"] = rec_path
        if os.path.exists(cls_path):
            kwargs["Cls_model_path"] = cls_path

        _ocr_instance = RapidOCR(**kwargs)
    return _ocr_instance


def get_layout_engine():
    """Initializes and returns cached offline RapidLayout engine."""
    global _layout_instance
    if _layout_instance is None:
        from rapid_layout import RapidLayout
        layout_path = get_local_model_path("layout_cdla.onnx")
        if os.path.exists(layout_path):
            _layout_instance = RapidLayout(model_dir_or_path=layout_path)
        else:
            _layout_instance = RapidLayout()
    return _layout_instance


def get_table_engine():
    """Initializes and returns cached offline RapidTable engine."""
    global _table_instance
    if _table_instance is None:
        from rapid_table import RapidTable, RapidTableInput
        table_path = get_local_model_path("slanet-plus.onnx")
        if os.path.exists(table_path):
            cfg = RapidTableInput(model_dir_or_path=table_path, use_ocr=False)
            _table_instance = RapidTable(cfg=cfg)
        else:
            cfg = RapidTableInput(use_ocr=False)
            _table_instance = RapidTable(cfg=cfg)
    return _table_instance
