"""
app_gui.py - Modern Standalone Desktop Application
Features:
- Sleek CustomTkinter UI (dark/light mode compatible)
- Drag-and-drop / file browser for PDFs and images
- Page range selection (All or specific pages)
- Toggle switches for CV Preprocessing (Deskew, Shadow Removal, Orientation)
- Toggle switches for Quality Assurance (Highlight Low Confidence, QA Audit)
- Real-time progress bar and live logging console
- One-click 'Open in Word' and 'Open Output Folder' post-conversion buttons
"""

import sys
import os
import threading
import time
import subprocess
from typing import Optional

# Ensure project root is in sys.path
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

import customtkinter as ctk
from tkinter import filedialog, messagebox

# Set modern theme
ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")


class DocumentConverterApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("DocMorph Pro — High-Fidelity Document & Table Converter")
        self.geometry("860x760")
        self.minsize(780, 680)

        self.selected_file_path: Optional[str] = None
        self.output_docx_path: Optional[str] = None
        self.output_dir: Optional[str] = None
        self.is_converting = False

        self._build_ui()

    def _build_ui(self):
        # Header Banner
        self.header_frame = ctk.CTkFrame(self, corner_radius=10)
        self.header_frame.pack(fill="x", padx=18, pady=(15, 8))

        self.title_label = ctk.CTkLabel(
            self.header_frame,
            text="DocMorph Pro",
            font=ctk.CTkFont(size=22, weight="bold")
        )
        self.title_label.pack(side="left", padx=16, pady=10)

        self.subtitle_label = ctk.CTkLabel(
            self.header_frame,
            text="Scanned PDF & Image to 100% Flow-Editable Word (.docx)",
            font=ctk.CTkFont(size=12, slant="italic"),
            text_color="gray70"
        )
        self.subtitle_label.pack(side="left", padx=6, pady=10)

        self.mode_switch = ctk.CTkOptionMenu(
            self.header_frame,
            values=["Dark", "Light"],
            command=self._change_appearance_mode,
            width=90
        )
        self.mode_switch.pack(side="right", padx=16, pady=10)
        self.mode_switch.set("Dark")

        # Main Scrollable Body
        self.main_frame = ctk.CTkScrollableFrame(self, corner_radius=10)
        self.main_frame.pack(fill="both", expand=True, padx=18, pady=6)

        # 1. File Selection Card
        self.file_card = ctk.CTkFrame(self.main_frame, corner_radius=8)
        self.file_card.pack(fill="x", padx=10, pady=8)

        self.file_card_lbl = ctk.CTkLabel(
            self.file_card, text="1. Select Document", font=ctk.CTkFont(size=14, weight="bold")
        )
        self.file_card_lbl.pack(anchor="w", padx=14, pady=(10, 4))

        self.file_entry_row = ctk.CTkFrame(self.file_card, fg_color="transparent")
        self.file_entry_row.pack(fill="x", padx=14, pady=(2, 10))

        self.file_entry = ctk.CTkEntry(
            self.file_entry_row,
            placeholder_text="Choose a PDF, PNG, JPG, or TIFF document...",
            font=ctk.CTkFont(size=12)
        )
        self.file_entry.pack(side="left", fill="x", expand=True, padx=(0, 10))

        self.browse_btn = ctk.CTkButton(
            self.file_entry_row,
            text="Browse...",
            width=110,
            command=self._browse_file
        )
        self.browse_btn.pack(side="right")

        self.file_info_lbl = ctk.CTkLabel(
            self.file_card,
            text="Supports multi-page PDFs, exam papers, financial balance sheets, and camera photos.",
            font=ctk.CTkFont(size=11),
            text_color="gray65"
        )
        self.file_info_lbl.pack(anchor="w", padx=14, pady=(0, 8))

        # 2. Conversion Options Card
        self.opts_card = ctk.CTkFrame(self.main_frame, corner_radius=8)
        self.opts_card.pack(fill="x", padx=10, pady=8)

        self.opts_card_lbl = ctk.CTkLabel(
            self.opts_card, text="2. Configuration & Page Range", font=ctk.CTkFont(size=14, weight="bold")
        )
        self.opts_card_lbl.pack(anchor="w", padx=14, pady=(10, 6))

        # Page range controls
        self.page_row = ctk.CTkFrame(self.opts_card, fg_color="transparent")
        self.page_row.pack(fill="x", padx=14, pady=4)

        self.range_var = ctk.StringVar(value="all")
        self.all_pages_radio = ctk.CTkRadioButton(
            self.page_row, text="All Pages", variable=self.range_var, value="all",
            command=self._toggle_page_entry
        )
        self.all_pages_radio.pack(side="left", padx=(0, 20))

        self.custom_pages_radio = ctk.CTkRadioButton(
            self.page_row, text="Page Range:", variable=self.range_var, value="custom",
            command=self._toggle_page_entry
        )
        self.custom_pages_radio.pack(side="left", padx=(0, 8))

        self.start_page_entry = ctk.CTkEntry(self.page_row, width=60, placeholder_text="Start")
        self.start_page_entry.insert(0, "1")
        self.start_page_entry.pack(side="left", padx=(0, 6))
        self.start_page_entry.configure(state="disabled")

        self.to_lbl = ctk.CTkLabel(self.page_row, text="to")
        self.to_lbl.pack(side="left", padx=(0, 6))

        self.end_page_entry = ctk.CTkEntry(self.page_row, width=60, placeholder_text="End")
        self.end_page_entry.pack(side="left")
        self.end_page_entry.configure(state="disabled")

        # Switches Row 1: Preprocessing Cleaners
        self.switches_row1 = ctk.CTkFrame(self.opts_card, fg_color="transparent")
        self.switches_row1.pack(fill="x", padx=14, pady=(8, 4))

        self.deskew_var = ctk.BooleanVar(value=True)
        self.deskew_switch = ctk.CTkSwitch(
            self.switches_row1, text="Auto-Deskew", variable=self.deskew_var
        )
        self.deskew_switch.pack(side="left", padx=(0, 16))

        self.shadow_var = ctk.BooleanVar(value=True)
        self.shadow_switch = ctk.CTkSwitch(
            self.switches_row1, text="Shadow Removal", variable=self.shadow_var
        )
        self.shadow_switch.pack(side="left", padx=(0, 16))

        self.orient_var = ctk.BooleanVar(value=True)
        self.orient_switch = ctk.CTkSwitch(
            self.switches_row1, text="360° Orientation Fix", variable=self.orient_var
        )
        self.orient_switch.pack(side="left")

        # Switches Row 2: Quality Assurance & Outputs
        self.switches_row2 = ctk.CTkFrame(self.opts_card, fg_color="transparent")
        self.switches_row2.pack(fill="x", padx=14, pady=(4, 12))

        self.qa_var = ctk.BooleanVar(value=True)
        self.qa_switch = ctk.CTkSwitch(
            self.switches_row2, text="Self-Healing Table Audit", variable=self.qa_var
        )
        self.qa_switch.pack(side="left", padx=(0, 16))

        self.highlight_var = ctk.BooleanVar(value=False)
        self.highlight_switch = ctk.CTkSwitch(
            self.switches_row2, text="Highlight Low Confidence (<60%)", variable=self.highlight_var
        )
        self.highlight_switch.pack(side="left", padx=(0, 16))

        self.md_var = ctk.BooleanVar(value=True)
        self.md_switch = ctk.CTkSwitch(
            self.switches_row2, text="Export Companion Markdown (.md)", variable=self.md_var
        )
        self.md_switch.pack(side="left")

        # 3. Action & Progress Card
        self.action_card = ctk.CTkFrame(self.main_frame, corner_radius=8)
        self.action_card.pack(fill="x", padx=10, pady=8)

        self.convert_btn = ctk.CTkButton(
            self.action_card,
            text="Convert to Editable Word (.docx)",
            height=44,
            font=ctk.CTkFont(size=15, weight="bold"),
            command=self._start_conversion
        )
        self.convert_btn.pack(fill="x", padx=16, pady=(14, 8))

        self.progress_bar = ctk.CTkProgressBar(self.action_card)
        self.progress_bar.pack(fill="x", padx=16, pady=(2, 6))
        self.progress_bar.set(0)

        self.status_lbl = ctk.CTkLabel(
            self.action_card, text="Ready.", font=ctk.CTkFont(size=12), text_color="gray75"
        )
        self.status_lbl.pack(padx=16, pady=(0, 6))

        # Post conversion buttons row (initially hidden)
        self.post_btn_row = ctk.CTkFrame(self.action_card, fg_color="transparent")
        self.post_btn_row.pack(fill="x", padx=16, pady=(2, 12))

        self.open_word_btn = ctk.CTkButton(
            self.post_btn_row,
            text="Open in Microsoft Word",
            fg_color="#1E6F5C",
            hover_color="#145A49",
            command=self._open_in_word
        )
        self.open_word_btn.pack(side="left", fill="x", expand=True, padx=(0, 8))

        self.open_folder_btn = ctk.CTkButton(
            self.post_btn_row,
            text="Open Output Folder",
            command=self._open_output_folder
        )
        self.open_folder_btn.pack(side="right", fill="x", expand=True, padx=(8, 0))

        # 4. Diagnostic Log Console
        self.log_card = ctk.CTkFrame(self.main_frame, corner_radius=8)
        self.log_card.pack(fill="both", expand=True, padx=10, pady=8)

        self.log_card_lbl = ctk.CTkLabel(
            self.log_card, text="Conversion & QA Log Output", font=ctk.CTkFont(size=12, weight="bold")
        )
        self.log_card_lbl.pack(anchor="w", padx=14, pady=(8, 2))

        self.log_box = ctk.CTkTextbox(
            self.log_card, height=140, font=ctk.CTkFont(family="Consolas", size=10)
        )
        self.log_box.pack(fill="both", expand=True, padx=14, pady=(2, 10))

    def _change_appearance_mode(self, mode: str):
        ctk.set_appearance_mode(mode)

    def _toggle_page_entry(self):
        if self.range_var.get() == "custom":
            self.start_page_entry.configure(state="normal")
            self.end_page_entry.configure(state="normal")
        else:
            self.start_page_entry.configure(state="disabled")
            self.end_page_entry.configure(state="disabled")

    def _browse_file(self):
        filetypes = [
            ("Supported Documents", "*.pdf;*.png;*.jpg;*.jpeg;*.tiff;*.tif;*.bmp;*.webp"),
            ("PDF Documents (*.pdf)", "*.pdf"),
            ("Images (*.png;*.jpg;*.tiff)", "*.png;*.jpg;*.jpeg;*.tiff;*.tif;*.bmp;*.webp"),
            ("All Files", "*.*")
        ]
        chosen = filedialog.askopenfilename(title="Select Document to Convert", filetypes=filetypes)
        if chosen:
            self.selected_file_path = chosen
            self.file_entry.delete(0, "end")
            self.file_entry.insert(0, chosen)
            self._update_file_info(chosen)

    def _update_file_info(self, path: str):
        size_mb = os.path.getsize(path) / (1024 * 1024)
        ext = os.path.splitext(path)[1].lower()
        if ext == ".pdf":
            try:
                import pymupdf
                doc = pymupdf.open(path)
                page_count = len(doc)
                doc.close()
                self.file_info_lbl.configure(
                    text=f"PDF Document: {page_count} page(s) | Size: {size_mb:.2f} MB"
                )
                self.end_page_entry.delete(0, "end")
                self.end_page_entry.insert(0, str(page_count))
            except Exception:
                self.file_info_lbl.configure(text=f"PDF Document | Size: {size_mb:.2f} MB")
        else:
            self.file_info_lbl.configure(
                text=f"Single Document Image ({ext.upper()}) | Size: {size_mb:.2f} MB"
            )

    def _log(self, message: str):
        self.log_box.insert("end", message + "\n")
        self.log_box.see("end")

    def _start_conversion(self):
        input_path = self.file_entry.get().strip()
        if not input_path or not os.path.exists(input_path):
            messagebox.showerror("Error", "Please select a valid document file.")
            return

        if self.is_converting:
            return

        self.is_converting = True
        self.convert_btn.configure(state="disabled", text="Converting Document...")
        self.progress_bar.set(0.1)
        self.status_lbl.configure(text="Initializing engine and local models...")
        self.log_box.delete("1.0", "end")

        thread = threading.Thread(target=self._run_conversion_worker, args=(input_path,), daemon=True)
        thread.start()

    def _run_conversion_worker(self, input_path: str):
        t0 = time.time()
        try:
            base, ext = os.path.splitext(input_path)
            output_docx = f"{base}.docx"
            output_md = f"{base}.md" if self.md_var.get() else None

            start_page = 1
            end_page = None
            if self.range_var.get() == "custom":
                try:
                    start_page = int(self.start_page_entry.get().strip() or 1)
                except ValueError:
                    start_page = 1
                try:
                    end_val = self.end_page_entry.get().strip()
                    end_page = int(end_val) if end_val else None
                except ValueError:
                    end_page = None

            self._log(f"Starting conversion for: {os.path.basename(input_path)}")
            self._log(f"Target Word Output: {os.path.basename(output_docx)}")
            self._log(f"Options: Deskew={self.deskew_var.get()}, Shadows={self.shadow_var.get()}, "
                      f"Orientation={self.orient_var.get()}, QA={self.qa_var.get()}")

            # Import convert_document
            from convert import convert_document

            self.after(0, lambda: self.status_lbl.configure(text="Processing pages & extracting tables..."))
            self.after(0, lambda: self.progress_bar.set(0.35))

            docx_res, md_res = convert_document(
                input_path=input_path,
                output_docx=output_docx,
                output_markdown=output_md,
                dpi=150,
                max_workers=4,
                start_page=start_page,
                end_page=end_page,
                deskew=self.deskew_var.get(),
                remove_shadows=self.shadow_var.get(),
                suppress_watermarks=False,
                fix_orientation=self.orient_var.get(),
                highlight_low_confidence=self.highlight_var.get(),
                qa_audit=self.qa_var.get()
            )

            elapsed = time.time() - t0
            self.output_docx_path = docx_res
            self.output_dir = os.path.dirname(os.path.abspath(docx_res))

            self.after(0, lambda: self._on_conversion_success(docx_res, elapsed))

        except Exception as e:
            self._log(f"\n[ERROR]: {str(e)}")
            self.after(0, lambda: self._on_conversion_error(str(e)))

    def _on_conversion_success(self, docx_path: str, elapsed: float):
        self.is_converting = False
        self.convert_btn.configure(state="normal", text="Convert to Editable Word (.docx)")
        self.progress_bar.set(1.0)
        self.status_lbl.configure(text=f"Conversion completed successfully in {elapsed:.1f}s!")
        self._log(f"\nSUCCESS: Created Microsoft Word document:")
        self._log(f"  -> {docx_path}")
        messagebox.showinfo("Conversion Complete", f"Document converted successfully in {elapsed:.1f}s!\n\nSaved to: {docx_path}")

    def _on_conversion_error(self, err_msg: str):
        self.is_converting = False
        self.convert_btn.configure(state="normal", text="Convert to Editable Word (.docx)")
        self.progress_bar.set(0)
        self.status_lbl.configure(text="Conversion failed. Check log for details.")
        messagebox.showerror("Conversion Failed", f"An error occurred during conversion:\n\n{err_msg}")

    def _open_in_word(self):
        if self.output_docx_path and os.path.exists(self.output_docx_path):
            try:
                os.startfile(self.output_docx_path)
            except Exception as e:
                messagebox.showerror("Error", f"Failed to open file: {e}")
        else:
            messagebox.showwarning("Notice", "No converted Word document found yet.")

    def _open_output_folder(self):
        if self.output_dir and os.path.exists(self.output_dir):
            try:
                subprocess.Popen(f'explorer "{self.output_dir}"')
            except Exception as e:
                messagebox.showerror("Error", f"Failed to open folder: {e}")
        else:
            messagebox.showwarning("Notice", "Output folder not available.")


def main():
    app = DocumentConverterApp()
    app.mainloop()


if __name__ == "__main__":
    main()

