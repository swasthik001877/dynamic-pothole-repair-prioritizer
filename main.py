"""
PotholeFix Desktop – main.py
PyQt6 + SQLite3 | Citizen / Admin / Repair Crew roles
"""
import sys, os, json, shutil
from datetime import date, datetime
from pathlib import Path

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QFrame, QScrollArea, QTableWidget, QTableWidgetItem,
    QLineEdit, QComboBox, QSpinBox, QTextEdit, QDialog, QFormLayout,
    QMessageBox, QHeaderView, QStackedWidget, QDateEdit,
    QFileDialog, QGridLayout, QSizePolicy,
    QAbstractItemView, QStatusBar, QDoubleSpinBox, QGroupBox, QListWidget,
    QListWidgetItem
)
from PyQt6.QtCore import Qt, QDate, QSize, QThread, pyqtSignal, QTimer, QObject
from PyQt6.QtGui import QColor, QPalette, QPixmap

import matplotlib
matplotlib.use("QtAgg")
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure

sys.path.insert(0, str(Path(__file__).parent))
import database as db
from priority_engine import default_engine

# ── Palette ────────────────────────────────────────────────────────────────────
C = {
    "bg":"#0f1117","card":"#1a1d27","sidebar":"#12151f","input":"#1e2130",
    "row_alt":"#22263a","hover":"#2a2f45",
    "blue":"#3b82f6","cyan":"#06b6d4","green":"#10b981",
    "amber":"#f59e0b","red":"#ef4444","purple":"#8b5cf6",
    "text":"#f1f5f9","muted":"#94a3b8","dim":"#64748b","border":"#2d3250",
}
STATUS_COLORS = {
    "Pending":"#64748b","Scheduled":"#06b6d4",
    "In Progress":"#3b82f6","Fixed":"#10b981","Unresolved":"#ef4444",
}
SEV_COLORS = ["#10b981","#22c55e","#84cc16","#eab308",
              "#f59e0b","#f97316","#ef4444","#dc2626","#b91c1c","#7f1d1d"]

GLOBAL_SS = f"""
QWidget{{background:{C['bg']};color:{C['text']};font-family:'Segoe UI',Arial,sans-serif;font-size:13px;}}
QFrame{{background:{C['bg']};}}
QScrollArea,QScrollArea>QWidget>QWidget{{background:{C['bg']};}}
QScrollBar:vertical{{background:{C['sidebar']};width:8px;border-radius:4px;}}
QScrollBar::handle:vertical{{background:{C['border']};border-radius:4px;min-height:20px;}}
QScrollBar::add-line:vertical,QScrollBar::sub-line:vertical{{height:0px;}}
QScrollBar:horizontal{{background:{C['sidebar']};height:8px;}}
QScrollBar::handle:horizontal{{background:{C['border']};border-radius:4px;}}
QScrollBar::add-line:horizontal,QScrollBar::sub-line:horizontal{{width:0px;}}
QLineEdit,QTextEdit,QComboBox,QSpinBox,QDoubleSpinBox,QDateEdit{{
    background:{C['input']};color:{C['text']};border:1px solid {C['border']};
    border-radius:8px;padding:8px 12px;font-size:13px;min-height:20px;}}
QLineEdit:focus,QTextEdit:focus,QComboBox:focus,QSpinBox:focus,QDateEdit:focus{{border:1px solid {C['blue']};}}
QComboBox::drop-down{{border:none;width:24px;}}
QComboBox QAbstractItemView{{background:{C['card']};color:{C['text']};border:1px solid {C['border']};
    selection-background-color:{C['blue']};}}
QTableWidget{{background:{C['card']};gridline-color:{C['border']};border:none;border-radius:8px;
    alternate-background-color:{C['row_alt']};}}
QTableWidget::item{{padding:10px 14px;border:none;}}
QTableWidget::item:selected{{background:{C['hover']};color:{C['text']};}}
QHeaderView::section{{background:{C['sidebar']};color:{C['muted']};font-weight:bold;font-size:11px;
    padding:12px 14px;border:none;border-bottom:1px solid {C['border']};}}
QGroupBox{{border:1px solid {C['border']};border-radius:8px;margin-top:12px;padding-top:8px;}}
QGroupBox::title{{color:{C['muted']};subcontrol-origin:margin;left:12px;padding:0 6px;}}
QListWidget{{background:{C['card']};border:1px solid {C['border']};border-radius:8px;}}
QListWidget::item{{padding:8px 12px;border-bottom:1px solid {C['border']};}}
QListWidget::item:selected{{background:{C['hover']};}}
QMessageBox{{background:{C['card']};}}
QDialog{{background:{C['card']};}}
QTabWidget::pane{{border:1px solid {C['border']};border-radius:8px;background:{C['card']};}}
QTabBar::tab{{background:{C['input']};color:{C['muted']};padding:8px 18px;border-radius:6px 6px 0 0;margin-right:2px;}}
QTabBar::tab:selected{{background:{C['card']};color:{C['text']};border-bottom:2px solid {C['blue']};}}
"""

# ── Helpers ────────────────────────────────────────────────────────────────────

def card(parent=None, radius=10, color=None):
    f = QFrame(parent)
    bg = color or C["card"]
    f.setStyleSheet(f"QFrame{{background:{bg};border-radius:{radius}px;}}")
    return f

def btn(text, color=None, small=False):
    b = QPushButton(text)
    bg = color or C["blue"]
    pad = "6px 14px" if small else "9px 20px"
    fs  = "12px" if small else "13px"
    b.setStyleSheet(f"""
        QPushButton{{background:{bg};color:{C['text']};border:none;
            border-radius:7px;padding:{pad};font-weight:600;font-size:{fs};}}
        QPushButton:hover{{background:{bg}dd;}}
        QPushButton:pressed{{background:{bg}99;}}
    """)
    b.setCursor(Qt.CursorShape.PointingHandCursor)
    return b

def lbl(text, size=13, bold=False, color=None, parent=None):
    w = QLabel(text, parent)
    col = color or C["text"]
    wt  = "bold" if bold else "normal"
    w.setStyleSheet(f"color:{col};font-size:{size}px;font-weight:{wt};background:transparent;")
    return w

def badge(text, color=C["blue"]):
    w = QLabel(f"  {text}  ")
    w.setStyleSheet(f"background:{color}22;color:{color};border:1px solid {color}55;"
                    f"border-radius:5px;padding:2px 4px;font-size:11px;font-weight:600;")
    w.setFixedHeight(24)
    return w

def sep():
    f = QFrame(); f.setFrameShape(QFrame.Shape.HLine)
    f.setStyleSheet(f"color:{C['border']};background:{C['border']};max-height:1px;")
    return f

def stat_card(title, value, icon, color, parent=None):
    f = card(parent, 12)
    f.setFixedHeight(120)
    lay = QHBoxLayout(f); lay.setContentsMargins(20,16,20,16)
    ico = QLabel(icon)
    ico.setStyleSheet(f"font-size:34px;background:{color}22;color:{color};"
                      f"border-radius:10px;padding:8px;")
    ico.setFixedSize(60,60); ico.setAlignment(Qt.AlignmentFlag.AlignCenter)
    lay.addWidget(ico); lay.addSpacing(14)
    txt = QVBoxLayout(); txt.setSpacing(3)
    v = QLabel(str(value))
    v.setStyleSheet(f"font-size:30px;font-weight:bold;color:{color};background:transparent;")
    t = QLabel(title)
    t.setStyleSheet(f"color:{C['muted']};font-size:11px;background:transparent;")
    txt.addWidget(v); txt.addWidget(t)
    lay.addLayout(txt); lay.addStretch()
    return f, v


# ── ML Severity analyser (runs in thread) ──────────────────────────────────────

class MLAnalyser(QThread):
    """
    Simulates ML image analysis. In production replace _analyse() body
    with a real model call (e.g. TensorFlow/ONNX inference).
    """
    result = pyqtSignal(int, str)   # severity 1-10, explanation

    def __init__(self, image_paths):
        super().__init__()
        self.image_paths = image_paths

    def run(self):
        severity, note = self._analyse(self.image_paths)
        self.result.emit(severity, note)

    def _analyse(self, paths):
        """
        Heuristic simulation based on image file size as a proxy for
        damage complexity. Replace with real CNN inference here.
        """
        if not paths:
            return 5, "No image – default severity assigned."
        try:
            from PIL import Image as PILImage
            scores = []
            for p in paths:
                img = PILImage.open(p).convert("RGB")
                w, h = img.size
                px   = list(img.getdata())
                # Variance of brightness → proxy for surface irregularity
                bright = [0.299*r + 0.587*g + 0.114*b for r,g,b in px[:5000]]
                mean_b = sum(bright)/len(bright)
                var_b  = sum((x-mean_b)**2 for x in bright)/len(bright)
                # Dark patches → damage indicator
                dark_ratio = sum(1 for x in bright if x < 80)/len(bright)
                scores.append((var_b, dark_ratio))

            avg_var   = sum(s[0] for s in scores)/len(scores)
            avg_dark  = sum(s[1] for s in scores)/len(scores)

            # Map to 1-10
            sev = int(min(10, max(1,
                1 + (avg_var / 600) * 5 + avg_dark * 5
            )))
            notes = {
                (1,3):  "Surface looks mostly intact – minor cracking.",
                (3,5):  "Moderate surface damage detected.",
                (5,7):  "Significant pothole – irregular dark patches found.",
                (7,9):  "Severe damage – high surface variance and dark areas.",
                (9,11): "Critical damage – immediate repair required.",
            }
            note = next((v for (lo,hi),v in notes.items() if lo<=sev<hi),
                        "Damage detected.")
            return sev, note
        except Exception as e:
            # Fallback: size-based heuristic
            sizes = [os.path.getsize(p) for p in paths if os.path.exists(p)]
            avg_kb = (sum(sizes)/len(sizes)/1024) if sizes else 50
            sev = min(10, max(1, int(avg_kb / 40)))
            return sev, f"Quick analysis: severity {sev}/10 (image size heuristic)."




class GeocoderThread(QThread):
    """FIX #2: Run Nominatim geocoding off the main thread to prevent UI freeze."""
    result   = pyqtSignal(float, float, str)   # lat, lng, display_name
    error    = pyqtSignal(str)

    def __init__(self, query=None, lat=None, lng=None):
        super().__init__()
        self.query = query   # forward geocode
        self.lat   = lat     # reverse geocode
        self.lng   = lng

    def run(self):
        import urllib.request, urllib.parse
        headers = {"User-Agent": "PotholeFixApp/1.0"}
        try:
            if self.query:
                url = "https://nominatim.openstreetmap.org/search?" + urllib.parse.urlencode({
                    "q": self.query, "format": "json", "limit": 1
                })
                req = urllib.request.Request(url, headers=headers)
                with urllib.request.urlopen(req, timeout=8) as r:
                    data = json.loads(r.read())
                if data:
                    self.result.emit(float(data[0]["lat"]), float(data[0]["lon"]),
                                     data[0].get("display_name",""))
                else:
                    self.error.emit("No results found. Try a different address.")
            elif self.lat is not None:
                url = "https://nominatim.openstreetmap.org/reverse?" + urllib.parse.urlencode({
                    "lat": self.lat, "lon": self.lng, "format": "json"
                })
                req = urllib.request.Request(url, headers=headers)
                with urllib.request.urlopen(req, timeout=8) as r:
                    data = json.loads(r.read())
                self.result.emit(self.lat, self.lng, data.get("display_name",""))
        except Exception as e:
            self.error.emit(f"Network error: {e}")

# ── Map picker dialog (OpenStreetMap tiles via QLabel + simple overlay) ────────

class MapPickerDialog(QDialog):
    """
    Map location picker with address search and coordinate entry.
    Pass initial_lat/initial_lng to pre-fill from GPS detection.
    """
    location_picked = pyqtSignal(float, float, str)

    def __init__(self, parent=None, initial_lat=None, initial_lng=None,
                 initial_address=""):
        super().__init__(parent)
        self.setWindowTitle("📍 Pick Location on Map")
        self.setMinimumSize(720, 580)
        self.setStyleSheet(GLOBAL_SS)
        # Use GPS-detected coords if provided, else Mangaluru default
        self.lat     = initial_lat if initial_lat is not None else 12.8698
        self.lng     = initial_lng if initial_lng is not None else 74.8426
        self.address = initial_address
        self._build()

    def _build(self):
        lay = QVBoxLayout(self)
        lay.setContentsMargins(20,18,20,18); lay.setSpacing(12)
        lay.addWidget(lbl("Pick location – enter coordinates or search address", 13, bold=True))

        # Search bar
        search_row = QHBoxLayout()
        self.search_in = QLineEdit()
        self.search_in.setPlaceholderText("Type address or area, e.g. MG Road, Mangaluru")
        self.search_in.returnPressed.connect(self._geocode)
        search_row.addWidget(self.search_in)
        self._search_btn = btn("🔍 Search", C["blue"], small=True)
        self._search_btn.clicked.connect(self._geocode)
        search_row.addWidget(self._search_btn)
        lay.addLayout(search_row)

        # Coordinate entry
        coord_grp = QGroupBox("Coordinates")
        cg = QHBoxLayout(coord_grp); cg.setSpacing(14)
        cg.addWidget(lbl("Latitude:", 12, color=C["muted"]))
        self.lat_in = QDoubleSpinBox()
        self.lat_in.setRange(-90,90); self.lat_in.setDecimals(6)
        self.lat_in.setValue(self.lat)   # pre-filled from GPS if detected
        self.lat_in.valueChanged.connect(self._update_map_lbl)
        cg.addWidget(self.lat_in)
        cg.addWidget(lbl("Longitude:", 12, color=C["muted"]))
        self.lng_in = QDoubleSpinBox()
        self.lng_in.setRange(-180,180); self.lng_in.setDecimals(6)
        self.lng_in.setValue(self.lng)   # pre-filled from GPS if detected
        self.lng_in.valueChanged.connect(self._update_map_lbl)
        cg.addWidget(self.lng_in)
        self._rev_btn = btn("📍 Reverse Geocode", C["purple"], small=True)
        self._rev_btn.clicked.connect(self._reverse_geocode)
        cg.addWidget(self._rev_btn)
        lay.addWidget(coord_grp)

        # Address result
        # Show pre-filled address from GPS detection if available
        initial_text = f"📍 {self.address[:140]}" if self.address else "Address: –"
        self.addr_lbl = lbl(initial_text, 12, color=C["cyan"])
        self.addr_lbl.setWordWrap(True)
        lay.addWidget(self.addr_lbl)

        # Map hint panel
        map_frame = card()
        map_frame.setFixedHeight(220)
        mfl = QVBoxLayout(map_frame); mfl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        mfl.addWidget(lbl("🗺️", 48, color=C["blue"]))
        mfl.addWidget(lbl("Map View", 15, bold=True))
        self.map_coord_lbl = lbl(f"📍 {self.lat:.5f}, {self.lng:.5f}", 13, color=C["cyan"])
        self.map_coord_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        mfl.addWidget(self.map_coord_lbl)
        hint = lbl("Enter coordinates above and click Reverse Geocode to get address.\n"
                   "For full interactive map, open in browser: openstreetmap.org", 11, color=C["muted"])
        hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        hint.setWordWrap(True)
        mfl.addWidget(hint)
        osm_btn = btn("🌐 Open in OpenStreetMap Browser", C["blue"], small=True)
        osm_btn.clicked.connect(self._open_osm)
        mfl.addWidget(osm_btn)
        lay.addWidget(map_frame)

        btn_row = QHBoxLayout()
        confirm = btn("✅ Confirm Location", C["green"])
        confirm.clicked.connect(self._confirm)
        cancel  = btn("Cancel", C["input"])
        cancel.clicked.connect(self.reject)
        btn_row.addWidget(confirm); btn_row.addWidget(cancel)
        lay.addLayout(btn_row)

    def _set_search_busy(self, busy):
        self._search_btn.setEnabled(not busy)
        self._rev_btn.setEnabled(not busy)
        self._search_btn.setText("⏳ Searching…" if busy else "🔍 Search")
        self._rev_btn.setText("⏳ …" if busy else "📍 Reverse Geocode")

    def _geocode(self):
        query = self.search_in.text().strip()
        if not query: return
        self._set_search_busy(True)
        self.addr_lbl.setText("Searching…")
        self._geo_thread = GeocoderThread(query=query)
        self._geo_thread.result.connect(self._on_geo_result)
        self._geo_thread.error.connect(self._on_geo_error)
        self._geo_thread.finished.connect(lambda: self._set_search_busy(False))
        self._geo_thread.start()

    def _reverse_geocode(self):
        lat = self.lat_in.value(); lng = self.lng_in.value()
        self._set_search_busy(True)
        self.addr_lbl.setText("Fetching address…")
        self._rev_thread = GeocoderThread(lat=lat, lng=lng)
        self._rev_thread.result.connect(self._on_geo_result)
        self._rev_thread.error.connect(self._on_geo_error)
        self._rev_thread.finished.connect(lambda: self._set_search_busy(False))
        self._rev_thread.start()

    def _on_geo_result(self, lat, lng, address):
        self.lat_in.setValue(lat); self.lng_in.setValue(lng)
        self.address = address
        self.addr_lbl.setText(f"📍 {address[:140]}" if address else "📍 Location set")
        self._update_map_lbl()

    def _on_geo_error(self, msg):
        self.addr_lbl.setText(f"⚠ {msg}")

    def _open_osm(self):
        """Open OpenStreetMap at current coordinates in default browser."""
        import webbrowser
        lat = self.lat_in.value()
        lng = self.lng_in.value()
        url = (f"https://www.openstreetmap.org/?mlat={lat}&mlon={lng}"
               f"#map=17/{lat}/{lng}&layers=M")
        webbrowser.open(url)
        # Update label too
        self._update_map_lbl()

    def _update_map_lbl(self):
        lat = self.lat_in.value(); lng = self.lng_in.value()
        self.map_coord_lbl.setText(f"📍 {lat:.6f}, {lng:.6f}")

    def _confirm(self):
        self.lat     = self.lat_in.value()
        self.lng     = self.lng_in.value()
        # Emit signal (kept for backward compat) then accept
        self.location_picked.emit(self.lat, self.lng, self.address)
        self.accept()  # caller reads dlg.lat / dlg.lng / dlg.address directly


# ── Chart widget ───────────────────────────────────────────────────────────────

class ChartWidget(FigureCanvas):
    def __init__(self, figsize=(5,3), parent=None):
        self.fig = Figure(figsize=figsize, facecolor=C["card"])
        super().__init__(self.fig)
        self.setParent(parent)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

    def draw_bar(self, labels, values, colors=None, title="", xlabel=""):
        self.fig.clear()
        ax = self.fig.add_subplot(111, facecolor=C["card"])
        cols = colors or [C["blue"]]*len(values)
        bars = ax.barh(labels, values, color=cols, height=0.55, edgecolor="none")
        ax.set_title(title, color=C["text"], fontsize=11, pad=8, fontweight="bold")
        ax.set_xlabel(xlabel, color=C["muted"], fontsize=9)
        ax.tick_params(colors=C["muted"], labelsize=8)
        ax.spines[:].set_visible(False)
        ax.xaxis.grid(True, color=C["border"], linewidth=0.5, linestyle="--")
        ax.set_axisbelow(True)
        for bar, val in zip(bars, values):
            ax.text(bar.get_width()+0.5, bar.get_y()+bar.get_height()/2,
                    f"{val:.1f}", va="center", ha="left", color=C["text"], fontsize=8)
        self.fig.tight_layout(pad=1.2); self.draw()

    def draw_pie(self, labels, values, colors=None, title=""):
        self.fig.clear()
        ax = self.fig.add_subplot(111, facecolor=C["card"])
        cols = colors or [C["blue"],C["green"],C["amber"],C["red"],C["purple"]]
        wedges,texts,autotexts = ax.pie(values, labels=None, autopct="%1.0f%%",
            colors=cols[:len(values)], startangle=90,
            wedgeprops={"edgecolor":C["card"],"linewidth":2})
        for at in autotexts: at.set_color(C["text"]); at.set_fontsize(9)
        ax.legend(labels, loc="lower center", ncol=3, fontsize=8,
                  labelcolor=C["text"], facecolor=C["card"], edgecolor=C["border"],
                  framealpha=0.8, bbox_to_anchor=(0.5,-0.12))
        ax.set_title(title, color=C["text"], fontsize=11, pad=8, fontweight="bold")
        self.fig.tight_layout(pad=1.0); self.draw()

    def draw_line(self, x_vals, y_vals, title="", xlabel="", color=None):
        self.fig.clear()
        ax = self.fig.add_subplot(111, facecolor=C["card"])
        col = color or C["cyan"]
        ax.plot(x_vals, y_vals, color=col, linewidth=2, marker="o",
                markersize=5, markerfacecolor=C["card"], markeredgecolor=col, markeredgewidth=2)
        ax.fill_between(range(len(y_vals)), y_vals, alpha=0.12, color=col)
        ax.set_title(title, color=C["text"], fontsize=11, pad=8, fontweight="bold")
        ax.set_xlabel(xlabel, color=C["muted"], fontsize=9)
        ax.set_xticks(range(len(x_vals)))
        ax.set_xticklabels(x_vals, rotation=35, ha="right", fontsize=7)
        ax.tick_params(colors=C["muted"], labelsize=8)
        ax.spines[:].set_visible(False)
        ax.yaxis.grid(True, color=C["border"], linewidth=0.5, linestyle="--")
        ax.set_axisbelow(True)
        self.fig.tight_layout(pad=1.2); self.draw()


# ── Sidebar button ─────────────────────────────────────────────────────────────

class SidebarButton(QPushButton):
    def __init__(self, icon, text):
        super().__init__(f"  {icon}  {text}")
        self.setCheckable(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedHeight(48)
        self.setActive(False)

    def setActive(self, active):
        if active:
            self.setStyleSheet(f"""QPushButton{{background:{C['blue']}22;color:{C['blue']};
                border:none;border-left:3px solid {C['blue']};border-radius:0;
                text-align:left;padding-left:16px;font-weight:600;font-size:14px;}}""")
        else:
            self.setStyleSheet(f"""QPushButton{{background:transparent;color:{C['muted']};
                border:none;border-left:3px solid transparent;border-radius:0;
                text-align:left;padding-left:16px;font-size:13px;}}
                QPushButton:hover{{background:{C['hover']};color:{C['text']};}}""")
        self.setChecked(active)


# ═══════════════════════════════════════════════════════════════════════════════
# LOGIN / REGISTER
# ═══════════════════════════════════════════════════════════════════════════════

class LoginWindow(QDialog):
    logged_in = pyqtSignal(dict)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("PotholeFix – Sign In")
        self.setFixedSize(440, 520)
        self.setStyleSheet(GLOBAL_SS)
        self._build()

    def _build(self):
        lay = QVBoxLayout(self); lay.setContentsMargins(44,44,44,44); lay.setSpacing(0)
        ico = QLabel("🚧"); ico.setAlignment(Qt.AlignmentFlag.AlignCenter)
        ico.setStyleSheet("font-size:48px;background:transparent;")
        lay.addWidget(ico); lay.addSpacing(8)
        t = lbl("PotholeFix",22,bold=True); t.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lay.addWidget(t)
        sub = lbl("Infrastructure Management System",12,color=C["muted"])
        sub.setAlignment(Qt.AlignmentFlag.AlignCenter); lay.addWidget(sub)
        lay.addSpacing(28)

        frm = card(); frm.setStyleSheet(f"QFrame{{background:{C['card']};border-radius:12px;}}")
        fl = QVBoxLayout(frm); fl.setContentsMargins(24,24,24,24); fl.setSpacing(14)
        fl.addWidget(lbl("Email",12,color=C["muted"]))
        self.email_in = QLineEdit(); self.email_in.setPlaceholderText("admin@potholefix.gov")
        fl.addWidget(self.email_in)
        fl.addWidget(lbl("Password",12,color=C["muted"]))
        self.pass_in = QLineEdit(); self.pass_in.setEchoMode(QLineEdit.EchoMode.Password)
        self.pass_in.setPlaceholderText("••••••••"); self.pass_in.returnPressed.connect(self._login)
        fl.addWidget(self.pass_in)
        fl.addSpacing(6)
        login_btn = btn("Sign In →", C["blue"]); login_btn.setFixedHeight(44)
        login_btn.clicked.connect(self._login); fl.addWidget(login_btn)
        self.err = lbl("",11,color=C["red"]); self.err.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.err.hide(); fl.addWidget(self.err)
        lay.addWidget(frm); lay.addSpacing(14)

        reg = btn("Create Account", C["input"]); reg.setFixedHeight(38)
        reg.clicked.connect(self._register); lay.addWidget(reg)
        hint = lbl("Demo: admin@potholefix.gov / admin123",10,color=C["dim"])
        hint.setAlignment(Qt.AlignmentFlag.AlignCenter); lay.addWidget(hint)

    def _login(self):
        user = db.authenticate_user(self.email_in.text().strip(), self.pass_in.text())
        if user:
            self.logged_in.emit(user); self.accept()
        else:
            self.err.setText("Invalid email or password."); self.err.show()

    def _register(self):
        dlg = RegisterDialog(self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self.email_in.setText(dlg.created_email); self.pass_in.setFocus()


class RegisterDialog(QDialog):
    def __init__(self, parent=None, crew_only=False):
        super().__init__(parent)
        self.crew_only = crew_only
        self.created_email = ""
        self.setWindowTitle("Register" if not crew_only else "Add Repair Crew")
        self.setFixedSize(400,360)
        self.setStyleSheet(GLOBAL_SS)
        self._build()

    def _build(self):
        lay = QFormLayout(self); lay.setContentsMargins(28,28,28,28); lay.setSpacing(14)
        self.name_in  = QLineEdit(); self.name_in.setPlaceholderText("Full name")
        self.email_in = QLineEdit(); self.email_in.setPlaceholderText("you@example.com")
        self.pass_in  = QLineEdit(); self.pass_in.setEchoMode(QLineEdit.EchoMode.Password)
        self.pass_in.setPlaceholderText("Min 6 characters")
        self.role_in  = QComboBox()
        if self.crew_only:
            self.role_in.addItem("Repair Crew")
            self.role_in.setEnabled(False)
        else:
            # Security fix: public registration is Citizen-only
            # Repair Crew added by Admin; Admin promoted via DB
            self.role_in.addItem("Citizen")
            self.role_in.setEnabled(False)
        lay.addRow(lbl("Name",12,color=C["muted"]),       self.name_in)
        lay.addRow(lbl("Email",12,color=C["muted"]),      self.email_in)
        lay.addRow(lbl("Password",12,color=C["muted"]),   self.pass_in)
        # Only show role selector for admin adding crew (crew_only mode)
        if self.crew_only:
            lay.addRow(lbl("Role",12,color=C["muted"]), self.role_in)
        self.err = lbl("",11,color=C["red"]); lay.addRow(self.err)
        ok = btn("Register ✓", C["green"]); ok.clicked.connect(self._go); lay.addRow(ok)

    def _go(self):
        n=self.name_in.text().strip(); e=self.email_in.text().strip()
        p=self.pass_in.text(); r=self.role_in.currentText()
        if not all([n,e,p]): self.err.setText("All fields required."); return
        # FIX #10: proper email validation
        import re
        if not re.match(r'^[^@\s]+@[^@\s]+\.[^@\s]+$', e):
            self.err.setText("Enter a valid email address."); return
        if len(p)<6: self.err.setText("Password min 6 chars."); return
        user = db.create_user(n,e,p,r)
        if user:
            self.created_email = e
            QMessageBox.information(self,"✅ Done",f"Account created!\nLogin: {e}")
            self.accept()
        else:
            self.err.setText("Email already registered.")




class TrafficDialog(QDialog):
    """
    Admin dialog to view and edit road traffic volumes.
    Traffic data drives priority score calculations.
    Road types auto-suggest volumes if none set.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("🚗  Traffic Data Management")
        self.setMinimumSize(680, 500)
        self.setStyleSheet(GLOBAL_SS)
        self._build()
        self._refresh()

    def _build(self):
        lay = QVBoxLayout(self); lay.setContentsMargins(20,18,20,18); lay.setSpacing(12)
        lay.addWidget(lbl("🚗  Road Traffic Volumes", 15, bold=True))
        lay.addWidget(lbl(
            "Traffic volume × severity = priority score. "
            "Higher volume roads get repaired faster.",
            11, color=C["muted"]))

        # Add/Edit form
        form_card = card()
        fl = QHBoxLayout(form_card); fl.setContentsMargins(14,12,14,12); fl.setSpacing(10)
        fl.addWidget(lbl("Road Name:", 11, color=C["muted"]))
        self.road_in = QLineEdit(); self.road_in.setPlaceholderText("e.g. MG Road")
        self.road_in.setFixedWidth(200); fl.addWidget(self.road_in)
        fl.addWidget(lbl("Vehicles/Day:", 11, color=C["muted"]))
        self.vol_in = QSpinBox(); self.vol_in.setRange(100, 500000)
        self.vol_in.setValue(10000); self.vol_in.setSingleStep(1000)
        self.vol_in.setFixedWidth(100); fl.addWidget(self.vol_in)
        sv = btn("💾 Save", C["green"], small=True); sv.clicked.connect(self._save); fl.addWidget(sv)
        rc = btn("♻ Recalculate All Scores", C["purple"], small=True)
        rc.clicked.connect(self._recalc); fl.addWidget(rc)
        fl.addStretch()
        lay.addWidget(form_card)

        # Road type quick-fill buttons
        hint_row = QHBoxLayout(); hint_row.setSpacing(6)
        hint_row.addWidget(lbl("Quick fill:", 10, color=C["dim"]))
        for label_text, vol in [("NH/SH Highway",50000),("City Main Road",20000),
                      ("Secondary Road",8000),("Lane/Internal",2000)]:
            qb = btn(label_text, C["input"], small=True)
            qb.clicked.connect(lambda _, v=vol: self.vol_in.setValue(v))
            hint_row.addWidget(qb)
        hint_row.addStretch()
        lay.addLayout(hint_row)

        self.table = QTableWidget()
        self.table.setColumnCount(3)
        self.table.setHorizontalHeaderLabels(["Road Name","Avg Vehicles/Day","Last Updated"])
        self.table.setAlternatingRowColors(True)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.verticalHeader().setVisible(False)
        self.table.setShowGrid(False)
        self.table.setSortingEnabled(True)
        self.table.doubleClicked.connect(self._load_row)
        lay.addWidget(self.table)
        lay.addWidget(lbl("Double-click a row to load for editing", 10, color=C["dim"]))

        cl = btn("Close", C["input"]); cl.clicked.connect(self.accept); lay.addWidget(cl)

    def _refresh(self):
        data = db.get_all_traffic()
        self.table.setRowCount(len(data))
        for row, t in enumerate(data):
            cells = [t["road_name"], f"{t['avg_daily_traffic']:,}", t["last_updated"][:16]]
            colors = [C["text"], C["cyan"], C["dim"]]
            for col, (txt, cc) in enumerate(zip(cells, colors)):
                item = QTableWidgetItem(txt)
                item.setForeground(QColor(cc))
                self.table.setItem(row, col, item)
            self.table.setRowHeight(row, 40)

    def _save(self):
        road = self.road_in.text().strip()
        vol  = self.vol_in.value()
        if not road:
            QMessageBox.warning(self, "Error", "Road name is required."); return
        db.upsert_traffic(road, vol)
        n = db.recalculate_all_scores()
        QMessageBox.information(self, "✅ Saved",
            f"Traffic saved for '{road}'.\n{n} report scores recalculated.")
        self.road_in.clear(); self._refresh()

    def _recalc(self):
        n = db.recalculate_all_scores()
        QMessageBox.information(self, "Done", f"Recalculated {n} report scores.")

    def _load_row(self, index):
        road = self.table.item(index.row(), 0).text()
        t    = db.get_traffic_for_road(road)
        if t:
            self.road_in.setText(t["road_name"])
            self.vol_in.setValue(t["avg_daily_traffic"])

# ═══════════════════════════════════════════════════════════════════════════════
# DASHBOARD
# ═══════════════════════════════════════════════════════════════════════════════

class DashboardView(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._build(); self.refresh()

    def _build(self):
        lay = QVBoxLayout(self); lay.setContentsMargins(32,24,32,24); lay.setSpacing(18)
        hdr = QHBoxLayout()
        hdr.addWidget(lbl("📊  Dashboard",18,bold=True)); hdr.addStretch()
        traffic_btn = btn("🚗 Traffic Data", C["input"], small=True)
        traffic_btn.setToolTip("View and edit road traffic volumes for priority scoring")
        traffic_btn.clicked.connect(lambda: TrafficDialog(self).exec())
        hdr.addWidget(traffic_btn)
        r=btn("🔄 Refresh",C["input"],small=True); r.clicked.connect(self.refresh); hdr.addWidget(r)
        lay.addLayout(hdr)

        self._stat_row = QHBoxLayout(); self._stat_row.setSpacing(16)
        self._stat_vals = {}
        for title,icon,color in [
            ("Total Reports","📋",C["blue"]),("Active Repairs","🔧",C["amber"]),
            ("Resolved","✅",C["green"]),("High Priority","🚨",C["red"])]:
            f,v = stat_card(title,"–",icon,color,self)
            self._stat_row.addWidget(f); self._stat_vals[title]=v
        lay.addLayout(self._stat_row)

        charts = QHBoxLayout(); charts.setSpacing(16)
        self.bar_chart = ChartWidget((5,3.2))
        bc = card(); bl = QVBoxLayout(bc); bl.setContentsMargins(12,10,12,10)
        bl.addWidget(lbl("🔥  Top Priority Reports",12,bold=True)); bl.addWidget(self.bar_chart)
        charts.addWidget(bc,3)
        self.pie_chart = ChartWidget((3.5,3.2))
        pc = card(); pl = QVBoxLayout(pc); pl.setContentsMargins(12,10,12,10)
        pl.addWidget(lbl("📊  Status Distribution",12,bold=True)); pl.addWidget(self.pie_chart)
        charts.addWidget(pc,2)
        lay.addLayout(charts)

        self.line_chart = ChartWidget((8,2.8))
        lc = card(); ll = QVBoxLayout(lc); ll.setContentsMargins(12,10,12,10)
        ll.addWidget(lbl("📈  Monthly Report Trend",12,bold=True)); ll.addWidget(self.line_chart)
        lay.addWidget(lc)

    def refresh(self):
        a = db.get_analytics()
        self._stat_vals["Total Reports"].setText(str(a["total"]))
        self._stat_vals["Active Repairs"].setText(str(a["active"]))
        self._stat_vals["Resolved"].setText(str(a["fixed"]))
        self._stat_vals["High Priority"].setText(str(a["high_priority"]))

        reports = db.get_reports(sort_by="priority_score",order="DESC",limit=10)
        if reports:
            labels=[f"#{r['id']} {r['road_name'][:18]}" for r in reports]
            values=[r["priority_score"] for r in reports]
            colors=[default_engine.get_label_color(v) for v in values]
            self.bar_chart.draw_bar(labels,values,colors,"Priority Scores (Top 10)","Score")

        sd=a["status_dist"]
        if sd:
            self.pie_chart.draw_pie(
                [d["status"] for d in sd],[d["cnt"] for d in sd],
                [STATUS_COLORS.get(d["status"],C["blue"]) for d in sd],"Report Status")

        m=a["monthly"]
        if m:
            self.line_chart.draw_line([x["month"] for x in m],[x["cnt"] for x in m],
                                      "Monthly Reports","Month",C["cyan"])




class GPSExtractThread(QThread):
    """Run GPS extraction off the main thread (OCR can take 1-3 seconds)."""
    result  = pyqtSignal(object)   # GPSResult or None
    error   = pyqtSignal(str)

    def __init__(self, image_paths):
        super().__init__()
        self.image_paths = image_paths

    def run(self):
        try:
            from gps_extractor import extract_gps_from_images
            result = extract_gps_from_images(self.image_paths)
            self.result.emit(result)
        except Exception as e:
            self.error.emit(str(e))

# ═══════════════════════════════════════════════════════════════════════════════
# CITIZEN – NEW REPORT (with image upload + ML analysis + map picker)
# ═══════════════════════════════════════════════════════════════════════════════

class NewReportDialog(QDialog):
    def __init__(self, current_user, parent=None):
        super().__init__(parent)
        self.current_user = current_user
        self.image_paths  = []   # final stored paths
        self.staged_paths = []   # user-selected source files (not yet stored)
        self.ml_severity  = None
        self.picked_lat   = 12.8698
        self.picked_lng   = 74.8426
        self.picked_addr  = ""
        self._gps_detected = False   # True once GPS auto-filled from photo
        self.setWindowTitle("🚧  Report a Pothole")
        self.setMinimumSize(640, 780)
        self.setStyleSheet(GLOBAL_SS)
        self._build()

    def _build(self):
        outer = QVBoxLayout(self); outer.setContentsMargins(0,0,0,0); outer.setSpacing(0)

        # Scrollable content
        scroll = QScrollArea(); scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        content = QWidget(); content.setStyleSheet(f"background:{C['bg']};")
        lay = QVBoxLayout(content); lay.setContentsMargins(28,24,28,24); lay.setSpacing(16)
        scroll.setWidget(content); outer.addWidget(scroll,1)

        lay.addWidget(lbl("🚧  New Pothole Report",17,bold=True))
        lay.addWidget(sep())

        # ── Personal info ──────────────────────────────────────────────────────
        grp1 = QGroupBox("Your Details"); g1l = QFormLayout(grp1); g1l.setSpacing(10)
        self.name_in  = QLineEdit(self.current_user["name"])
        self.email_in = QLineEdit(self.current_user["email"])
        self.phone_in = QLineEdit(); self.phone_in.setPlaceholderText("Optional")
        g1l.addRow("Name *",  self.name_in)
        g1l.addRow("Email *", self.email_in)
        g1l.addRow("Phone",   self.phone_in)
        lay.addWidget(grp1)

        # ── Location ───────────────────────────────────────────────────────────
        grp2 = QGroupBox("Location"); g2l = QVBoxLayout(grp2); g2l.setSpacing(10)
        map_row = QHBoxLayout()
        map_btn = btn("📍 Pick on Map",C["cyan"],small=True)
        map_btn.clicked.connect(self._pick_map)
        map_row.addWidget(map_btn)
        # Re-run GPS extraction button (if user wants to retry)
        re_gps = btn("📡 Re-detect GPS",C["input"],small=True)
        re_gps.setToolTip("Re-extract GPS from uploaded photos")
        re_gps.clicked.connect(lambda: self._run_gps_extract(self.staged_paths) if self.staged_paths else
                               QMessageBox.information(self,"No Photos","Upload photos first."))
        map_row.addWidget(re_gps)
        self.coord_lbl = lbl(f"  {self.picked_lat:.5f}, {self.picked_lng:.5f}",
                              12,color=C["muted"])
        map_row.addWidget(self.coord_lbl); map_row.addStretch()
        g2l.addLayout(map_row)
        self.road_in = QLineEdit(); self.road_in.setPlaceholderText("Road name, e.g. MG Road")
        self.loc_in  = QLineEdit(); self.loc_in.setPlaceholderText("Near landmark or area description")
        g2l.addWidget(lbl("Road Name *",11,color=C["muted"])); g2l.addWidget(self.road_in)
        g2l.addWidget(lbl("Location Description *",11,color=C["muted"])); g2l.addWidget(self.loc_in)
        lay.addWidget(grp2)

        # ── Photo upload + ML ──────────────────────────────────────────────────
        grp3 = QGroupBox("Photos & ML Severity Analysis"); g3l = QVBoxLayout(grp3); g3l.setSpacing(10)
        img_row = QHBoxLayout()
        add_img = btn("📷 Add Photos",C["blue"],small=True); add_img.clicked.connect(self._add_images)
        clear_img = btn("✕ Clear",C["input"],small=True); clear_img.clicked.connect(self._clear_images)
        img_row.addWidget(add_img); img_row.addWidget(clear_img); img_row.addStretch()
        g3l.addLayout(img_row)

        self.img_list = QListWidget(); self.img_list.setFixedHeight(90)
        self.img_list.setStyleSheet(f"background:{C['input']};border-radius:6px;")
        g3l.addWidget(self.img_list)

        # Thumbnail preview row
        self.thumb_row = QHBoxLayout(); self.thumb_row.setSpacing(8)
        thumb_frame = QFrame(); thumb_frame.setLayout(self.thumb_row)
        g3l.addWidget(thumb_frame)

        # GPS status label (updated when photos are added)
        self._gps_status_lbl = lbl(
            "  📷 Add photos taken with GPS Map Camera to auto-detect location",
            11, color=C["dim"])
        self._gps_status_lbl.setWordWrap(True)
        g3l.addWidget(self._gps_status_lbl)

        ml_row = QHBoxLayout()
        self._analyse_btn = btn("🤖 Analyse with ML",C["purple"],small=True)
        self._analyse_btn.clicked.connect(self._run_ml)
        ml_row.addWidget(self._analyse_btn)
        self.ml_lbl = lbl("  ML Severity: not yet analysed",12,color=C["muted"])
        ml_row.addWidget(self.ml_lbl); ml_row.addStretch()
        g3l.addLayout(ml_row)
        lay.addWidget(grp3)

        # ── Severity + description ─────────────────────────────────────────────
        grp4 = QGroupBox("Damage Details"); g4l = QFormLayout(grp4); g4l.setSpacing(10)
        # FIX: Citizen cannot manually set severity — ML sets it automatically.
        # We keep sev_spin hidden for internal use (ML result storage).
        self.sev_spin = QSpinBox(); self.sev_spin.setRange(1,10); self.sev_spin.setValue(5)
        self.sev_spin.valueChanged.connect(self._preview_score)
        self.sev_spin.hide()   # hidden from citizen

        sev_row = QHBoxLayout()
        self.sev_display = lbl("  Will be set by ML analysis (upload a photo first)",
                                11, color=C["muted"])
        self.sev_display.setWordWrap(True)
        sev_row.addWidget(self.sev_display)
        self.sev_hint = lbl("", 11, color=C["amber"])
        sev_row.addWidget(self.sev_hint); sev_row.addStretch()
        g4l.addRow("Severity", sev_row)
        self.desc_in = QTextEdit(); self.desc_in.setPlaceholderText("Describe the pothole…")
        self.desc_in.setFixedHeight(80)
        g4l.addRow("Description", self.desc_in)
        lay.addWidget(grp4)

        # Score preview
        self.score_lbl = lbl("Estimated Priority Score: –",12,color=C["amber"])
        lay.addWidget(self.score_lbl)
        self.road_in.textChanged.connect(self._preview_score)

        self.err_lbl = lbl("",11,color=C["red"]); lay.addWidget(self.err_lbl)

        # Buttons
        btn_row = QHBoxLayout(); btn_row.setSpacing(10)
        submit = btn("✅ Submit Report",C["green"]); submit.setFixedHeight(44)
        submit.clicked.connect(self._submit)
        cancel = btn("Cancel",C["input"]); cancel.clicked.connect(self.reject)
        btn_row.addWidget(submit); btn_row.addWidget(cancel)

        # Fixed bottom bar
        bot = QFrame(); bot.setStyleSheet(f"background:{C['card']};border-top:1px solid {C['border']};")
        bl = QHBoxLayout(bot); bl.setContentsMargins(28,12,28,12)
        bl.addLayout(btn_row)
        outer.addWidget(bot)

        self._preview_score()

    def _pick_map(self):
        # Pass currently detected coords so map opens at the right location
        dlg = MapPickerDialog(self,
                              initial_lat=self.picked_lat,
                              initial_lng=self.picked_lng,
                              initial_address=self.picked_addr)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            lat  = dlg.lat
            lng  = dlg.lng
            addr = dlg.address
            self.picked_lat  = lat
            self.picked_lng  = lng
            self.picked_addr = addr
            self.coord_lbl.setText(f"  📍 {lat:.6f}, {lng:.6f}")
            if addr and not self.loc_in.text().strip():
                parts = [p.strip() for p in addr.split(",") if len(p.strip()) > 3]
                self.loc_in.setText(", ".join(parts[:3])[:100])
            if addr and not self.road_in.text().strip():
                import re
                road_m = re.search(
                    r'([A-Z][A-Za-z0-9 ]+ (?:Road|Street|Lane|Nagar|Circle|'
                    r'Bridge|Colony|Highway|NH|SH|Main|Cross))',
                    addr)
                if road_m:
                    self.road_in.setText(road_m.group(1).strip())
            self._preview_score()

    def _add_images(self):
        files, _ = QFileDialog.getOpenFileNames(
            self,"Select Photos","",
            "Images (*.jpg *.jpeg *.png *.bmp *.webp)")
        if not files: return
        newly_added = []
        for f in files[:5]:
            if f not in self.staged_paths:
                self.staged_paths.append(f)
                self.img_list.addItem(QListWidgetItem(f"📷 {Path(f).name}"))
                self._add_thumb(f)
                newly_added.append(f)

        # Auto-extract GPS from newly added images
        if newly_added and not self._gps_detected:
            self._run_gps_extract(newly_added)

    def _run_gps_extract(self, paths):
        """Run GPS extraction in background thread."""
        self._gps_status_lbl.setText("  🔍 Detecting GPS location from photo…")
        self._gps_status_lbl.setStyleSheet(f"color:{C['cyan']};font-size:11px;background:transparent;")
        self._gps_thread = GPSExtractThread(paths)
        self._gps_thread.result.connect(self._on_gps_result)
        self._gps_thread.error.connect(self._on_gps_error)
        self._gps_thread.start()

    def _on_gps_result(self, result):
        if result is None:
            self._gps_status_lbl.setText(
                "  ℹ No GPS data found in photo. Use map picker or enter coordinates manually.")
            self._gps_status_lbl.setStyleSheet(f"color:{C['amber']};font-size:11px;background:transparent;")
            return

        # Show detected info and ask user to confirm
        method_icon = "📡" if result.method == "EXIF" else "🔍"
        conf_icon   = {"high":"✅","medium":"⚠","low":"❓"}.get(result.confidence,"")
        info = (f"  {method_icon} GPS detected via {result.method} {conf_icon}\n"
                f"  📍 {result.lat:.6f}, {result.lng:.6f}")
        if result.address:
            info += f"\n  🏠 {result.address[:80]}"
        if result.timestamp:
            info += f"\n  🕐 {result.timestamp}"

        from PyQt6.QtWidgets import QMessageBox
        reply = QMessageBox.question(
            self, f"{method_icon} GPS Location Detected",
            f"Location found in photo:\n\n"
            f"Lat: {result.lat}  |  Lng: {result.lng}\n"
            f"{'Address: ' + result.address[:60] if result.address else ''}\n"
            f"Method: {result.method} ({result.confidence} confidence)\n\n"
            f"Auto-fill coordinates and location?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.Yes
        )

        if reply == QMessageBox.StandardButton.Yes:
            self.picked_lat  = result.lat
            self.picked_lng  = result.lng
            self.picked_addr = result.address
            self.coord_lbl.setText(f"  📍 {result.lat:.6f}, {result.lng:.6f}")

            # Auto-fill location text if empty
            if result.address and not self.loc_in.text().strip():
                # Clean address: take first meaningful part
                addr_clean = result.address.replace("  "," ").strip()
                self.loc_in.setText(addr_clean[:100])

            # Auto-fill road name if empty (extract from address)
            if result.address and not self.road_in.text().strip():
                import re
                road_match = re.search(
                    r'([A-Z][a-z]+ (?:Road|Street|Lane|Nagar|Circle|Bridge|Cross|Main|Highway|NH|SH)[\\w]*)',
                    result.address
                )
                if road_match:
                    self.road_in.setText(road_match.group(1))

            self._gps_detected = True
            self._gps_status_lbl.setText(
                f"  {method_icon} GPS auto-filled  ({result.method}, {result.confidence} confidence)")
            self._gps_status_lbl.setStyleSheet(
                f"color:{C['green']};font-size:11px;background:transparent;")
            self._preview_score()
        else:
            self._gps_status_lbl.setText("  📍 GPS detected but not applied — fill manually.")
            self._gps_status_lbl.setStyleSheet(f"color:{C['muted']};font-size:11px;background:transparent;")

    def _on_gps_error(self, msg):
        self._gps_status_lbl.setText(f"  ⚠ GPS extraction error: {msg}")
        self._gps_status_lbl.setStyleSheet(f"color:{C['amber']};font-size:11px;background:transparent;")

    def _add_thumb(self, path):
        try:
            pix = QPixmap(path).scaled(72,72,Qt.AspectRatioMode.KeepAspectRatio,
                                       Qt.TransformationMode.SmoothTransformation)
            t = QLabel(); t.setPixmap(pix)
            t.setStyleSheet("border-radius:6px;background:transparent;")
            self.thumb_row.addWidget(t)
        except: pass

    def _clear_images(self):
        # FIX #17: confirm before wiping photos
        if self.staged_paths:
            if QMessageBox.question(
                self, "Clear Photos",
                f"Remove all {len(self.staged_paths)} staged photo(s)?"
            ) != QMessageBox.StandardButton.Yes:
                return
        self.staged_paths.clear()
        self.img_list.clear()
        while self.thumb_row.count():
            item = self.thumb_row.takeAt(0)
            if item.widget(): item.widget().deleteLater()
        self.ml_lbl.setText("  ML Severity: not yet analysed")
        self.ml_lbl.setStyleSheet(f"color:{C['muted']};font-size:12px;background:transparent;")
        self.ml_severity = None

    def _run_ml(self):
        if not self.staged_paths:
            QMessageBox.information(self,"No Images","Add at least one photo first.")
            return
        # FIX #25: disable button so it can't be double-clicked
        self._analyse_btn.setEnabled(False)
        self._analyse_btn.setText("🤖 Analysing…")
        self.ml_lbl.setText("  🤖 Analysing images, please wait…")
        self._ml_thread = MLAnalyser(self.staged_paths)
        self._ml_thread.result.connect(self._on_ml_result)
        self._ml_thread.start()

    def _on_ml_result(self, severity, note):
        self.ml_severity = severity
        self.sev_spin.setValue(severity)
        col = default_engine.get_label_color(severity * 10)
        self.ml_lbl.setText(f"  🤖 ML Severity: {severity}/10 — {note}")
        self.ml_lbl.setStyleSheet(f"color:{col};font-size:12px;background:transparent;")
        # Update the citizen-visible severity display label
        sev_col = SEV_COLORS[max(0, min(9, severity - 1))]
        sev_label = default_engine.get_label(severity * 10)
        self.sev_display.setText(f"  {severity}/10  [{sev_label}]")
        self.sev_display.setStyleSheet(
            f"color:{sev_col};font-size:13px;font-weight:bold;background:transparent;")
        # Re-enable analyse button
        self._analyse_btn.setEnabled(True)
        self._analyse_btn.setText("🤖 Analyse with ML")

    def _preview_score(self):
        road = self.road_in.text().strip()
        sev  = self.sev_spin.value()

        tvol  = db.get_or_estimate_traffic(road) if road else 8000
        all_t = [x["avg_daily_traffic"] for x in db.get_all_traffic()]
        max_t = max(all_t) if all_t else 8000
        score = default_engine.calculate_score(sev, tvol, max_t)
        lbl_t = default_engine.get_label(score)
        lcol  = default_engine.get_label_color(score)
        self.score_lbl.setText(f"Estimated Priority Score: {score:.1f}  [{lbl_t}]")
        self.score_lbl.setStyleSheet(f"color:{lcol};font-size:12px;background:transparent;")

    def _submit(self):
        name  = self.name_in.text().strip()
        email = self.email_in.text().strip()
        road  = self.road_in.text().strip()
        loc   = self.loc_in.text().strip()
        sev   = self.sev_spin.value()
        desc  = self.desc_in.toPlainText().strip()

        if not all([name,email,road,loc]):
            self.err_lbl.setText("Please fill all required (*) fields."); return
        import re
        if not re.match(r'^[^@\s]+@[^@\s]+\.[^@\s]+$', email):
            self.err_lbl.setText("Enter a valid email address."); return

        # FIX #35: Check for nearby existing reports
        nearby = db.get_nearby_reports(self.picked_lat, self.picked_lng, radius_m=50)
        if nearby:
            closest = nearby[0]
            reply = QMessageBox.question(
                self, "⚠ Nearby Report Exists",
                f"A report already exists {closest['distance_m']}m away:\n"
                f"  Road: {closest['road_name']}\n"
                f"  Status: {closest['status']}\n\n"
                f"Is this a different pothole?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No
            )
            if reply == QMessageBox.StandardButton.No:
                return

        # Save images to uploads dir
        stored = [db.save_image(p) for p in self.staged_paths]
        stored = [s for s in stored if s]

        tvol  = db.get_or_estimate_traffic(road) if road else 8000
        all_t = [x["avg_daily_traffic"] for x in db.get_all_traffic()]
        max_t = max(all_t) if all_t else 8000
        score = default_engine.calculate_score(sev, tvol, max_t)

        db.create_report(
            user_id=self.current_user["id"],
            citizen_name=name, email=email,
            phone=self.phone_in.text().strip() or None,
            location_text=loc, lat=self.picked_lat, lng=self.picked_lng,
            road_name=road, severity=sev,
            description=desc or None,
            image_paths=stored, priority_score=score,
            ml_severity=self.ml_severity
        )
        QMessageBox.information(self,"✅ Submitted",
            f"Report submitted!\nPriority Score: {score:.1f}  [{default_engine.get_label(score)}]")
        self.accept()




class EditReportDialog(QDialog):
    """FIX #19: Admin can edit road name, location, coordinates, severity."""
    def __init__(self, report, current_user, parent=None):
        super().__init__(parent)
        self.report = report
        self.current_user = current_user
        self.setWindowTitle(f"Edit Report #{report['id']}")
        self.setFixedSize(480, 420)
        self.setStyleSheet(GLOBAL_SS)
        self._build()

    def _build(self):
        lay = QFormLayout(self)
        lay.setContentsMargins(24, 20, 24, 20)
        lay.setSpacing(12)
        lay.addRow(lbl(f"Editing Report #{self.report['id']}", 14, bold=True))

        self.road_in = QLineEdit(self.report["road_name"])
        self.loc_in  = QLineEdit(self.report["location_text"])
        self.lat_in  = QDoubleSpinBox()
        self.lat_in.setRange(-90, 90); self.lat_in.setDecimals(6)
        self.lat_in.setValue(self.report["latitude"])
        self.lng_in  = QDoubleSpinBox()
        self.lng_in.setRange(-180, 180); self.lng_in.setDecimals(6)
        self.lng_in.setValue(self.report["longitude"])
        self.sev_in  = QSpinBox()
        self.sev_in.setRange(1, 10)
        self.sev_in.setValue(self.report["severity"])
        self.desc_in = QTextEdit(self.report.get("description") or "")
        self.desc_in.setFixedHeight(80)

        lay.addRow(lbl("Road Name", 11, color=C["muted"]),     self.road_in)
        lay.addRow(lbl("Location Text", 11, color=C["muted"]), self.loc_in)
        lay.addRow(lbl("Latitude", 11, color=C["muted"]),      self.lat_in)
        lay.addRow(lbl("Longitude", 11, color=C["muted"]),     self.lng_in)
        lay.addRow(lbl("Severity (1-10)", 11, color=C["muted"]), self.sev_in)
        lay.addRow(lbl("Description", 11, color=C["muted"]),   self.desc_in)

        self.err = lbl("", 11, color=C["red"]); lay.addRow(self.err)

        btn_row = QHBoxLayout()
        sv = btn("💾 Save Changes", C["blue"]); sv.clicked.connect(self._save)
        ca = btn("Cancel", C["input"]);         ca.clicked.connect(self.reject)
        btn_row.addWidget(sv); btn_row.addWidget(ca)
        lay.addRow(btn_row)

    def _save(self):
        road = self.road_in.text().strip()
        loc  = self.loc_in.text().strip()
        if not road or not loc:
            self.err.setText("Road name and location are required."); return
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        conn = db.get_conn()
        conn.execute("""
            UPDATE pothole_reports
            SET road_name=?, location_text=?, latitude=?, longitude=?,
                description=?, updated_at=?
            WHERE id=?
        """, (road, loc, self.lat_in.value(), self.lng_in.value(),
              self.desc_in.toPlainText().strip() or None, now, self.report["id"]))
        conn.commit()
        new_sev = self.sev_in.value()
        if new_sev != self.report["severity"]:
            db.update_report_severity(
                self.report["id"], new_sev,
                actor_id=self.current_user["id"],
                actor_name=self.current_user["name"]
            )
        db.log_history(conn, self.report["id"],
                       self.current_user["id"], self.current_user["name"],
                       "Report edited", None, f"road={road}")
        conn.commit(); conn.close()
        QMessageBox.information(self, "✅ Saved", "Report updated.")
        self.accept()

# ═══════════════════════════════════════════════════════════════════════════════
# REPORTS VIEW
# ═══════════════════════════════════════════════════════════════════════════════

class ReportsView(QWidget):
    def __init__(self, current_user, parent=None):
        super().__init__(parent)
        self.current_user = current_user
        self._reports = []
        self._build(); self.refresh()

    def _build(self):
        lay = QVBoxLayout(self); lay.setContentsMargins(32,24,32,24); lay.setSpacing(18)
        hdr = QHBoxLayout()
        hdr.addWidget(lbl("📋  Pothole Reports",18,bold=True)); hdr.addStretch()
        if self.current_user["role"] == "Citizen":
            a=btn("＋ New Report",C["green"]); a.clicked.connect(self._new_report); hdr.addWidget(a)
        r=btn("🔄",C["input"],small=True); r.clicked.connect(self.refresh); hdr.addWidget(r)
        lay.addLayout(hdr)

        filt = card(); fl = QHBoxLayout(filt); fl.setContentsMargins(16,14,16,14); fl.setSpacing(12)
        fl.addWidget(lbl("Search:",11,color=C["muted"]))
        self.search_in = QLineEdit(); self.search_in.setPlaceholderText("Road, location…")
        self.search_in.setFixedWidth(200); self.search_in.textChanged.connect(self.refresh)
        fl.addWidget(self.search_in)
        fl.addWidget(lbl("Status:",11,color=C["muted"]))
        self.status_cb = QComboBox()
        self.status_cb.addItems(["All","Pending","Scheduled","In Progress","Fixed","Unresolved"])
        self.status_cb.currentIndexChanged.connect(self.refresh); fl.addWidget(self.status_cb)
        fl.addWidget(lbl("Min Severity:",11,color=C["muted"]))
        self.sev_sp = QSpinBox(); self.sev_sp.setRange(0,10); self.sev_sp.setFixedWidth(65)
        self.sev_sp.valueChanged.connect(self.refresh); fl.addWidget(self.sev_sp)
        fl.addStretch()
        lay.addWidget(filt)

        self.table = QTableWidget()
        self.table.setColumnCount(9)
        self.table.setHorizontalHeaderLabels([
            "ID","Road Name","Severity","ML Sev","Priority","Status","Photos","Location","Date"])
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(0,QHeaderView.ResizeMode.ResizeToContents)
        self.table.verticalHeader().setVisible(False)
        self.table.setShowGrid(False)
        self.table.setSortingEnabled(True)
        self.table.doubleClicked.connect(self._open)
        lay.addWidget(self.table)
        self.count_lbl = lbl("",11,color=C["muted"]); lay.addWidget(self.count_lbl)

    def refresh(self):
        status = self.status_cb.currentText(); status = None if status=="All" else status
        sev    = self.sev_sp.value() or None
        search = self.search_in.text().strip() or None
        uid    = self.current_user["id"] if self.current_user["role"]=="Citizen" else None
        self._reports = db.get_reports(status=status,min_severity=sev,search=search,user_id=uid)
        self.table.setRowCount(len(self._reports))
        for row,r in enumerate(self._reports):
            sc=r["priority_score"]; sev_i=r["severity"]
            ml_sev = str(r["ml_severity"]) if r.get("ml_severity") else "–"
            imgs = len(json.loads(r["image_paths"])) if r.get("image_paths") else 0
            # FIX #12: flag large discrepancy between citizen and ML severity
            ml_flag = ""
            if ml_sev != "–":
                try:
                    if abs(int(ml_sev) - sev_i) >= 3:
                        ml_flag = " ⚠"
                except Exception:
                    pass
            cells = [
                (str(r["id"]),C["muted"]),
                (r["road_name"],C["text"]),
                (f"  {sev_i}/10",SEV_COLORS[max(0,min(9,sev_i-1))]),
                (f"  {ml_sev}{ml_flag}",C["red"] if ml_flag else (C["purple"] if ml_sev!="–" else C["dim"])),
                (f"  {sc:.1f} [{default_engine.get_label(sc)}]",default_engine.get_label_color(sc)),
                (f"  {r['status']}",STATUS_COLORS.get(r["status"],C["muted"])),
                (f"  📷 {imgs}" if imgs else "  –",C["cyan"] if imgs else C["dim"]),
                (r["location_text"][:30]+"…" if len(r["location_text"])>30 else r["location_text"],C["muted"]),
                (r["created_at"][:10],C["dim"]),
            ]
            for col,(txt,cc) in enumerate(cells):
                item=QTableWidgetItem(txt); item.setForeground(QColor(cc))
                self.table.setItem(row,col,item)
            self.table.setRowHeight(row,44)
        self.count_lbl.setText(f"  {len(self._reports)} records")

    def _open(self,index):
        row=index.row()
        if row<len(self._reports):
            dlg=ReportDetailDialog(self._reports[row],self.current_user,self)
            dlg.exec(); self.refresh()

    def _new_report(self):
        dlg=NewReportDialog(self.current_user,self)
        dlg.exec(); self.refresh()


# ═══════════════════════════════════════════════════════════════════════════════
# REPORT DETAIL DIALOG
# ═══════════════════════════════════════════════════════════════════════════════

class ReportDetailDialog(QDialog):
    def __init__(self, report, current_user, parent=None):
        super().__init__(parent)
        self.report = report; self.current_user = current_user
        self.setWindowTitle(f"Report #{report['id']} – {report['road_name']}")
        self.setMinimumSize(640, 600)
        self.setStyleSheet(GLOBAL_SS)
        self._build()

    def _build(self):
        lay = QVBoxLayout(self); lay.setContentsMargins(28,22,28,22); lay.setSpacing(14)
        r = self.report
        sc = r["priority_score"]

        hdr = QHBoxLayout()
        hdr.addWidget(lbl(f"Report #{r['id']}",16,bold=True))
        hdr.addSpacing(8)
        hdr.addWidget(badge(r["status"],STATUS_COLORS.get(r["status"],C["muted"])))
        hdr.addWidget(badge(f"Sev {r['severity']}/10",SEV_COLORS[max(0,min(9,r['severity']-1))]))
        if r.get("ml_severity"):
            hdr.addWidget(badge(f"🤖 ML:{r['ml_severity']}",C["purple"]))
        hdr.addWidget(badge(f"Score:{sc:.1f}",default_engine.get_label_color(sc)))
        hdr.addStretch()
        lay.addLayout(hdr)

        grid = QGridLayout(); grid.setSpacing(10); grid.setColumnMinimumWidth(1,180)
        fields = [
            ("Road Name",r["road_name"]),("Location",r["location_text"]),
            ("Coordinates",f"{r['latitude']:.5f}, {r['longitude']:.5f}"),
            ("Priority Score",f"{sc:.2f} / 100  [{default_engine.get_label(sc)}]"),
            ("Citizen",r["citizen_name"]),("Email",r["email"]),
            ("Phone",r.get("phone_number") or "—"),("Created",r["created_at"][:16]),
        ]
        for i,(k,v) in enumerate(fields):
            col=(i%2)*2; rw=i//2
            grid.addWidget(lbl(k+":",11,color=C["muted"]),rw,col)
            grid.addWidget(lbl(v,12),rw,col+1)
        lay.addLayout(grid)

        if r.get("description"):
            lay.addWidget(sep())
            lay.addWidget(lbl("Description:",11,color=C["muted"]))
            d=QLabel(r["description"]); d.setWordWrap(True)
            d.setStyleSheet(f"color:{C['text']};background:{C['input']};border-radius:6px;padding:10px;")
            lay.addWidget(d)

        # Image thumbnails
        imgs = []
        if r.get("image_paths"):
            try: imgs = json.loads(r["image_paths"])
            except: pass
        if imgs:
            lay.addWidget(sep())
            lay.addWidget(lbl(f"📷 Photos ({len(imgs)}):",11,color=C["muted"]))
            thumb_row = QHBoxLayout(); thumb_row.setSpacing(8)
            for p in imgs[:6]:
                if os.path.exists(p):
                    pix=QPixmap(p).scaled(90,90,Qt.AspectRatioMode.KeepAspectRatio,
                                          Qt.TransformationMode.SmoothTransformation)
                    t=QLabel(); t.setPixmap(pix)
                    t.setStyleSheet("border-radius:6px;border:1px solid #2d3250;background:transparent;")
                    t.setCursor(Qt.CursorShape.PointingHandCursor)
                    t.mousePressEvent = lambda e,path=p: self._view_image(path)
                    thumb_row.addWidget(t)
                else:
                    t=QLabel("🖼"); t.setFixedSize(90,90)
                    t.setAlignment(Qt.AlignmentFlag.AlignCenter)
                    t.setStyleSheet(f"background:{C['input']};border-radius:6px;color:{C['muted']};font-size:24px;")
                    thumb_row.addWidget(t)
            thumb_row.addStretch()
            lay.addLayout(thumb_row)

        # Admin controls
        if self.current_user["role"]=="Admin":
            lay.addWidget(sep())
            ctrl = QHBoxLayout(); ctrl.setSpacing(10)
            ctrl.addWidget(lbl("Status:",11,color=C["muted"]))
            self.status_cb = QComboBox()
            # FIX #28: include all transitions so Unresolved can go back to Pending
            self.status_cb.addItems(["Pending","Scheduled","In Progress","Fixed","Unresolved"])
            self.status_cb.setCurrentText(r["status"])
            # Tooltip explaining transitions
            self.status_cb.setToolTip(
                "Pending → assign crew\n"
                "Scheduled / In Progress → being worked on\n"
                "Fixed → done\n"
                "Unresolved → set back to Pending to re-evaluate"
            )
            ctrl.addWidget(self.status_cb)
            u=btn("Update",C["blue"],small=True); u.clicked.connect(self._update_status); ctrl.addWidget(u)
            # FIX #19: Edit report button
            e=btn("✏ Edit",C["purple"],small=True); e.clicked.connect(self._edit_report); ctrl.addWidget(e)
            d=btn("🗑 Delete",C["red"],small=True); d.clicked.connect(self._delete); ctrl.addWidget(d)
            ctrl.addStretch(); lay.addLayout(ctrl)

            crews = db.get_all_crew()
            if crews and r["status"] not in ("Fixed",):
                lay.addWidget(lbl("Assign Crew:",11,color=C["muted"]))
                ar = QHBoxLayout(); ar.setSpacing(10)
                self.crew_cb = QComboBox()
                # Show workload count so admin picks least-busy crew
                workload = db.get_crew_workload()
                for cr in crews:
                    active_jobs = workload.get(cr["id"], 0)
                    self.crew_cb.addItem(f"{cr['name']}  ({active_jobs} active)", cr["id"])
                ar.addWidget(self.crew_cb)
                # FIX 4: No mandatory date — it's optional
                self.notes_in = QLineEdit()
                self.notes_in.setPlaceholderText("Assignment notes (optional)")
                ar.addWidget(self.notes_in)
                ab=btn("Assign →",C["amber"],small=True); ab.clicked.connect(self._assign); ar.addWidget(ab)
                ar.addStretch(); lay.addLayout(ar)
                self._crews = crews

        # FIX #15: Show crew proof images in report detail (admin view)
        assignments = db.get_assignments()
        my_assigns = [a for a in assignments if a["pothole_id"] == self.report["id"]]
        for a in my_assigns:
            proof_imgs = []
            if a.get("proof_images"):
                try: proof_imgs = json.loads(a["proof_images"])
                except: pass
            if proof_imgs or a.get("progress_note"):
                lay.addWidget(sep())
                crew_hdr = QHBoxLayout()
                crew_hdr.addWidget(lbl(f"🔧 Crew: {a['crew_name']}  [{a['repair_status']}]",
                                       11, bold=True, color=C["amber"]))
                if a.get("scheduled_date"):
                    crew_hdr.addWidget(lbl(f"  📅 {a['scheduled_date']}", 10, color=C["dim"]))
                crew_hdr.addStretch()
                lay.addLayout(crew_hdr)
                if a.get("progress_note"):
                    pn = QLabel(a["progress_note"]); pn.setWordWrap(True)
                    pn.setStyleSheet(f"color:{C['text']};background:{C['input']};"
                                     f"border-radius:6px;padding:8px;font-size:11px;")
                    lay.addWidget(pn)
                if proof_imgs:
                    lay.addWidget(lbl(f"📷 Proof Photos ({len(proof_imgs)}):", 10, color=C["muted"]))
                    pr = QHBoxLayout(); pr.setSpacing(6)
                    for p in proof_imgs[:6]:
                        if os.path.exists(p):
                            pix = QPixmap(p).scaled(80, 80, Qt.AspectRatioMode.KeepAspectRatio,
                                                    Qt.TransformationMode.SmoothTransformation)
                            t = QLabel(); t.setPixmap(pix)
                            t.setStyleSheet("border-radius:5px;border:1px solid #2d3250;background:transparent;")
                            t.setCursor(Qt.CursorShape.PointingHandCursor)
                            t.mousePressEvent = lambda e, path=p: self._view_image(path)
                            pr.addWidget(t)
                    pr.addStretch()
                    lay.addLayout(pr)

        # FIX #28: Show history timeline
        history = db.get_report_history(self.report["id"])
        if history:
            lay.addWidget(sep())
            lay.addWidget(lbl("📜 History:", 11, color=C["muted"]))
            for h in history[-5:]:  # show last 5 events
                ht = f"  {h['created_at'][:16]}  {h['actor_name'] or '?'}  →  {h['action']}"
                if h.get("new_value"): ht += f"  [{h['new_value']}]"
                lay.addWidget(lbl(ht, 10, color=C["dim"]))

        lay.addStretch()
        cb=btn("Close",C["input"]); cb.clicked.connect(self.accept); lay.addWidget(cb)

    def _view_image(self, path):
        dlg = QDialog(self); dlg.setWindowTitle("Photo"); dlg.setStyleSheet(GLOBAL_SS)
        l = QVBoxLayout(dlg); l.setContentsMargins(10,10,10,10)
        pix = QPixmap(path).scaled(800,600,Qt.AspectRatioMode.KeepAspectRatio,
                                   Qt.TransformationMode.SmoothTransformation)
        img = QLabel(); img.setPixmap(pix); l.addWidget(img)
        dlg.exec()

    def _update_status(self):
        db.update_report_status(
            self.report["id"], self.status_cb.currentText(),
            actor_id=self.current_user["id"], actor_name=self.current_user["name"]
        )
        QMessageBox.information(self,"✅","Status updated."); self.accept()
        for w in QApplication.topLevelWidgets():
            if isinstance(w, MainWindow): w.refresh_all()

    def _edit_report(self):
        dlg = EditReportDialog(self.report, self.current_user, self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self.accept()
            for w in QApplication.topLevelWidgets():
                if isinstance(w, MainWindow): w.refresh_all()

    def _delete(self):
        if QMessageBox.question(self,"Confirm","Delete this report?") == QMessageBox.StandardButton.Yes:
            db.delete_report(self.report["id"]); self.accept()

    def _assign(self):
        cid   = self.crew_cb.currentData()
        notes = self.notes_in.text().strip()
        try:
            db.create_assignment(
                self.report["id"], cid,
                scheduled_date=None,   # FIX 4: date not required
                notes=notes or None,
                actor_id=self.current_user["id"],
                actor_name=self.current_user["name"]
            )
            QMessageBox.information(self,"✅","Crew assigned successfully.")
            self.accept()
            for w in QApplication.topLevelWidgets():
                if isinstance(w, MainWindow): w.refresh_all()
        except ValueError as e:
            QMessageBox.warning(self,"⚠ Already Assigned", str(e))


# ═══════════════════════════════════════════════════════════════════════════════
# PRIORITY VIEW
# ═══════════════════════════════════════════════════════════════════════════════

class PriorityView(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._build(); self.refresh()

    def _build(self):
        lay = QVBoxLayout(self); lay.setContentsMargins(32,24,32,24); lay.setSpacing(18)
        hdr = QHBoxLayout()
        hdr.addWidget(lbl("🔥  Priority Queue",18,bold=True))
        hdr.addSpacing(8)
        hdr.addWidget(lbl("Sorted highest urgency first",11,color=C["muted"]))
        hdr.addStretch()
        rb=btn("♻ Recalculate",C["purple"],small=True); rb.clicked.connect(self._recalc); hdr.addWidget(rb)
        rf=btn("🔄",C["input"],small=True); rf.clicked.connect(self.refresh); hdr.addWidget(rf)
        lay.addLayout(hdr)
        leg=QHBoxLayout()
        for t,c in [("Critical ≥75",C["red"]),("High ≥50","#f97316"),("Medium ≥25",C["amber"]),("Low <25",C["green"])]:
            leg.addWidget(badge(t,c)); leg.addSpacing(4)
        leg.addStretch(); lay.addLayout(leg)
        self.table=QTableWidget()
        self.table.setColumnCount(7)
        self.table.setHorizontalHeaderLabels(["Rank","Road Name","Severity","ML Sev","Traffic","Priority Score","Status"])
        self.table.setAlternatingRowColors(True)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.verticalHeader().setVisible(False); self.table.setShowGrid(False)
        self.table.setSortingEnabled(True)
        lay.addWidget(self.table)

    def refresh(self):
        reports=db.get_reports(sort_by="priority_score",order="DESC")
        tl={t["road_name"]:t["avg_daily_traffic"] for t in db.get_all_traffic()}
        self.table.setRowCount(len(reports))
        for rank,r in enumerate(reports,1):
            sc=r["priority_score"]; ml=str(r["ml_severity"]) if r.get("ml_severity") else "–"
            cells=[
                (f"  #{rank}",C["muted"]),(r["road_name"],C["text"]),
                (f"  {r['severity']}/10",SEV_COLORS[max(0,min(9,r['severity']-1))]),
                (f"  {ml}",C["purple"] if ml!="–" else C["dim"]),
                (f"  {tl.get(r['road_name'],5000):,}",C["cyan"]),
                (f"  {sc:.2f}",default_engine.get_label_color(sc)),
                (f"  {r['status']}",STATUS_COLORS.get(r["status"],C["muted"])),
            ]
            for col,(txt,cc) in enumerate(cells):
                item=QTableWidgetItem(txt); item.setForeground(QColor(cc))
                self.table.setItem(rank-1,col,item)
            self.table.setRowHeight(rank-1,44)

    def _recalc(self):
        n=db.recalculate_all_scores()
        QMessageBox.information(self,"Done",f"Scores recalculated for {n} reports.")
        self.refresh()


# ═══════════════════════════════════════════════════════════════════════════════
# REPAIR CREW – ASSIGNMENTS + PROGRESS UPDATE
# ═══════════════════════════════════════════════════════════════════════════════

class CrewProgressDialog(QDialog):
    """Update assignment status. Proof photos only for Repair Crew, not Admin."""
    def __init__(self, assignment, current_user=None, parent=None):
        super().__init__(parent)
        self.assignment   = assignment
        self.current_user = current_user or {"role": "Repair Crew"}
        self.proof_paths  = []
        self.setWindowTitle(f"Update Assignment #{assignment['id']}")
        self.setMinimumSize(520, 480)
        self.setStyleSheet(GLOBAL_SS)
        self._build()

    def _build(self):
        lay = QVBoxLayout(self); lay.setContentsMargins(24,20,24,20); lay.setSpacing(14)
        a = self.assignment
        lay.addWidget(lbl(f"🔧  {a['road_name']}",15,bold=True))
        lay.addWidget(lbl(f"Severity {a['severity']}/10  |  Priority {a['priority_score']:.1f}  |  {a['location_text']}",
                          11,color=C["muted"]))
        lay.addWidget(sep())

        # FIX #18: Show citizen description and photos for crew reference
        if a.get("description"):
            desc_lbl = QLabel(f"📝 {a['description']}"); desc_lbl.setWordWrap(True)
            desc_lbl.setStyleSheet(f"color:{C['text']};background:{C['input']};"
                                   f"border-radius:6px;padding:8px;font-size:11px;")
            lay.addWidget(desc_lbl)
        cit_imgs = []
        if a.get("image_paths"):
            try: cit_imgs = json.loads(a["image_paths"])
            except: pass
        if cit_imgs:
            lay.addWidget(lbl(f"📷 Citizen Photos ({len(cit_imgs)}):", 10, color=C["muted"]))
            cit_row = QHBoxLayout(); cit_row.setSpacing(6)
            for p in cit_imgs[:4]:
                if os.path.exists(p):
                    pix = QPixmap(p).scaled(68, 68, Qt.AspectRatioMode.KeepAspectRatio,
                                            Qt.TransformationMode.SmoothTransformation)
                    t = QLabel(); t.setPixmap(pix)
                    t.setStyleSheet("border-radius:5px;border:1px solid #2d3250;background:transparent;")
                    cit_row.addWidget(t)
            cit_row.addStretch()
            lay.addLayout(cit_row)
        lay.addWidget(sep())

        # Status
        sf = QGroupBox("Update Status"); sl = QFormLayout(sf); sl.setSpacing(10)
        self.status_cb = QComboBox()
        self.status_cb.addItems(["Assigned","Started","Completed","Cancelled"])
        self.status_cb.setCurrentText(a["repair_status"])
        sl.addRow("New Status", self.status_cb)
        self.note_in = QTextEdit()
        self.note_in.setPlaceholderText("Progress notes – describe what was done…")
        self.note_in.setFixedHeight(90)
        if a.get("progress_note"): self.note_in.setText(a["progress_note"])
        sl.addRow("Progress Note", self.note_in)
        lay.addWidget(sf)

        # Proof photos — only shown for Repair Crew, not Admin
        is_crew = self.current_user.get("role") == "Repair Crew"
        pf = QGroupBox("Proof Photographs"); pl = QVBoxLayout(pf); pl.setSpacing(10)

        if is_crew:
            pr = QHBoxLayout()
            add_p = btn("📷 Add Proof Photos",C["blue"],small=True)
            add_p.clicked.connect(self._add_proof)
            pr.addWidget(add_p); pr.addStretch(); pl.addLayout(pr)
            self.proof_list = QListWidget(); self.proof_list.setFixedHeight(80)
            pl.addWidget(self.proof_list)
            self.proof_thumb_row = QHBoxLayout(); self.proof_thumb_row.setSpacing(6)
            pt_frame = QFrame(); pt_frame.setLayout(self.proof_thumb_row)
            pl.addWidget(pt_frame)
        else:
            # Admin: show existing proof images read-only
            self.proof_list = QListWidget(); self.proof_list.setFixedHeight(80)
            self.proof_thumb_row = QHBoxLayout()
            pl.addWidget(lbl("  Proof photos uploaded by repair crew:", 11, color=C["muted"]))
            pl.addWidget(self.proof_list)
            pt_frame = QFrame(); pt_frame.setLayout(self.proof_thumb_row)
            pl.addWidget(pt_frame)

        # Load existing proof images (shown for both roles)
        existing = []
        if a.get("proof_images"):
            try: existing = json.loads(a["proof_images"])
            except: pass
        for p in existing:
            self.proof_list.addItem(QListWidgetItem(f"📷 {Path(p).name}"))
            self._add_thumb_to(self.proof_thumb_row, p)

        if not existing and not is_crew:
            pl.addWidget(lbl("  No proof photos uploaded yet.", 11, color=C["dim"]))

        lay.addWidget(pf)

        # Location info
        map_lbl = lbl(f"📍 Coords: {a.get('latitude',0):.5f}, {a.get('longitude',0):.5f}",
                      11,color=C["cyan"])
        osm = btn("🌐 Open on Map",C["input"],small=True)
        lat=a.get("latitude",12.87); lng=a.get("longitude",74.84)
        osm.clicked.connect(lambda: __import__('webbrowser').open(
            f"https://www.openstreetmap.org/?mlat={lat}&mlon={lng}#map=17/{lat}/{lng}"))
        ml = QHBoxLayout(); ml.addWidget(map_lbl); ml.addWidget(osm); ml.addStretch()
        lay.addLayout(ml)

        lay.addStretch()
        br = QHBoxLayout(); br.setSpacing(10)
        sv = btn("💾 Save Update",C["green"]); sv.clicked.connect(self._save); br.addWidget(sv)
        cc = btn("Cancel",C["input"]); cc.clicked.connect(self.reject); br.addWidget(cc)
        lay.addLayout(br)

    def _add_proof(self):
        if self.current_user.get("role") != "Repair Crew":
            return   # Admin cannot upload proof
        files,_=QFileDialog.getOpenFileNames(self,"Proof Photos","","Images (*.jpg *.jpeg *.png *.bmp)")
        for f in files[:5]:
            if f not in self.proof_paths:
                self.proof_paths.append(f)
                self.proof_list.addItem(QListWidgetItem(f"📷 {Path(f).name}"))
                self._add_thumb_to(self.proof_thumb_row, f)

    def _add_thumb_to(self, row, path):
        try:
            pix=QPixmap(path).scaled(68,68,Qt.AspectRatioMode.KeepAspectRatio,
                                     Qt.TransformationMode.SmoothTransformation)
            t=QLabel(); t.setPixmap(pix)
            t.setStyleSheet("border-radius:5px;border:1px solid #2d3250;background:transparent;")
            row.addWidget(t)
        except: pass

    def _find_main_window(self):
        """Walk up parent chain to find MainWindow instance."""
        w = self.parent()
        while w is not None:
            if isinstance(w, MainWindow):
                return w
            w = w.parent() if hasattr(w, 'parent') else None
        # Fallback: search top-level widgets
        for widget in QApplication.topLevelWidgets():
            if isinstance(widget, MainWindow):
                return widget
        return None

    def _save(self):
        new_status = self.status_cb.currentText()
        note = self.note_in.toPlainText().strip()
        stored = [db.save_image(p,"proof") for p in self.proof_paths]
        stored = [s for s in stored if s]

        # Merge with existing proof images
        existing = []
        if self.assignment.get("proof_images"):
            try: existing = json.loads(self.assignment["proof_images"])
            except: pass
        all_proof = existing + stored

        db.update_assignment_status(
            self.assignment["id"], new_status,
            progress_note=note or None,
            proof_images=all_proof if all_proof else None
        )
        QMessageBox.information(self,"✅ Saved","Assignment updated successfully.")
        self.accept()
        # Propagate change to all open views (Reports, Dashboard, Priority)
        main_win = self._find_main_window()
        if main_win:
            main_win.refresh_all()


class AssignmentsView(QWidget):
    def __init__(self, current_user, parent=None):
        super().__init__(parent)
        self.current_user = current_user
        self._assignments = []
        self._build(); self.refresh()

    def _build(self):
        lay = QVBoxLayout(self); lay.setContentsMargins(32,24,32,24); lay.setSpacing(18)
        hdr = QHBoxLayout()
        hdr.addWidget(lbl("🔧  Repair Assignments",18,bold=True)); hdr.addStretch()
        r=btn("🔄",C["input"],small=True); r.clicked.connect(self.refresh); hdr.addWidget(r)
        lay.addLayout(hdr)

        filt = QHBoxLayout(); filt.setSpacing(12)
        filt.addWidget(lbl("Status:",11,color=C["muted"]))
        self.status_cb = QComboBox()
        self.status_cb.addItems(["All","Assigned","Started","Completed","Cancelled"])
        self.status_cb.currentIndexChanged.connect(self.refresh); filt.addWidget(self.status_cb)
        filt.addStretch(); lay.addLayout(filt)

        self.table = QTableWidget()
        self.table.setColumnCount(8)
        self.table.setHorizontalHeaderLabels(
            ["ID","Road","Severity","Priority","Crew","Scheduled","Status","Proof"])
        self.table.setAlternatingRowColors(True)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.verticalHeader().setVisible(False); self.table.setShowGrid(False)
        self.table.setSortingEnabled(True)
        self.table.doubleClicked.connect(self._open_progress)
        lay.addWidget(self.table)
        lay.addWidget(lbl("Double-click to update progress / upload proof photos",10,color=C["dim"]))

        # Crew stats (only for crew member)
        if self.current_user["role"]=="Repair Crew":
            stats_card = card(); sl = QHBoxLayout(stats_card); sl.setContentsMargins(16,12,16,12)
            self._total_lbl  = lbl("Total: –",12)
            self._done_lbl   = lbl("Completed: –",12,color=C["green"])
            self._active_lbl = lbl("Active: –",12,color=C["amber"])
            for w in [self._total_lbl,self._done_lbl,self._active_lbl]:
                sl.addWidget(w); sl.addSpacing(24)
            sl.addStretch()
            lay.addWidget(stats_card)

    def refresh(self):
        status = self.status_cb.currentText(); status = None if status=="All" else status
        cid = None if self.current_user["role"]=="Admin" else self.current_user["id"]
        self._assignments = db.get_assignments(crew_id=cid, status=status)
        self.table.setRowCount(len(self._assignments))
        st_cols={"Assigned":C["amber"],"Started":C["blue"],"Completed":C["green"],"Cancelled":C["red"]}
        for row,a in enumerate(self._assignments):
            sc=a["priority_score"]
            proof_count=0
            if a.get("proof_images"):
                try: proof_count=len(json.loads(a["proof_images"]))
                except: pass
            cells=[
                (f"#{a['id']}",C["muted"]),(a["road_name"],C["text"]),
                (f"  {a['severity']}/10",SEV_COLORS[max(0,min(9,a['severity']-1))]),
                (f"  {sc:.1f}",default_engine.get_label_color(sc)),
                (a["crew_name"],C["text"]),
                (a.get("scheduled_date") or "—",C["muted"]),
                (f"  {a['repair_status']}",st_cols.get(a["repair_status"],C["muted"])),
                (f"  📷 {proof_count}" if proof_count else "  –",C["cyan"] if proof_count else C["dim"]),
            ]
            for col,(txt,cc) in enumerate(cells):
                item=QTableWidgetItem(txt); item.setForeground(QColor(cc))
                self.table.setItem(row,col,item)
            self.table.setRowHeight(row,44)

        if self.current_user["role"]=="Repair Crew" and hasattr(self,"_total_lbl"):
            all_mine = db.get_assignments(crew_id=self.current_user["id"])
            total    = len(all_mine)
            done     = sum(1 for a in all_mine if a["repair_status"]=="Completed")
            active   = sum(1 for a in all_mine if a["repair_status"] in ("Assigned","Started"))
            self._total_lbl.setText(f"Total Assignments: {total}")
            self._done_lbl.setText(f"  ✅ Completed: {done}")
            self._active_lbl.setText(f"  🔧 Active: {active}")

    def _open_progress(self, index):
        row = index.row()
        if row < len(self._assignments):
            dlg = CrewProgressDialog(self._assignments[row], self.current_user, self)
            dlg.exec(); self.refresh()


# ═══════════════════════════════════════════════════════════════════════════════
# ADMIN – USERS MANAGEMENT
# ═══════════════════════════════════════════════════════════════════════════════

class UsersView(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._users = []
        self._build(); self.refresh()

    def _build(self):
        lay = QVBoxLayout(self); lay.setContentsMargins(32,24,32,24); lay.setSpacing(18)
        hdr = QHBoxLayout()
        hdr.addWidget(lbl("👥  User Management",18,bold=True)); hdr.addStretch()
        add=btn("➕ Add Repair Crew",C["green"]); add.clicked.connect(self._add_crew); hdr.addWidget(add)
        r=btn("🔄",C["input"],small=True); r.clicked.connect(self.refresh); hdr.addWidget(r)
        lay.addLayout(hdr)
        lay.addWidget(lbl("Admins can add Repair Crew members. Citizen accounts are self-registered.",
                          11,color=C["muted"]))

        self.table = QTableWidget()
        self.table.setColumnCount(6)
        self.table.setHorizontalHeaderLabels(["ID","Name","Email","Role","Status","Actions"])
        self.table.setAlternatingRowColors(True)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(0,QHeaderView.ResizeMode.ResizeToContents)
        self.table.verticalHeader().setVisible(False); self.table.setShowGrid(False)
        self.table.setSortingEnabled(True)
        lay.addWidget(self.table)
        lay.addWidget(lbl("Deactivated users cannot log in. Reports are preserved.",10,color=C["dim"]))

    def refresh(self):
        self._users = db.get_all_users()
        self.table.setSortingEnabled(False)
        self.table.setRowCount(len(self._users))
        role_cols = {"Admin": C["red"], "Repair Crew": C["amber"], "Citizen": C["green"]}
        for row, u in enumerate(self._users):
            active = u.get("is_active", 1)
            cells = [
                (str(u["id"]),   C["muted"]),
                (u["name"],      C["text"]  if active else C["dim"]),
                (u["email"],     C["cyan"]  if active else C["dim"]),
                (u["role"],      role_cols.get(u["role"], C["muted"])),
                ("● Active" if active else "⛔ Deactivated",
                 C["green"]  if active else C["red"]),
            ]
            for col, (txt, cc) in enumerate(cells):
                item = QTableWidgetItem(txt)
                item.setForeground(QColor(cc))
                self.table.setItem(row, col, item)

            # Action column — use QPushButton via setCellWidget
            # Re-create widget each refresh so stale connections don't pile up
            action_w = QWidget()
            action_w.setStyleSheet("background: transparent;")
            al = QHBoxLayout(action_w)
            al.setContentsMargins(6, 4, 6, 4)
            al.setSpacing(8)
            if u["role"] != "Admin":
                if active:
                    ab = QPushButton("⛔  Deactivate")
                    ab.setStyleSheet(
                        f"QPushButton{{background:{C['red']}22;color:{C['red']};"
                        f"border:1px solid {C['red']}55;border-radius:5px;"
                        f"padding:4px 10px;font-weight:600;font-size:11px;}}"
                        f"QPushButton:hover{{background:{C['red']}44;}}"
                    )
                    ab.setCursor(Qt.CursorShape.PointingHandCursor)
                    ab.clicked.connect(lambda _, uid=u["id"]: self._deactivate(uid))
                    al.addWidget(ab)
                else:
                    rb = QPushButton("✅  Reactivate")
                    rb.setStyleSheet(
                        f"QPushButton{{background:{C['green']}22;color:{C['green']};"
                        f"border:1px solid {C['green']}55;border-radius:5px;"
                        f"padding:4px 10px;font-weight:600;font-size:11px;}}"
                        f"QPushButton:hover{{background:{C['green']}44;}}"
                    )
                    rb.setCursor(Qt.CursorShape.PointingHandCursor)
                    rb.clicked.connect(lambda _, uid=u["id"]: self._reactivate(uid))
                    al.addWidget(rb)
            else:
                al.addWidget(lbl("  —", 11, color=C["dim"]))
            al.addStretch()
            self.table.setCellWidget(row, 5, action_w)
            self.table.setRowHeight(row, 46)
        self.table.setSortingEnabled(True)

    def _add_crew(self):
        dlg = RegisterDialog(self, crew_only=True)
        if dlg.exec() == QDialog.DialogCode.Accepted: self.refresh()

    def _deactivate(self, uid):
        if QMessageBox.question(self,"Confirm",
            "Deactivate this user?\nThey will not be able to log in.") == QMessageBox.StandardButton.Yes:
            db.deactivate_user(uid)
            QMessageBox.information(self,"Done","User deactivated.")
            self.refresh()

    def _reactivate(self, uid):
        db.reactivate_user(uid); self.refresh()


# ═══════════════════════════════════════════════════════════════════════════════
# PROFILE, EXPORT
# ═══════════════════════════════════════════════════════════════════════════════

class ProfileView(QWidget):
    def __init__(self, current_user, parent=None):
        super().__init__(parent)
        self.current_user = current_user
        self._build()

    def _build(self):
        lay = QVBoxLayout(self); lay.setContentsMargins(32,24,32,24); lay.setSpacing(18)
        lay.addWidget(lbl("👤  My Profile",18,bold=True))
        frm = card(); frm.setMaximumWidth(520)
        fl = QFormLayout(frm); fl.setContentsMargins(28,22,28,22); fl.setSpacing(14)
        rc = {"Admin":C["red"],"Repair Crew":C["amber"],"Citizen":C["green"]}
        fl.addRow(lbl("Name",11,color=C["muted"]),    lbl(self.current_user["name"],13))
        fl.addRow(lbl("Email",11,color=C["muted"]),   lbl(self.current_user["email"],13))
        fl.addRow(lbl("Role",11,color=C["muted"]),    badge(self.current_user["role"],rc.get(self.current_user["role"],C["blue"])))
        fl.addRow(sep())
        fl.addRow(lbl("New Name:",11,color=C["muted"]))
        self.name_in = QLineEdit(self.current_user["name"]); fl.addRow(self.name_in)
        fl.addRow(lbl("New Password:",11,color=C["muted"]))
        self.pass_in = QLineEdit(); self.pass_in.setEchoMode(QLineEdit.EchoMode.Password)
        self.pass_in.setPlaceholderText("Leave blank to keep current"); fl.addRow(self.pass_in)
        sv=btn("💾 Save Changes",C["blue"]); sv.clicked.connect(self._save); fl.addRow(sv)
        lay.addWidget(frm); lay.addStretch()

    def _save(self):
        db.update_user(self.current_user["id"],
                       name=self.name_in.text().strip() or None,
                       password=self.pass_in.text() or None)
        QMessageBox.information(self,"✅","Profile updated.")


class ExportView(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._build()

    def _build(self):
        lay = QVBoxLayout(self); lay.setContentsMargins(32,24,32,24); lay.setSpacing(18)
        lay.addWidget(lbl("📤  Export Data",18,bold=True))
        for title,desc,action in [
            ("Export Reports (CSV)","All pothole reports with priority & ML severity",self._exp_reports),
            ("Export Assignments (CSV)","Repair assignments with proof photo counts",self._exp_assignments),
        ]:
            rc = card(); rl = QHBoxLayout(rc); rl.setContentsMargins(20,16,20,16)
            tx = QVBoxLayout(); tx.addWidget(lbl(title,13,bold=True)); tx.addWidget(lbl(desc,11,color=C["muted"]))
            rl.addLayout(tx); rl.addStretch()
            eb=btn("Export →",C["blue"],small=True); eb.clicked.connect(action); rl.addWidget(eb)
            lay.addWidget(rc)
        lay.addStretch()

    def _exp_reports(self):
        import csv
        reports=db.get_reports(limit=9999)
        path,_=QFileDialog.getSaveFileName(self,"Save","pothole_reports.csv","CSV (*.csv)")
        if not path: return
        with open(path,"w",newline="",encoding="utf-8") as f:
            w=csv.writer(f)
            w.writerow(["ID","Road","Severity","ML Severity","Priority Score","Status",
                        "Location","Lat","Lng","Citizen","Email","Photos","Created"])
            for r in reports:
                imgs=len(json.loads(r["image_paths"])) if r.get("image_paths") else 0
                w.writerow([r["id"],r["road_name"],r["severity"],r.get("ml_severity",""),
                            r["priority_score"],r["status"],r["location_text"],
                            r["latitude"],r["longitude"],r["citizen_name"],r["email"],imgs,r["created_at"][:16]])
        QMessageBox.information(self,"✅ Exported",f"Saved to:\n{path}")

    def _exp_assignments(self):
        import csv
        asgn=db.get_assignments()
        path,_=QFileDialog.getSaveFileName(self,"Save","assignments.csv","CSV (*.csv)")
        if not path: return
        with open(path,"w",newline="",encoding="utf-8") as f:
            w=csv.writer(f)
            w.writerow(["ID","Road","Severity","Priority","Crew","Scheduled","Status","Proof Photos","Notes","Completed"])
            for a in asgn:
                pc=0
                if a.get("proof_images"):
                    try: pc=len(json.loads(a["proof_images"]))
                    except: pass
                w.writerow([a["id"],a["road_name"],a["severity"],a["priority_score"],
                            a["crew_name"],a.get("scheduled_date",""),a["repair_status"],
                            pc,a.get("progress_note",""),a.get("completed_at","")])
        QMessageBox.information(self,"✅ Exported",f"Saved to:\n{path}")


# ═══════════════════════════════════════════════════════════════════════════════
# MAIN WINDOW
# ═══════════════════════════════════════════════════════════════════════════════

class MainWindow(QMainWindow):
    logout_requested = pyqtSignal()   # emitted when user clicks Logout

    def __init__(self, current_user):
        super().__init__()
        self.current_user = current_user
        self._logout_requested = False
        self.setWindowTitle(f"PotholeFix – {current_user['name']} ({current_user['role']})")
        self.setMinimumSize(1280,800)
        self.setStyleSheet(GLOBAL_SS)
        self._build()
        self._nav_to(0)
        self._start_auto_refresh()

    def _build(self):
        central = QWidget(); self.setCentralWidget(central)
        main_lay = QHBoxLayout(central); main_lay.setContentsMargins(0,0,0,0); main_lay.setSpacing(0)

        # ── Sidebar ────────────────────────────────────────────────────────────
        sidebar = QFrame(); sidebar.setFixedWidth(240)
        sidebar.setStyleSheet(f"QFrame{{background:{C['sidebar']};border-right:1px solid {C['border']};}}")
        sb = QVBoxLayout(sidebar); sb.setContentsMargins(0,0,0,0); sb.setSpacing(0)

        logo = QFrame(); logo.setFixedHeight(80)
        logo.setStyleSheet(f"QFrame{{background:{C['sidebar']};border-bottom:1px solid {C['border']};}}")
        ll = QVBoxLayout(logo); ll.setContentsMargins(20,14,20,14)
        ll.addWidget(lbl("🚧  PotholeFix",16,bold=True))
        ll.addWidget(lbl("Infrastructure System",9,color=C["dim"]))
        sb.addWidget(logo)

        is_admin = self.current_user["role"]=="Admin"
        is_crew  = self.current_user["role"]=="Repair Crew"

        self._nav_btns = []; self._stack = QStackedWidget()
        pages = [
            ("📊","Dashboard",   lambda: DashboardView(self),                          True),
            ("📋","Reports",     lambda: ReportsView(self.current_user,self),           True),
            ("🔥","Priority",    lambda: PriorityView(self),                            True),
            ("🔧","Assignments", lambda: AssignmentsView(self.current_user,self),       True),
            ("👥","Users",       lambda: UsersView(self),                               is_admin),
            ("📤","Export",      lambda: ExportView(self),                              is_admin),
            ("👤","Profile",     lambda: ProfileView(self.current_user,self),           True),
        ]

        idx=0
        for icon,name,factory,visible in pages:
            if not visible: continue
            b=SidebarButton(icon,name)
            b.clicked.connect(lambda _,i=idx: self._nav_to(i))
            sb.addWidget(b); self._nav_btns.append(b)
            self._stack.addWidget(factory()); idx+=1

        sb.addStretch()

        # User info bottom
        uf = QFrame(); uf.setFixedHeight(72)
        uf.setStyleSheet(f"QFrame{{background:{C['sidebar']};border-top:1px solid {C['border']};}}")
        ul=QVBoxLayout(uf); ul.setContentsMargins(16,12,16,12); ul.setSpacing(2)
        ul.addWidget(lbl(self.current_user["name"],12,bold=True))
        rc={"Admin":C["red"],"Repair Crew":C["amber"],"Citizen":C["green"]}
        ul.addWidget(lbl(self.current_user["role"],10,color=rc.get(self.current_user["role"],C["blue"])))
        sb.addWidget(uf)

        lo=QPushButton("⏻  Logout"); lo.setFixedHeight(38)
        lo.setCursor(Qt.CursorShape.PointingHandCursor)
        lo.setStyleSheet(f"QPushButton{{background:{C['red']}22;color:{C['red']};border:none;font-weight:600;font-size:12px;}}"
                         f"QPushButton:hover{{background:{C['red']}44;}}")
        lo.clicked.connect(self._logout); sb.addWidget(lo)
        main_lay.addWidget(sidebar)

        # Content
        content=QFrame(); content.setStyleSheet(f"QFrame{{background:{C['bg']};}}")
        cl=QVBoxLayout(content); cl.setContentsMargins(0,0,0,0); cl.addWidget(self._stack)
        main_lay.addWidget(content,1)

        status=QStatusBar()
        status.setStyleSheet(f"background:{C['sidebar']};color:{C['muted']};font-size:11px;")
        status.showMessage(f"Logged in as {self.current_user['name']}  ·  {self.current_user['role']}")
        self.setStatusBar(status)



    def refresh_all(self):
        """
        FIX #16: Only refresh the currently visible page immediately.
        Mark all other pages as stale so they refresh when next navigated to.
        """
        current = self._stack.currentWidget()
        if current and hasattr(current, "refresh"):
            try:
                current.refresh()
            except Exception:
                pass
        # Mark all other pages stale
        for i in range(self._stack.count()):
            w = self._stack.widget(i)
            if w is not current:
                w._needs_refresh = True

    def _nav_to(self, index):
        self._stack.setCurrentIndex(index)
        for i, b in enumerate(self._nav_btns): b.setActive(i == index)
        w = self._stack.currentWidget()
        # Refresh if stale or on explicit navigation
        if hasattr(w, "refresh") and getattr(w, "_needs_refresh", True):
            try:
                w.refresh()
                w._needs_refresh = False
            except Exception:
                pass
        return  # replaced below

    def _start_auto_refresh(self):
        """Auto-refresh current view every 30 seconds."""
        self._refresh_timer = QTimer(self)
        self._refresh_timer.setInterval(30000)
        self._refresh_timer.timeout.connect(self.refresh_all)
        self._refresh_timer.start()
        # FIX #27: Update status bar with last-refresh time
        self._status_timer = QTimer(self)
        self._status_timer.setInterval(1000)
        self._status_timer.timeout.connect(self._update_status_bar)
        self._status_timer.start()
        self._last_refresh = datetime.now()

    def _update_status_bar(self):
        secs = int((datetime.now() - self._last_refresh).total_seconds())
        role = self.current_user["role"]
        name = self.current_user["name"]
        self.statusBar().showMessage(
            f"  {name}  [{role}]   ·   Last refreshed: {secs}s ago"
        )

    def _logout(self):
        if QMessageBox.question(self,"Logout","Log out of PotholeFix?") == QMessageBox.StandardButton.Yes:
            self._logout_requested = True
            self._refresh_timer.stop()
            self.logout_requested.emit()   # AppController shows login
            self.close()


# ═══════════════════════════════════════════════════════════════════════════════
# APP CONTROLLER – manages login ↔ main window transitions without nesting
#                  event loops or touching deleted C++ objects.
# ═══════════════════════════════════════════════════════════════════════════════

class AppController(QObject):
    """
    Owns the login window and main window lifecycle.
    Uses signals so transitions happen inside the running event loop,
    never nested (which caused the 'event loop already running' crash).
    """
    def __init__(self, app):
        super().__init__()
        self.app = app
        self._main_win = None
        self._login_win = None

    def start(self):
        self._show_login()

    def _show_login(self):
        # Clean up any existing login window
        if self._login_win is not None:
            try:
                self._login_win.close()
            except RuntimeError:
                pass
            self._login_win = None

        login = LoginWindow()
        login.logged_in.connect(self._on_logged_in)
        # When login dialog is rejected (X button / no login) → quit app
        login.rejected.connect(self._on_login_rejected)
        self._login_win = login
        login.show()   # Non-blocking show, NOT exec()

    def _on_login_rejected(self):
        # Quit only if user dismissed login AND no main window is showing
        # Small delay lets _on_logged_in run first if sign-in was clicked
        QTimer.singleShot(200, self._maybe_quit)

    def _maybe_quit(self):
        if self._main_win is None and (self._login_win is None or not self._login_win.isVisible()):
            self.app.quit()

    def _on_logged_in(self, user):
        # Disconnect rejected so closing login after login doesn't trigger quit
        if self._login_win is not None:
            try:
                self._login_win.rejected.disconnect(self._on_login_rejected)
            except (RuntimeError, TypeError):
                pass
            try:
                self._login_win.close()
            except RuntimeError:
                pass
            self._login_win = None

        # Close old main window safely
        if self._main_win is not None:
            try:
                self._main_win._logout_requested = False  # prevent recursive trigger
                self._main_win.close()
            except RuntimeError:
                pass
            self._main_win = None

        # Create and show new main window
        win = MainWindow(user)
        win.logout_requested.connect(self._show_login)
        self._main_win = win
        win.show()


def _apply_dark_palette(app):
    app.setStyle("Fusion")
    palette = QPalette()
    palette.setColor(QPalette.ColorRole.Window,          QColor("#0f1117"))
    palette.setColor(QPalette.ColorRole.WindowText,      QColor("#f1f5f9"))
    palette.setColor(QPalette.ColorRole.Base,            QColor("#1a1d27"))
    palette.setColor(QPalette.ColorRole.AlternateBase,   QColor("#22263a"))
    palette.setColor(QPalette.ColorRole.Text,            QColor("#f1f5f9"))
    palette.setColor(QPalette.ColorRole.Button,          QColor("#1a1d27"))
    palette.setColor(QPalette.ColorRole.ButtonText,      QColor("#f1f5f9"))
    palette.setColor(QPalette.ColorRole.Highlight,       QColor("#3b82f6"))
    palette.setColor(QPalette.ColorRole.HighlightedText, QColor("#ffffff"))
    app.setPalette(palette)


def main():
    app = QApplication.instance() or QApplication(sys.argv)
    # Prevent Qt from quitting when the last window (login dialog) closes.
    # We manage quit manually via AppController.
    app.setQuitOnLastWindowClosed(False)
    _apply_dark_palette(app)
    db.init_db()
    db.seed_sample_data()

    controller = AppController(app)
    controller.start()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
