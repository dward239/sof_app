from __future__ import annotations
from pathlib import Path
import sys, os, json, traceback, math
import pandas as pd

def _resource_path(*parts) -> Path:
    """
    Return an absolute Path to a bundled resource.
    Works in dev and in PyInstaller (sys._MEIPASS) mode.
    """
    base = getattr(sys, "_MEIPASS", None)
    if base:
        return Path(base, *parts)
    return Path(__file__).resolve().parent.joinpath(*parts)


from sof_app.version import __version__

# Prefer PySide6 (LGPL). Allow explicit opt-in to PyQt6 via env.
BINDING = os.getenv("SOF_QT_BINDING", "pyside6").lower()
USING_PYQT = False

if BINDING == "pyqt6":
    try:
        from PyQt6.QtWidgets import (
            QApplication, QWidget, QLabel, QPushButton, QLineEdit, QFileDialog,
            QGridLayout, QMessageBox, QTableWidget, QTableWidgetItem, QHeaderView,
            QCheckBox, QSpinBox, QComboBox, QDoubleSpinBox
        )
        from PyQt6.QtCore import Qt, QUrl
        from PyQt6.QtGui import QGuiApplication, QDesktopServices, QIcon
        USING_PYQT = True
    except ModuleNotFoundError:
        # fall back to PySide6 if PyQt6 not available
        from PySide6.QtWidgets import (
            QApplication, QWidget, QLabel, QPushButton, QLineEdit, QFileDialog,
            QGridLayout, QMessageBox, QTableWidget, QTableWidgetItem, QHeaderView,
            QCheckBox, QSpinBox, QComboBox, QDoubleSpinBox
        )
        from PySide6.QtCore import Qt, QUrl
        from PySide6.QtGui import QGuiApplication, QDesktopServices, QIcon
else:
    try:
        # default path: PySide6
        from PySide6.QtWidgets import (
            QApplication, QWidget, QLabel, QPushButton, QLineEdit, QFileDialog,
            QGridLayout, QMessageBox, QTableWidget, QTableWidgetItem, QHeaderView,
            QCheckBox, QSpinBox, QComboBox, QDoubleSpinBox
        )
        from PySide6.QtCore import Qt, QUrl
        from PySide6.QtGui import QGuiApplication, QDesktopServices, QIcon
    except ModuleNotFoundError:
        # as last resort, try PyQt6 (GPL)
        from PyQt6.QtWidgets import (
            QApplication, QWidget, QLabel, QPushButton, QLineEdit, QFileDialog,
            QGridLayout, QMessageBox, QTableWidget, QTableWidgetItem, QHeaderView,
            QCheckBox, QSpinBox, QComboBox, QDoubleSpinBox
        )
        from PyQt6.QtCore import Qt, QUrl
        from PyQt6.QtGui import QGuiApplication, QDesktopServices, QIcon
        USING_PYQT = True
        print(
            "WARNING: Falling back to PyQt6 (GPL-3). "
            "Set SOF_QT_BINDING=pyside6 to prefer the LGPL binding.",
            file=sys.stderr,
        )


# ---- Numeric sorting helper  ----
class NumericItem(QTableWidgetItem):
    """
    QTableWidgetItem that sorts by a numeric key (Qt.UserRole).
    NaNs are pushed to the end when sorting ascending.
    """
    def __init__(self, value: float, text: str | None = None, nan_high: bool = True):
        if text is None:
            if value is None or (isinstance(value, float) and math.isnan(value)):
                text = ""
            else:
                text = str(value)
        super().__init__(text)
        # numeric sort key
        try:
            v = float(value)
        except Exception:
            v = float("nan")
        if math.isnan(v):
            v_sort = float("inf") if nan_high else float("-inf")
        else:
            v_sort = v
        self.setData(Qt.ItemDataRole.UserRole, v_sort)
        self.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

    def __lt__(self, other: QTableWidgetItem) -> bool:
        try:
            a = float(self.data(Qt.ItemDataRole.UserRole))
            b = float(other.data(Qt.ItemDataRole.UserRole))
            return a < b
        except Exception:
            return super().__lt__(other)

from sof_app.io.excel_loader import load_samples, load_limits
from sof_app.services.sof import compute_sof
from sof_app.services.audit import write_audit

def _num_from_display(val) -> float:
    """Extract leading numeric token from '123.4 unit' for sorting."""
    if val is None or (isinstance(val, float) and math.isnan(val)):
        return float("nan")
    s = str(val).strip()
    if not s:
        return float("nan")
    head = s.split()[0].replace(",", "")
    try:
        return float(head)  # handles 1e6, 1e+06, etc.
    except Exception:
        return float("nan")

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
    
    def validate_inputs(self):
        try:
            if not self.samples_path or not self.limits_path:
                QMessageBox.information(self, "Validate inputs", "Select both Samples and Limits files first.")
                return

            # Load (re-using your loaders so Excel/CSV both work)
            samples = load_samples(self.samples_path)
            limits  = load_limits(self.limits_path)

            problems = []

            # Required columns
            req_s = {"nuclide", "value", "unit"}
            req_l = {"nuclide", "limit_value", "limit_unit"}
            miss_s = req_s - set(samples.columns)
            miss_l = req_l - set(limits.columns)
            if miss_s:
                problems.append(f"- Samples missing columns: {sorted(miss_s)}")
            if miss_l:
                problems.append(f"- Limits missing columns: {sorted(miss_l)}")

            # Empty/blank nuclide names
            if "nuclide" in samples.columns:
                n_blank = samples["nuclide"].astype(str).str.strip().eq("").sum()
                if n_blank:
                    problems.append(f"- Samples has {n_blank} blank nuclide name(s).")

            # Duplicate canonical nuclides in limits (simple check on raw names)
            if "nuclide" in limits.columns:
                dup = limits["nuclide"].astype(str).str.strip().value_counts()
                dup = dup[dup > 1]
                if not dup.empty:
                    problems.append(f"- Limits has duplicate nuclides (raw names): {', '.join(dup.index[:10])}"
                                    + (" …" if len(dup) > 10 else ""))

            # Counts units sanity check (cpm/cps/count)
            if "unit" in samples.columns:
                ustr = samples["unit"].astype(str).str.lower()
                mask = ustr.str.contains(r"\bcpm\b|\bcps\b|count", regex=True)
                if mask.any():
                    ex = samples.loc[mask, "unit"].astype(str).unique()
                    problems.append(f"- Counts units detected in samples: {', '.join(ex[:6])}"
                                    + (" …" if len(ex) > 6 else "")
                                    + " (convert to activity first, e.g., dpm or Bq).")

            # Surface /100 cm^2 hint
            if "unit" in samples.columns:
                if samples["unit"].astype(str).str.contains(r"/\s*100\s*cm\^?2|\*\*2", regex=True).any():
                    problems.append("- Note: surface units like dpm/100 cm^2 will be auto-normalized to Bq/m^2.")

            if problems:
                QMessageBox.warning(self, "Validate inputs", "Issues found:\n\n" + "\n".join(problems))
            else:
                QMessageBox.information(self, "Validate inputs", "Looks good ✅")
        except Exception as e:
            traceback.print_exc()
            QMessageBox.critical(self, "Validate inputs", f"{type(e).__name__}: {e}")


    def __init__(self):
        super().__init__()
        self.setWindowTitle(f"SOF Calculator (Desktop) — v{__version__}")
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

        # Amber Warning Threshold
        grid.addWidget(QLabel("Warn threshold (amber if SOF ≥):"), row, 0)
        self.spin_warn = QDoubleSpinBox(self)
        self.spin_warn.setRange(0.0, 1.0)
        self.spin_warn.setDecimals(2)
        self.spin_warn.setSingleStep(0.01)
        self.spin_warn.setValue(0.90)  # default
        self.spin_warn.valueChanged.connect(self._maybe_autorecompute)
        
        #Optional banner recolor w/o calc.
        self.spin_warn.valueChanged.connect(lambda _=None: (self.populate_ui() if self.summary is not None else None))
        grid.addWidget(self.spin_warn, row, 1); row += 1

        # Buttons

        self.btn_compute = QPushButton("Compute SOF", self); self.btn_compute.clicked.connect(self.compute)
        grid.addWidget(self.btn_compute, row, 0)

        self.btn_validate = QPushButton("Validate Inputs", self); self.btn_validate.clicked.connect(self.validate_inputs)
        grid.addWidget(self.btn_validate, row, 1)

        self.btn_save_csv = QPushButton("Save CSV…", self); self.btn_save_csv.clicked.connect(self.save_csv); self.btn_save_csv.setEnabled(False)
        grid.addWidget(self.btn_save_csv, row, 2)
        row += 1

        self.btn_save_audit = QPushButton("Save Audit JSON…", self); self.btn_save_audit.clicked.connect(self.save_audit); self.btn_save_audit.setEnabled(False)
        grid.addWidget(self.btn_save_audit, row, 0)

        self.btn_copy_table = QPushButton("Copy table to clipboard", self); self.btn_copy_table.clicked.connect(self.copy_table); self.btn_copy_table.setEnabled(False)
        grid.addWidget(self.btn_copy_table, row, 1)

        self.btn_open_results = QPushButton("Open results folder", self); self.btn_open_results.clicked.connect(self.open_results)
        grid.addWidget(self.btn_open_results, row, 2)
        row += 1


        # --- CSV format tip + link ---
        self.csv_tip = QLabel(
            "CSV/Excel headers"
            "Samples: nuclide, value, unit[, sigma];  "
            "Limits: nuclide, limit_value, limit_unit[, category].  "
            "Units like MBq or dpm/100 cm^2; counts (cpm/cps) are not allowed."
        )
        self.csv_tip.setWordWrap(True)
        self.csv_tip.setStyleSheet("color: gray; font-size: 11px;")
        grid.addWidget(self.csv_tip, row, 0, 1, 2)

        self.btn_csv_tips = QPushButton("View examples…", self)
        self.btn_csv_tips.setFlat(True)
        self.btn_csv_tips.setStyleSheet("color:#1a73e8; text-decoration: underline; border: none;")
        self.btn_csv_tips.clicked.connect(self.show_csv_tips)
        grid.addWidget(self.btn_csv_tips, row, 2)
        row += 1

        # Summary (big banner)
        self.lbl_summary = QLabel("SOF: —   Pass: —   Margin: —", self)
        self.lbl_summary.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # Bigger, bold font
        f = self.lbl_summary.font()
        f.setPointSize(18)        # <-- change size here
        f.setBold(True)
        self.lbl_summary.setFont(f)

        # Base styling (bg color is set later in populate_ui)
        self.lbl_summary.setStyleSheet("padding: 10px; border-radius: 8px;")
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
                # Warn threshold
                wt = s.get("warn_threshold", None)
                try:
                    wtv = float(wt) if wt is not None else None
                except Exception:
                    wtv = None
                if wtv is None or not (0.0 < wtv <= 1.0):
                    self.spin_warn.setValue(0.90)
                else:
                    self.spin_warn.setValue(wtv)

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
            "warn_threshold": float(self.spin_warn.value()),

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
            

    def show_csv_tips(self):
            # Works with PyQt6 or PySide6
            try:
                from PyQt6.QtWidgets import (
                    QDialog, QVBoxLayout, QHBoxLayout, QTextBrowser, QPlainTextEdit, QPushButton, QLabel
                )
                from PyQt6.QtGui import QFontDatabase
            except ModuleNotFoundError:
                from PySide6.QtWidgets import (
                    QDialog, QVBoxLayout, QHBoxLayout, QTextBrowser, QPlainTextEdit, QPushButton, QLabel
                )
                from PySide6.QtGui import QFontDatabase

            # Header + bullets as HTML (theme friendly)
            html = """
            <h3 style="margin-top:0">CSV / Excel format tips</h3>
            <p><b>Samples</b> (required): <code>nuclide, value, unit</code> &nbsp;&nbsp;
            <i>optional</i>: <code>sigma</code> (1-σ, same unit as <code>value</code>)</p>
            <p><b>Limits</b> (required): <code>nuclide, limit_value, limit_unit</code> &nbsp;&nbsp;
            <i>optional</i>: <code>category, rule_name, note</code></p>
            <ul style="margin-top:8px">
            <li>Units: activity (<code>Bq</code>, <code>MBq</code>, <code>Ci</code>, <code>dpm</code>), dose/rate (<code>mSv/h</code>, <code>mrem/h</code>), time (<code>h</code>, <code>yr</code>).</li>
            <li>Surface contamination like <code>dpm/100 cm^2</code> is auto-normalized to <code>Bq/m^2</code>.</li>
            <li><b>Counts are blocked</b> (<code>cpm</code>/<code>cps</code>/<code>counts</code>): convert to activity first.</li>
            </ul>
            """

            ex_samples = (
                "nuclide,value,unit,sigma\n"
                "Cs-137,1.0,MBq,0.05\n"
                "Co-60,600,\"dpm/100 cm^2\",\n"
            )
            ex_limits = (
                "nuclide,limit_value,limit_unit,category,rule_name\n"
                "Cs-137,4.0,MBq,General,My Limits v1\n"
                "Co-60,2000,Bq/m^2,General,My Limits v1\n"
            )

            dlg = QDialog(self)
            dlg.setWindowTitle("CSV format tips")
            layout = QVBoxLayout(dlg)

            header = QTextBrowser(dlg)
            header.setReadOnly(True)
            header.setHtml(html)
            layout.addWidget(header)

            fixed = QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont)

            def add_example(title: str, text: str, copy_label: str):
                layout.addWidget(QLabel(f"<b>{title}</b>"))
                edit = QPlainTextEdit(dlg)
                edit.setReadOnly(True)
                edit.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
                edit.setFont(fixed)
                edit.setPlainText(text)
                # Dark-theme friendly; switch to light if you prefer
                edit.setStyleSheet("QPlainTextEdit { background: #161b22; color: #e6edf3; border: 1px solid #444; }")
                edit.setMinimumHeight(120)
                layout.addWidget(edit)

                row = QHBoxLayout()
                row.addStretch(1)
                btn = QPushButton(copy_label, dlg)
                btn.clicked.connect(lambda: QGuiApplication.clipboard().setText(edit.toPlainText()))
                row.addWidget(btn)
                layout.addLayout(row)

            add_example("Example — Samples", ex_samples, "Copy Samples")
            add_example("Example — Limits",  ex_limits,  "Copy Limits")

            btn_close = QPushButton("Close", dlg)
            btn_close.clicked.connect(dlg.accept)
            layout.addWidget(btn_close)

            dlg.resize(820, 560)
            dlg.exec()


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

    def _banner_colors(self, passed: bool, sof_total: float, warn_threshold: float) -> tuple[str, str]:
        """
        3-state banner:
        - Red if SOF > 1.0
        - Amber if passed and SOF >= warn_threshold
        - Green otherwise
        """
        if not passed:
            return "#b71c1c", "white"      # red
        if sof_total >= warn_threshold:
            return "#f57c00", "black"      # amber
        return "#1b5e20", "white"          # green
    

    def populate_ui(self):
        
        s = self.summary or {}
        self.lbl_summary.setText(
            f"SOF: {s.get('sof_total', float('nan')):.4g}   "
            f"Pass: {s.get('pass_limit', False)}   "
            f"Margin: {s.get('margin_to_1', float('nan')):.4g}"
        )

        passed = bool(s.get("pass_limit", False))
        sof_total = float(s.get("sof_total", float("nan")))
        warn_threshold = float(self.spin_warn.value()) if hasattr(self, "spin_warn") else 0.90

        bg, fg = self._banner_colors(passed, sof_total, warn_threshold)
        self.lbl_summary.setStyleSheet(
            f"padding: 10px; border-radius: 8px; background-color: {bg}; color: {fg};"
        )

        df = self.per_nuclide_df if self.per_nuclide_df is not None else pd.DataFrame()
        cols = ["nuclide","conc_display","limit_display","fraction","fraction_sigma","allowed_additional_in_limit_units"]

        # Remember current sort state (so user click persists)
        header = self.table.horizontalHeader()
        prev_col = header.sortIndicatorSection()
        prev_ord = header.sortIndicatorOrder()

        self.table.setSortingEnabled(False)
        self.table.setRowCount(len(df))

        for r in range(len(df)):
            for c, col in enumerate(cols):
                val = df.iloc[r][col]

                if col in ("fraction", "fraction_sigma", "allowed_additional_in_limit_units"):
                    # numeric with pretty text
                    if col == "fraction" and "fraction_display" in df.columns:
                        txt = str(df.iloc[r]["fraction_display"])
                        try:
                            vfloat = float(df.iloc[r]["fraction"])
                        except Exception:
                            vfloat = float("nan")
                    else:
                        try:
                            vfloat = float(val)
                            txt = "" if (isinstance(vfloat, float) and math.isnan(vfloat)) else f"{vfloat:.4g}"
                        except Exception:
                            vfloat, txt = float("nan"), ""
                    self.table.setItem(r, c, NumericItem(vfloat, txt))

                elif col in ("conc_display", "limit_display"):
                    # parse number for sorting; prefer raw numeric columns if present
                    txt = "" if pd.isna(val) else str(val)
                    if col == "conc_display" and "value_conv" in df.columns:
                        vfloat = float(df.iloc[r]["value_conv"])
                    elif col == "limit_display" and "limit_value_base" in df.columns:
                        vfloat = float(df.iloc[r]["limit_value_base"])
                    else:
                        vfloat = _num_from_display(txt)
                    self.table.setItem(r, c, NumericItem(vfloat, txt))

                else:
                    # plain text (nuclide)
                    item = QTableWidgetItem("" if pd.isna(val) else str(val))
                    self.table.setItem(r, c, item)

        self.table.setSortingEnabled(True)

        # restore previous sort (if any)
        if prev_col >= 0:
            self.table.sortItems(prev_col, prev_ord)

        self.btn_save_csv.setEnabled(not df.empty)
        self.btn_save_audit.setEnabled(self.summary is not None)
        self.btn_copy_table.setEnabled(not df.empty)


    # ----- utilities -----
    def save_csv(self):
        if self.per_nuclide_df is None:
            return
        path, _ = QFileDialog.getSaveFileName(self, "Save CSV", "per_nuclide.csv", "CSV (*.csv)")
        if path:
            self.per_nuclide_df.to_csv(path, index=False)
            QMessageBox.information(self, "Saved", f"Saved {path}")

    def save_audit(self):
        if self.summary is None:
            return
        path, _ = QFileDialog.getSaveFileName(self, "Save Audit JSON", "audit.json", "JSON (*.json)")
        if path:
            cat = None if self.cat_combo.currentIndex() <= 0 else self.cat_combo.currentText().strip()
            write_audit(
                path,
                inputs={
                    "samples_path": os.path.abspath(self.samples_path),
                    "limits_path": os.path.abspath(self.limits_path),
                    "alias_path": os.getenv("SOF_ALIAS_PATH"),
                    "category": cat,
                    "options": {
                        "combine_duplicates": self.chk_combine.isChecked(),
                        "treat_missing_as_zero": self.chk_missing_zero.isChecked(),
                        "display_sigfigs": int(self.spin_sig.value()),
                        "warn_threshold": float(self.spin_warn.value()),
                    },
                },
                results={"summary": self.summary},
            )
            QMessageBox.information(self, "Saved", f"Saved {path}")

    def copy_table(self):
        if self.per_nuclide_df is None:
            return
        csv = self.per_nuclide_df.to_csv(index=False)
        QGuiApplication.clipboard().setText(csv)
        QMessageBox.information(self, "Copied", "Per-nuclide table copied to clipboard (CSV).")

    def open_results(self):
        os.makedirs("results", exist_ok=True)
        QDesktopServices.openUrl(QUrl.fromLocalFile(os.path.abspath("results")))


def main():
    app = QApplication(sys.argv)

    # --- Windows: set AppUserModelID BEFORE creating/showing windows ---
    if sys.platform.startswith("win"):
        try:
            import ctypes
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("dward239.SOF.App")
        except Exception:
            pass

    # --- App/window icon ---
    icon_path = _resource_path("assets", "icons", "sof_trefoil.ico")
    if icon_path.is_file():
        app.setWindowIcon(QIcon(str(icon_path)))

    w = SofQt()

    # Also set directly on the window (helps on some setups)
    if icon_path.is_file():
        w.setWindowIcon(QIcon(str(icon_path)))

    w.resize(900, 600)
    w.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
