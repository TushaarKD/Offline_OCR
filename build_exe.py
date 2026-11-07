"""
build_exe.py - Standalone Portable Windows Application Compiler
Uses PyInstaller to package DocMorph Pro into a 100% offline, self-contained
Windows executable directory with all ONNX models and GUI assets bundled.
"""

import os
import sys
import subprocess
import shutil

REQUIRED_MODELS = [
    "ch_PP-OCRv4_det_infer.onnx",
    "ch_PP-OCRv4_rec_infer.onnx",
    "ch_ppocr_mobile_v2.0_cls_infer.onnx",
    "layout_cdla.onnx",
    "slanet-plus.onnx"
]


def check_models():
    """Verify that all required offline ONNX models exist."""
    print("Checking bundled ONNX models...")
    models_dir = os.path.join(os.path.dirname(__file__), "models")
    if not os.path.exists(models_dir):
        raise FileNotFoundError(f"Missing models directory: {models_dir}")

    for m in REQUIRED_MODELS:
        p = os.path.join(models_dir, m)
        if not os.path.exists(p):
            raise FileNotFoundError(f"Missing required model: {p}")
        size_mb = os.path.getsize(p) / (1024 * 1024)
        print(f"  [OK] {m} ({size_mb:.2f} MB)")
    print("All required ONNX models present and verified.\n")


def build_app(mode: str = "onedir"):
    """
    Build standalone executable using PyInstaller.
    mode: 'onedir' (instant startup, portable directory) or 'onefile' (single packed .exe).
    """
    check_models()

    dist_dir = os.path.join(os.path.dirname(__file__), "dist")
    build_dir = os.path.join(os.path.dirname(__file__), "build")

    print(f"Building DocMorph Pro (mode: {mode})...")
    sep = ";" if sys.platform.startswith("win") else ":"

    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--noconfirm",
        f"--{mode}",
        "--windowed",
        "--name", "DocMorphPro",
        f"--add-data", f"models{sep}models",
        "--collect-all", "customtkinter",
        "--collect-all", "rapidocr_onnxruntime",
        "--collect-all", "rapid_layout",
        "--collect-all", "rapid_table",
        "--collect-all", "onnxruntime",
        "--hidden-import", "pymupdf",
        "--hidden-import", "docx",
        "--hidden-import", "cv2",
        "--hidden-import", "PIL",
        "app_gui.py"
    ]

    print("Running PyInstaller command:")
    print(" ".join(cmd))
    print("-" * 50)

    res = subprocess.run(cmd)
    if res.returncode != 0:
        print("\n[ERROR] PyInstaller compilation failed.")
        sys.exit(res.returncode)

    print("\n" + "=" * 50)
    print("BUILD SUCCESSFUL!")
    if mode == "onedir":
        app_path = os.path.join(dist_dir, "DocMorphPro", "DocMorphPro.exe")
        app_dir = os.path.join(dist_dir, "DocMorphPro")
        models_dest = os.path.join(app_dir, "models")
        if not os.path.exists(models_dest):
            shutil.copytree(models_dir, models_dest)
        print(f"Portable Application Folder: {app_dir}")
        print(f"Executable:                 {app_path}")
    else:
        app_path = os.path.join(dist_dir, "DocMorphPro.exe")
        print(f"Single Standalone EXE:      {app_path}")
    print("=" * 50)


if __name__ == "__main__":
    mode_arg = sys.argv[1] if len(sys.argv) > 1 and sys.argv[1] in ("onedir", "onefile") else "onedir"
    build_app(mode=mode_arg)
