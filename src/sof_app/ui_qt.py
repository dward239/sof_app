from __future__ import annotations
import sys, os, json, traceback
import pandas as pd

# Try PyQt6, fall back to PySide6 if needed
try:
    from PyQt6.QtWidgets import (
        QApplication, QWidget, QLabel, QPushButton, QLineEdit, QFileDialog,
        QGridLayout, QMessageBox, QTableWidget, QTableWidgetItem, QHeaderView,
        QCheckBox, QSpinBox, QComboBox
    )
    from PyQt6.QtCore import Qt, QUrl
    from PyQt6.QtGui import QGuiApplication, QDesktopServices
except ModuleNotFoundError:
    from PySide6.QtWidgets import (
        QApplication, QWidget, QLabel, QPushButton, QLineEdit, QFileDialog,
        QGridLayout, QMessageBox, QTableWidget, QTableWidgetItem, QHeaderView,
        QCheckBox, QSpinBox, QComboBox
    )
    from PySide6.QtCore import Qt, QUrl
    from PySide6.QtGui import QGuiApplication, QDesktopServices

from sof_app.io.excel_loader import load_samples, load_limits
from sof_app.services.sof import compute_sof
from sof_app.services.audit import write_audit

SETTINGS_PATH = os.path.join(os.path.expanduser("~"), ".sof_app_settings.json")

class DropLineEdit(QLineEdit):
    """QLineEdit that accepts file drag-and-drop."""
    def __init__(self, parent=None, on_drop=None):
        super().__init__(parent)
        self.setReadOnly(True)
        self.setAcceptDrops(True)
        self._on_drop = on_drop

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            event.ignore()

    def dropEvent(self, event):
        urls = event.mimeData().urls()
        if not urls:
            return
        local = urls[0].toLocalFile()
        if local and os.path.isfile(local):
            self.setText(local)
            if callable(self._on_drop):
                self._on_drop(local)

class SofQt(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("SOF Calculator (Desktop) — v0.1.1")
        self.samples_path = ""
        self.limits_path  = ""
        self.per_nuclide_df = None
        self.summary = None

        grid = QGridLayout(self)

        # Files
        grid.addWidget(QLabel("Samples (Excel/CSV):"), 0, 0)
        self.samples_edit = DropLineEdit(self, on_drop=self._after_samples_drop)
        grid.addWidget(self.samples_edit, 0, 1)
        btn_s = QPushButton("Browse…", self); btn_s.clicked.connect(self.pick_samples)
        grid.addWidget(btn_s, 0, 2)

        grid.addWidget(QLabel("Limits (Excel/CSV):"), 1, 0)
        self.limits_edit = DropLineEdit(self, on_drop=self._after_limits_drop)
        grid.addWidget(self.limits_edit, 1, 1)
        btn_l = QPushButton("Browse…", self); btn_l.clicked.connect(self.pick_limits)
        grid.addWidget(btn_l, 1, 2)

        # Category dropdown (auto-populated from limits)
        grid.addWidget(QLabel("Category:"), 2, 0)
        self.cat_combo = QComboBox(self); self.cat_combo.setEditable(False)
        self.cat_combo.addItem("(none)")
        self.cat_combo.currentIndexChanged.connect(self._maybe_autorecompute)
        grid.addWidget(self.cat_combo, 2, 1, 1, 2)

        # Options
        row = 3
        grid.addWidget(QLabel("Options:"), row, 0)
        self.chk_combine = QCheckBox("Combine duplicate nuclides"); self.chk_combine.setChecked(True)
        self.chk_combine.stateChanged.connect(self._maybe_autorecompute)
        grid.addWidget(self.chk_combine, row, 1, 1, 2); row += 1

        self.chk_missing_zero = QCheckBox("Treat missing limits as zero (skip)"); self.chk_missing_zero.setChecked(True)
        self.chk_missing_zero.stateChanged.connect(self._maybe_autorecompute)
        grid.addWidget(self.chk_missing_zero, row, 1, 1, 2); row += 1

        grid.addWidget(QLabel("Display sig figs:"), row, 0)
        self.spin_sig = QSpinBox(self); self.spin_sig.setRange(1, 8); self.spin_sig.setValue(4)
        self.spin_sig.valueChanged.connect(self._maybe_autorecompute)
        grid.addWidget(self.spin_sig, row, 1); row += 1

        # Buttons
        self.btn_compute = QPushButton("Compute SOF", self); self.btn_compute.clicked.connect(self.compute)
        grid.addWidget(self.btn_compute, row, 0)

        self.btn_save_csv = QPushButton("Save CSV…", self); self.btn_save_csv.clicked.connect(self.save_csv); self.btn_save_csv.setEnabled(False)
        grid.addWidget(self.btn_save_csv, row, 1)

        self.btn_save_audit = QPushButton("Save Audit JSON…", self); self.btn_save_audit.clicked.connect(self.save_audit); self.btn_save_audit.setEnabled(False)
        grid.addWidget(self.btn_save_audit, row, 2); row += 1

        # Utilities
        self.btn_copy_table = QPushButton("Copy table to clipboard", self); self.btn_copy_table.clicked.connect(self.copy_table); self.btn_copy_table.setEnabled(False)
        grid.addWidget(self.btn_copy_table, row, 1)
        self.btn_open_results = QPushButton("Open results folder", self); self.btn_open_results.clicked.connect(self.open_results)
        grid.addWidget(self.btn_open_results, row, 2); row += 1

        # Summary
        self.lbl_summary = QLabel("SOF: —   Pass: —   Margin: —", self)
        grid.addWidget(self.lbl_summary, row, 0, 1, 3); row += 1

        # Table
        self.table = QTableWidget(self)
        self.table.setColumnCount(6)
        self.table.setHorizontalHeaderLabels([
            "Nuclide","Conc","Limit","Fraction","σ(fraction)","Allowed addl (limit units)"
        ])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.setSortingEnabled(True)
        grid.addWidget(self.table, row, 0, 1, 3)

        # Load sticky settings (last paths/options)
        self.load_settings()

    # ----- settings -----
    def load_settings(self):
        try:
            if os.path.exists(SETTINGS_PATH):
                with open(SETTINGS_PATH, "r", encoding="utf-8") as f:
                    s = json.load(f)
                self.samples_path = s.get("samples_path",""); self.samples_edit.setText(self.samples_path or "")
                self.limits_path  = s.get("limits_path","");  self.limits_edit.setText(self.limits_path or "")
                self.chk_combine.setChecked(bool(s.get("combine_duplicates", True)))
                self.chk_missing_zero.setChecked(bool(s.get("treat_missing_as_zero", True)))
                self.spin_sig.setValue(int(s.get("display_sigfigs", 4)))
                # If limits exists, populate categories and restore selection
                if self.limits_path and os.path.isfile(self.limits_path):
                    self._populate_categories_from_limits(self.limits_path, select=s.get("category"))
        except Exception:
            # non-fatal; continue with defaults
            pass

    def save_settings(self, category: str | None = None):
        data = {
            "samples_path": self.samples_path,
            "limits_path": self.limits_path,
            "combine_duplicates": self.chk_combine.isChecked(),
            "treat_missing_as_zero": self.chk_missing_zero.isChecked(),
            "display_sigfigs": int(self.spin_sig.value()),
            "category": category if category is not None else (None if self.cat_combo.currentIndex()<=0 else self.cat_combo.currentText().strip()),
        }
        try:
            with open(SETTINGS_PATH, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
        except Exception:
            pass

    # ----- file pickers / drops -----
    def pick_samples(self):
        path, _ = QFileDialog.getOpenFileName(self, "Select Samples", "", "Data Files (*.csv *.xlsx *.xls);;All Files (*)")
        if path:
            self.samples_path = path
            self.samples_edit.setText(path)
            self.save_settings()

    def _after_samples_drop(self, path: str):
        self.samples_path = path
        self.save_settings()

    def pick_limits(self):
        path, _ = QFileDialog.getOpenFileName(self, "Select Limits", "", "Data Files (*.csv *.xlsx *.xls);;All Files (*)")
        if path:
            self.limits_path = path
            self.limits_edit.setText(path)
            self._populate_categories_from_limits(path)
            self.save_settings()

    def _after_limits_drop(self, path: str):
        self.limits_path = path
        self._populate_categories_from_limits(path)
        self.save_settings()

    def _populate_categories_from_limits(self, path: str, select: str | None = None):
        try:
            lim = load_limits(path)
            self.cat_combo.clear()
            self.cat_combo.addItem("(none)")
            cats = []
            if "category" in lim.columns:
                cats = sorted([c for c in lim["category"].dropna().unique().tolist() if str(c).strip() != ""])
                for c in cats: self.cat_combo.addItem(str(c))
            # try to select
            if select and select in cats:
                idx = self.cat_combo.findText(select)
                if idx >= 0:
                    self.cat_combo.setCurrentIndex(idx+1)  # +1 for (none)
        except Exception as e:
            QMessageBox.warning(self, "Limits read", f"Could not read categories: {e}")

    # ----- compute & UI update -----
    def _maybe_autorecompute(self, *args):
        if self.samples_path and self.limits_path and self.per_nuclide_df is not None:
            self.compute(auto=True)

    def compute(self, auto: bool=False):
        try:
            if not self.samples_path or not self.limits_path:
                if not auto:
                    QMessageBox.warning(self, "Missing input", "Please select both Samples and Limits files.")
                return
            samples = load_samples(self.samples_path)
            limits  = load_limits(self.limits_path)
            cat = None if self.cat_combo.currentIndex() <= 0 else self.cat_combo.currentText().strip()
            per, summ = compute_sof(
                samples, limits, cat,
                combine_duplicates=self.chk_combine.isChecked(),
                treat_missing_as_zero=self.chk_missing_zero.isChecked(),
                display_sigfigs=int(self.spin_sig.value()),
            )
            self.per_nuclide_df = per
            self.summary = summ
            self.populate_ui()
            self.save_settings(category=cat)
        except Exception as e:
            traceback.print_exc()
            QMessageBox.critical(self, "Error", f"{type(e).__name__}: {e}")

    def populate_ui(self):
        s = self.summary or {}
        self.lbl_summary.setText(
            f"SOF: {s.get('sof_total', float('nan')):.4g}   "
            f"Pass: {s.get('pass_limit', False)}   "
            f"Margin: {s.get('margin_to_1', float('nan')):.4g}"
        )
        df = self.per_nuclide_df if self.per_nuclide_df is not None else pd.DataFrame()
        self.table.setRowCount(len(df))
        cols = ["nuclide","conc_display","limit_display","fraction","fraction_sigma","allowed_additional_in_limit_units"]
        for r in range(len(df)):
            for c, col in enumerate(cols):
                val = df.iloc[r][col]
                text = f"{val:.4g}" if isinstance(val, float) else str(val)
                self.table.setItem(r, c, QTableWidgetItem(text))
        self.btn_save_csv.setEnabled(not df.empty)
        self.btn_save_audit.setEnabled(self.summary is not None)
        self.btn_copy_table.setEnabled(not df.empty)

    # ----- utilities -----
    def save_csv(self):
        if self.per_nuclide_df is None: return
        path, _ = QFileDialog.getSaveFileName(self, "Save CSV", "per_nuclide.csv", "CSV (*.csv)")
        if path:
            self.per_nuclide_df.to_csv(path, index=False)
            QMessageBox.information(self, "Saved", f"Saved {path}")

    def save_audit(self):
        if self.summary is None: return
        path, _ = QFileDialog.getSaveFileName(self, "Save Audit JSON", "audit.json", "JSON (*.json)")
        if path:
            cat = None if self.cat_combo.currentIndex() <= 0 else self.cat_combo.currentText().strip()
            write_audit(path, inputs={
                "samples_path": os.path.abspath(self.samples_path),
                "limits_path": os.path.abspath(self.limits_path),
                "category": cat,
                "options": {
                    "combine_duplicates": self.chk_combine.isChecked(),
                    "treat_missing_as_zero": self.chk_missing_zero.isChecked(),
                    "display_sigfigs": int(self.spin_sig.value())
                }
            }, results={"summary": self.summary})
            QMessageBox.information(self, "Saved", f"Saved {path}")

    def copy_table(self):
        if self.per_nuclide_df is None: return
        csv = self.per_nuclide_df.to_csv(index=False)
        QGuiApplication.clipboard().setText(csv)
        QMessageBox.information(self, "Copied", "Per-nuclide table copied to clipboard (CSV).")

    def open_results(self):
        os.makedirs("results", exist_ok=True)
        QDesktopServices.openUrl(QUrl.fromLocalFile(os.path.abspath("results")))

def main():
    app = QApplication(sys.argv)
    w = SofQt()
    w.resize(900, 600)
    w.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
