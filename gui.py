import os
os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"
os.environ["OMP_NUM_THREADS"] = "1"
import sys
import threading
import time
import math
import random
import webbrowser
import psutil 
from PyQt5 import QtCore, QtGui, QtWidgets
from PyQt5.QtCore import Qt, QTimer, pyqtSlot, pyqtSignal, QRectF, QPointF
from main import CypherCore, save_env_keys, get_app_dir, get_env_path

# =============================================================================
# COLOR PALETTE (Cyberpunk / F.R.I.D.A.Y. Sci-Fi HUD)
# =============================================================================
COLOR_BG = "#04070c"               # Deep Space Obsidian
COLOR_PANEL_BG = "rgba(6, 14, 24, 0.78)"  # Frosted Glass Tint
COLOR_ACCENT = "#00d9f6"           # High-Volt Cyan
COLOR_ACCENT_DIM = "rgba(0, 217, 246, 0.25)"
COLOR_SEC = "#005f7f"              # Subdued Cyan
COLOR_BORDER = "rgba(0, 217, 246, 0.35)"
COLOR_TEXT = "#ffffff"
COLOR_TEXT_DIM = "rgba(0, 217, 246, 0.85)"
COLOR_WARN = "#ff3344"             # Neon Red (Shutdown / Alarm)

# Contextual State Colors
COLOR_IDLE = "#00d9f6"             # Cyan Neon
COLOR_LISTEN = "#00ff77"           # Matrix Emerald Green
COLOR_PROCESS = "#3a86ff"          # High-Energy Plasma Blue
COLOR_SPEAK = "#ff007f"            # Hot Neon Magenta / Vocalizing

# =============================================================================
# STANDALONE ASSET PATH & FONT LOADER
# =============================================================================
def get_resource_path(relative_path):
    """Get absolute path to resource, works for dev and for PyInstaller bundle."""
    base_path = getattr(sys, '_MEIPASS', os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base_path, relative_path)

def get_font_family(file_name):
    font_path = get_resource_path(os.path.join("font", file_name))
    if not os.path.exists(font_path): 
        return "Segoe UI Black"
    font_id = QtGui.QFontDatabase.addApplicationFont(font_path)
    if font_id == -1: 
        return "Segoe UI Black"
    return QtGui.QFontDatabase.applicationFontFamilies(font_id)[0]


# =============================================================================
# DRAWING HELPER: SCI-FI CORNER BRACKETS
# =============================================================================
def draw_sci_fi_corners(painter, rect, color, bracket_len=14, thickness=2):
    """Draws tech HUD corner brackets [ ┏ ┓ ┗ ┛ ] around a bounding rectangle."""
    painter.save()
    pen = QtGui.QPen(QtGui.QColor(color))
    pen.setWidth(thickness)
    painter.setPen(pen)

    x, y, w, h = rect.x(), rect.y(), rect.width(), rect.height()

    # Top-Left [┏]
    painter.drawLine(x, y, x + bracket_len, y)
    painter.drawLine(x, y, x, y + bracket_len)

    # Top-Right [┓]
    painter.drawLine(x + w, y, x + w - bracket_len, y)
    painter.drawLine(x + w, y, x + w, y + bracket_len)

    # Bottom-Left [┗]
    painter.drawLine(x, y + h, x + bracket_len, y + h)
    painter.drawLine(x, y + h, x, y + h - bracket_len)

    # Bottom-Right [┛]
    painter.drawLine(x + w, y + h, x + w - bracket_len, y + h)
    painter.drawLine(x + w, y + h, x + w, y + h - bracket_len)

    painter.restore()


# =============================================================================
# WIDGET: SEGMENTED LED BAR GAUGE (CPU / RAM / Battery / Disk)
# =============================================================================
class SegmentedGauge(QtWidgets.QWidget):
    """Futuristic segmented LED bar meter (12 neon blocks)."""
    def __init__(self, label, font_family, parent=None):
        super().__init__(parent)
        self.label = label
        self.font_family = font_family
        self.value = 0.0          # Current percentage (0 to 100)
        self.target_value = 0.0   # Target for smooth interpolation
        self.sub_text = ""        # Optional extra text (e.g. "[CHARGING]")
        self.total_segments = 12
        self.setFixedHeight(34)
        
        # Smooth interpolation timer
        self.anim_timer = QTimer(self)
        self.anim_timer.timeout.connect(self._step_anim)
        self.anim_timer.start(30)

    def set_value(self, val, sub_text=""):
        self.target_value = max(0.0, min(100.0, float(val)))
        self.sub_text = sub_text

    def _step_anim(self):
        diff = self.target_value - self.value
        if abs(diff) > 0.4:
            self.value += diff * 0.2
            self.update()
        elif self.value != self.target_value:
            self.value = self.target_value
            self.update()

    def paintEvent(self, event):
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.Antialiasing)

        w, h = self.width(), self.height()
        
        # 1. Label on left
        painter.setPen(QtGui.QColor(COLOR_TEXT_DIM))
        lbl_font = QtGui.QFont("Consolas", 11, QtGui.QFont.Bold)
        painter.setFont(lbl_font)
        painter.drawText(0, 0, 110, h, Qt.AlignVCenter | Qt.AlignLeft, self.label)

        # 2. Segmented LED Bars in middle
        bar_x = 115
        val_w = 60
        bar_w = w - bar_x - val_w
        if bar_w > 40:
            seg_gap = 3
            seg_w = max(3, (bar_w - (self.total_segments - 1) * seg_gap) / self.total_segments)
            seg_h = 10
            seg_y = (h - seg_h) // 2

            active_count = int(round((self.value / 100.0) * self.total_segments))

            for i in range(self.total_segments):
                sx = bar_x + i * (seg_w + seg_gap)
                rect = QRectF(sx, seg_y, seg_w, seg_h)

                if i < active_count:
                    # Color shift: Cyan (<70%) -> Amber (70-85%) -> Red (>85%)
                    if self.value < 70:
                        seg_color = QtGui.QColor(COLOR_ACCENT)
                    elif self.value < 85:
                        seg_color = QtGui.QColor("#ffb703")
                    else:
                        seg_color = QtGui.QColor(COLOR_WARN)
                    
                    painter.fillRect(rect, seg_color)
                else:
                    # Inactive dim segment
                    painter.fillRect(rect, QtGui.QColor(0, 95, 127, 45))

        # 3. Numeric Percentage readout on right
        val_str = f"{int(round(self.value))}%"
        if self.sub_text:
            val_str = f"{val_str}"

        painter.setPen(QtGui.QColor(COLOR_ACCENT if self.value < 85 else COLOR_WARN))
        num_font = QtGui.QFont("Consolas", 11, QtGui.QFont.Bold)
        painter.setFont(num_font)
        painter.drawText(w - val_w, 0, val_w, h, Qt.AlignVCenter | Qt.AlignRight, val_str)


# =============================================================================
# WIDGET: DATA STREAM ROW (Text + Tech Pill / Indicator)
# =============================================================================
class DataStreamRow(QtWidgets.QWidget):
    """Custom data stream row with dynamic sci-fi badges."""
    def __init__(self, key, parent=None):
        super().__init__(parent)
        self.key = key
        self.val_text = "INITIALIZING..."
        self.is_active = False
        self.setFixedHeight(30)

    def set_data(self, val_text, is_active=False):
        self.val_text = val_text
        self.is_active = is_active
        self.update()

    def paintEvent(self, event):
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.Antialiasing)

        w, h = self.width(), self.height()

        # Key label
        painter.setPen(QtGui.QColor(COLOR_TEXT_DIM))
        font_key = QtGui.QFont("Consolas", 11, QtGui.QFont.Bold)
        painter.setFont(font_key)
        painter.drawText(0, 0, 110, h, Qt.AlignVCenter | Qt.AlignLeft, self.key)

        # Value text / pill
        font_val = QtGui.QFont("Consolas", 11, QtGui.QFont.Bold)
        painter.setFont(font_val)

        # Highlight tag badges
        if "[ONLINE]" in self.val_text or "ACTIVE" in self.val_text:
            color = QtGui.QColor(COLOR_LISTEN)
        elif "[OFFLINE]" in self.val_text or "STANDBY" in self.val_text:
            color = QtGui.QColor(COLOR_SEC)
        elif "KB/s" in self.val_text:
            color = QtGui.QColor(COLOR_ACCENT)
        else:
            color = QtGui.QColor(COLOR_TEXT)

        painter.setPen(color)
        painter.drawText(115, 0, w - 115, h, Qt.AlignVCenter | Qt.AlignLeft, self.val_text)


# =============================================================================
# WIDGET: SCI-FI HUD PANEL (Diagnostics & System Status)
# =============================================================================
class HUDPanel(QtWidgets.QFrame):
    """Sci-Fi HUD card with glassmorphism, corner brackets, and live telemetry."""
    def __init__(self, title, font_family, alignment=Qt.AlignLeft, parent=None):
        super().__init__(parent)
        self.title_text = title
        self.font_family = font_family
        self.alignment = alignment

        self.setStyleSheet(f"""
            QFrame {{
                background-color: {COLOR_PANEL_BG};
                border: 1px solid {COLOR_BORDER};
                border-radius: 12px;
            }}
        """)

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(6)

        # Panel Title with Neon Accent Line
        self.title_lbl = QtWidgets.QLabel(title)
        self.title_lbl.setStyleSheet(f"""
            color: {COLOR_ACCENT}; 
            font-family: '{font_family}', 'Impact'; 
            font-size: 26px; 
            letter-spacing: 3px; 
            text-transform: uppercase;
            font-style: italic;
            border: none;
            background: transparent;
        """)
        self.title_lbl.setAlignment(alignment)
        layout.addWidget(self.title_lbl)

        # Accent tech divider line
        divider = QtWidgets.QFrame()
        divider.setFixedHeight(2)
        divider.setStyleSheet(f"""
            background: qlineargradient(x1:0, y1:0, x2:1, y2:0, 
                stop:0 {COLOR_ACCENT}, stop:0.7 {COLOR_SEC}, stop:1 transparent);
            border: none;
        """)
        layout.addWidget(divider)
        layout.addSpacing(6)

        self.content_layout = QtWidgets.QVBoxLayout()
        self.content_layout.setSpacing(4)
        layout.addLayout(self.content_layout)
        layout.addStretch()

    def paintEvent(self, event):
        super().paintEvent(event)
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.Antialiasing)
        # Draw high-tech corner brackets around the panel
        draw_sci_fi_corners(painter, self.rect().adjusted(2, 2, -2, -2), COLOR_ACCENT, bracket_len=14, thickness=2)


# =============================================================================
# WIDGET: MULTI-RING HOLOGRAPHIC ARC REACTOR (Centerpiece)
# =============================================================================
class RotatingCore(QtWidgets.QWidget):
    """
    Advanced Multi-Ring Sci-Fi Arc Reactor:
    - Outer radar calibration ring with 48 tick marks & compass degrees
    - Triple-segmented outer energy arcs with smooth rotational inertia
    - Middle orbital dotted ring with 3 orbiting satellite nodes
    - Dynamic sonar ripple waves expanding outward in 'listening' mode
    - Hyperspeed particle vortex spin in 'processing' mode
    - Energetic speech pulse rhythm in 'speaking' mode
    - Centerpiece avatar with holographic radial backlight and targeting reticle
    """
    def __init__(self, image_path="image.png", parent=None):
        super().__init__(parent)
        self.angle_1 = 0.0
        self.angle_2 = 0.0
        self.angle_3 = 0.0
        self.is_active = False 
        self.state = "idle" # idle | listening | processing | speaking

        # Animation Loop (60 FPS smooth)
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.animate)
        self.timer.start(16) 

        # Breathing / Pulse parameters
        self.pulse_phase = 0.0
        
        # Sonar Ripple Waves for 'listening' mode
        self.sonar_waves = [0.0, 30.0, 60.0]

        # Load avatar image
        self.pixmap = QtGui.QPixmap(image_path)
        if self.pixmap.isNull():
            self.pixmap = QtGui.QPixmap(300, 300)
            self.pixmap.fill(Qt.transparent)
            
        self.cached_pixmap = None 

    def set_state(self, state):
        self.state = state
        self.update()

    def animate(self):
        # Dynamic speeds mapped to AI state
        if self.state == "processing":
            speed = 9.0
        elif self.state == "listening":
            speed = 4.5
        elif self.state == "speaking":
            speed = 5.5
        elif self.is_active:
            speed = 3.0
        else:
            speed = 1.4

        # Continuous smooth angle increments
        self.angle_1 = (self.angle_1 + speed) % 360.0
        self.angle_2 = (self.angle_2 - (speed * 0.6)) % 360.0
        self.angle_3 = (self.angle_3 + (speed * 1.4)) % 360.0

        # Breathing sine wave for ambient glow
        self.pulse_phase += 0.08
        if self.pulse_phase > 2 * math.pi:
            self.pulse_phase -= 2 * math.pi

        # Sonar wave ripple progression in listening mode
        if self.state == "listening":
            for i in range(len(self.sonar_waves)):
                self.sonar_waves[i] = (self.sonar_waves[i] + 1.2) % 65.0

        self.update()

    def resizeEvent(self, event):
        w, h = self.width(), self.height()
        radius = min(w, h) // 2 - 50
        if radius > 0:
            self.cached_pixmap = self.pixmap.scaled(
                int(radius * 1.55), int(radius * 1.55), 
                Qt.KeepAspectRatio, 
                Qt.SmoothTransformation
            )
        else:
            self.cached_pixmap = None
        super().resizeEvent(event)

    def paintEvent(self, event):
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.Antialiasing)

        w, h = self.width(), self.height()
        cx, cy = w // 2, h // 2
        radius = min(w, h) // 2 - 55
        if radius <= 30:
            return

        # ---------------------------------------------------------------------
        # 1. State Color Selection
        # ---------------------------------------------------------------------
        if self.state == "listening":
            theme_color = QtGui.QColor(COLOR_LISTEN)
            accent_arc = QtGui.QColor(0, 255, 119, 220)
            dot_color = QtGui.QColor(0, 255, 119, 130)
            status_text = "LISTENING FOR AUDIO INPUT..."
        elif self.state == "processing":
            theme_color = QtGui.QColor(COLOR_PROCESS)
            accent_arc = QtGui.QColor(58, 134, 255, 230)
            dot_color = QtGui.QColor(58, 134, 255, 140)
            status_text = "NEURAL COGNITION RUNNING..."
        elif self.state == "speaking":
            theme_color = QtGui.QColor(COLOR_SPEAK)
            accent_arc = QtGui.QColor(255, 0, 127, 230)
            dot_color = QtGui.QColor(255, 0, 127, 140)
            status_text = "SYNTHESIZING VOCAL SPEECH..."
        else:
            theme_color = QtGui.QColor(COLOR_IDLE)
            accent_arc = QtGui.QColor(0, 217, 246, 200)
            dot_color = QtGui.QColor(0, 217, 246, 110)
            status_text = "CYPHER SYSTEM ONLINE :: STANDBY" if self.is_active else "CORE INITIALIZED :: READY"

        # ---------------------------------------------------------------------
        # 2. Sonar Ripple Waves (Listening Mode)
        # ---------------------------------------------------------------------
        if self.state == "listening":
            painter.save()
            for wave_offset in self.sonar_waves:
                r_sonar = radius + wave_offset
                # Opacity fades as wave expands outward
                alpha = int(max(0, 160 * (1.0 - (wave_offset / 65.0))))
                pen_sonar = QtGui.QPen(QtGui.QColor(0, 255, 119, alpha))
                pen_sonar.setWidth(2)
                painter.setPen(pen_sonar)
                painter.setBrush(Qt.NoBrush)
                painter.drawEllipse(QPointF(cx, cy), r_sonar, r_sonar)
            painter.restore()

        # ---------------------------------------------------------------------
        # 3. Outer Radial Radar Tick Marks (Compass Calibration Ring)
        # ---------------------------------------------------------------------
        painter.save()
        painter.translate(cx, cy)
        r_ticks = radius + 22
        painter.setPen(QtGui.QColor(0, 217, 246, 60))
        num_ticks = 48
        for i in range(num_ticks):
            angle_rad = i * (2 * math.pi / num_ticks)
            is_cardinal = (i % 12 == 0)
            tick_len = 8 if is_cardinal else 4
            
            p1_x = (r_ticks) * math.cos(angle_rad)
            p1_y = (r_ticks) * math.sin(angle_rad)
            p2_x = (r_ticks + tick_len) * math.cos(angle_rad)
            p2_y = (r_ticks + tick_len) * math.sin(angle_rad)
            
            if is_cardinal:
                painter.setPen(QtGui.QColor(theme_color.red(), theme_color.green(), theme_color.blue(), 180))
            else:
                painter.setPen(QtGui.QColor(theme_color.red(), theme_color.green(), theme_color.blue(), 60))
            painter.drawLine(QPointF(p1_x, p1_y), QPointF(p2_x, p2_y))
        painter.restore()

        # ---------------------------------------------------------------------
        # 4. Triple-Segmented Outer Rotating Energy Arc
        # ---------------------------------------------------------------------
        painter.save()
        painter.translate(cx, cy)
        painter.rotate(self.angle_1)
        pen_arc = QtGui.QPen(accent_arc)
        pen_arc.setWidth(4)
        pen_arc.setCapStyle(Qt.RoundCap)
        painter.setPen(pen_arc)
        r_outer_arc = radius + 10
        rect_outer = QRectF(-r_outer_arc, -r_outer_arc, r_outer_arc * 2, r_outer_arc * 2)
        # 3 arcs of 70 degrees each, spaced by 50 degrees
        painter.drawArc(rect_outer, 0 * 16, 70 * 16)
        painter.drawArc(rect_outer, 120 * 16, 70 * 16)
        painter.drawArc(rect_outer, 240 * 16, 70 * 16)
        painter.restore()

        # ---------------------------------------------------------------------
        # 5. Middle Orbital Dotted Ring with 3 Satellite Node Beads
        # ---------------------------------------------------------------------
        painter.save()
        painter.translate(cx, cy)
        painter.rotate(self.angle_2)
        
        pen_dot = QtGui.QPen(dot_color)
        pen_dot.setStyle(Qt.DotLine)
        pen_dot.setWidth(2)
        painter.setPen(pen_dot)
        painter.drawEllipse(QRectF(-radius, -radius, radius * 2, radius * 2))

        # 3 Orbiting Glowing Beads
        painter.setPen(Qt.NoPen)
        painter.setBrush(QtGui.QBrush(theme_color))
        for orb_angle in [0, 120, 240]:
            rad_orb = math.radians(orb_angle)
            ox = radius * math.cos(rad_orb)
            oy = radius * math.sin(rad_orb)
            painter.drawEllipse(QPointF(ox, oy), 4, 4)
        painter.restore()

        # ---------------------------------------------------------------------
        # 6. Inner Fast Counter-Rotating Blades
        # ---------------------------------------------------------------------
        painter.save()
        painter.translate(cx, cy)
        painter.rotate(self.angle_3)
        pen_inner = QtGui.QPen(QtGui.QColor(theme_color.red(), theme_color.green(), theme_color.blue(), 160))
        pen_inner.setWidth(2)
        painter.setPen(pen_inner)
        r_inner = radius - 15
        rect_inner = QRectF(-r_inner, -r_inner, r_inner * 2, r_inner * 2)
        painter.drawArc(rect_inner, 30 * 16, 100 * 16)
        painter.drawArc(rect_inner, 210 * 16, 100 * 16)
        painter.restore()

        # ---------------------------------------------------------------------
        # 7. Holographic Radial Backlight Behind Avatar
        # ---------------------------------------------------------------------
        painter.save()
        pulse_val = 0.5 + 0.5 * math.sin(self.pulse_phase)
        alpha_glow = int(35 + pulse_val * 45)
        grad = QtGui.QRadialGradient(cx, cy, radius - 20)
        grad.setColorAt(0.0, QtGui.QColor(theme_color.red(), theme_color.green(), theme_color.blue(), alpha_glow))
        grad.setColorAt(0.7, QtGui.QColor(theme_color.red(), theme_color.green(), theme_color.blue(), int(alpha_glow * 0.4)))
        grad.setColorAt(1.0, Qt.transparent)
        painter.setPen(Qt.NoPen)
        painter.setBrush(QtGui.QBrush(grad))
        painter.drawEllipse(QPointF(cx, cy), radius - 20, radius - 20)
        painter.restore()

        # ---------------------------------------------------------------------
        # 8. Center Avatar with Bezel & Clip Path
        # ---------------------------------------------------------------------
        if self.cached_pixmap:
            img_x = cx - self.cached_pixmap.width() // 2
            img_y = cy - self.cached_pixmap.height() // 2
            
            path = QtGui.QPainterPath()
            path.addEllipse(QPointF(cx, cy), radius - 30, radius - 30)
            
            painter.save()
            painter.setClipPath(path)
            painter.drawPixmap(img_x, img_y, self.cached_pixmap)
            painter.restore()

            # Glowing inner bezel ring
            pen_bezel = QtGui.QPen(QtGui.QColor(theme_color.red(), theme_color.green(), theme_color.blue(), 180))
            pen_bezel.setWidth(2)
            painter.setPen(pen_bezel)
            painter.setBrush(Qt.NoBrush)
            painter.drawEllipse(QPointF(cx, cy), radius - 30, radius - 30)

        # ---------------------------------------------------------------------
        # 9. Targeting Reticle / Crosshair Ticks (4 Cardinal Corners)
        # ---------------------------------------------------------------------
        painter.save()
        painter.setPen(QtGui.QColor(theme_color.red(), theme_color.green(), theme_color.blue(), 140))
        ret_r1 = radius - 38
        ret_r2 = radius - 24
        # North, South, East, West ticks
        painter.drawLine(cx, cy - ret_r1, cx, cy - ret_r2)
        painter.drawLine(cx, cy + ret_r1, cx, cy + ret_r2)
        painter.drawLine(cx - ret_r1, cy, cx - ret_r2, cy)
        painter.drawLine(cx + ret_r1, cy, cx + ret_r2, cy)
        painter.restore()

        # ---------------------------------------------------------------------
        # 10. Status Pill Readout Below Core
        # ---------------------------------------------------------------------
        painter.save()
        font_status = QtGui.QFont("Consolas", 11, QtGui.QFont.Bold)
        font_status.setLetterSpacing(QtGui.QFont.AbsoluteSpacing, 2)
        painter.setFont(font_status)
        painter.setPen(theme_color)
        text_rect = QtCore.QRect(0, cy + radius + 22, w, 28)
        painter.drawText(text_rect, Qt.AlignCenter, status_text)
        painter.restore()


# =============================================================================
# WIDGET: ANIMATED VOICE WAVEFORM / SPECTRUM EQUALIZER
# =============================================================================
class VoiceVisualizer(QtWidgets.QWidget):
    """
    Real-time Sci-Fi Sound Frequency Visualizer:
    - 32 vertical glowing neon bars
    - Smooth peak indicator caps that float and slowly drop
    - Animated sine hum during IDLE
    - Responsive energetic dancing waves during LISTENING and SPEAKING
    - Cyber matrix data pulse during PROCESSING
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.num_bars = 32
        self.bar_heights = [4.0] * self.num_bars
        self.peak_heights = [6.0] * self.num_bars
        self.state = "idle"
        self.wave_phase = 0.0
        self.setFixedHeight(65)

        self.anim_timer = QTimer(self)
        self.anim_timer.timeout.connect(self._step_wave)
        self.anim_timer.start(24) # ~40 FPS

    def set_state(self, state):
        self.state = state
        self.update()

    def _step_wave(self):
        self.wave_phase += 0.12
        max_h = self.height() - 20

        for i in range(self.num_bars):
            idx_ratio = i / float(self.num_bars)

            if self.state == "listening":
                # Lively reactive microphone dance with harmonic peaks
                sine1 = math.sin(self.wave_phase * 2.2 + i * 0.45)
                sine2 = math.cos(self.wave_phase * 1.5 - i * 0.25)
                noise = random.uniform(0.1, 0.4)
                target_h = max(5.0, (0.4 * abs(sine1) + 0.4 * abs(sine2) + noise) * max_h)
            elif self.state == "speaking":
                # High-energy vocal speech spectrum with centered amplitude peak
                bell = math.exp(-((idx_ratio - 0.5) ** 2) / 0.12)
                pulse = abs(math.sin(self.wave_phase * 3.0 + i * 0.3))
                jitter = random.uniform(0.05, 0.25)
                target_h = max(6.0, (pulse * 0.75 + jitter) * bell * max_h + 8.0)
            elif self.state == "processing":
                # Digital matrix scanning wave sweeping across the spectrum
                sweep = (math.sin(self.wave_phase * 2.0 - i * 0.3) + 1.0) / 2.0
                target_h = max(4.0, (sweep ** 2) * max_h * 0.8)
            else:
                # Idle: Smooth gentle ambient breathing ripple
                ripple = math.sin(self.wave_phase + i * 0.25) * 0.5 + 0.5
                target_h = max(4.0, ripple * 16.0 + 3.0)

            # Smooth approach to target height
            self.bar_heights[i] += (target_h - self.bar_heights[i]) * 0.35

            # Peak cap drop mechanics
            if self.bar_heights[i] >= self.peak_heights[i]:
                self.peak_heights[i] = self.bar_heights[i]
            else:
                self.peak_heights[i] = max(self.bar_heights[i], self.peak_heights[i] - 1.2)

        self.update()

    def paintEvent(self, event):
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.Antialiasing)

        w, h = self.width(), self.height()

        # Color based on state
        if self.state == "listening":
            bar_color = QtGui.QColor(COLOR_LISTEN)
            cap_color = QtGui.QColor("#ffffff")
        elif self.state == "processing":
            bar_color = QtGui.QColor(COLOR_PROCESS)
            cap_color = QtGui.QColor("#90e0ef")
        elif self.state == "speaking":
            bar_color = QtGui.QColor(COLOR_SPEAK)
            cap_color = QtGui.QColor("#ffffff")
        else:
            bar_color = QtGui.QColor(COLOR_ACCENT)
            cap_color = QtGui.QColor("#ffffff")

        # Background frame for spectrum
        bg_rect = QRectF(0, 0, w, h)
        painter.fillRect(bg_rect, QtGui.QColor(4, 10, 18, 120))
        painter.setPen(QtGui.QPen(QtGui.QColor(0, 217, 246, 40), 1))
        painter.drawRect(bg_rect)

        # Draw sci-fi corner accents on visualizer
        draw_sci_fi_corners(painter, self.rect(), COLOR_ACCENT, bracket_len=8, thickness=1)

        # Draw bars
        bar_gap = 3
        bar_w = max(2.0, (w - 20 - (self.num_bars - 1) * bar_gap) / float(self.num_bars))
        base_y = h - 10

        for i in range(self.num_bars):
            bx = 10 + i * (bar_w + bar_gap)
            bh = self.bar_heights[i]
            by = base_y - bh

            # Bar with vertical gradient
            grad = QtGui.QLinearGradient(bx, base_y, bx, by)
            grad.setColorAt(0.0, QtGui.QColor(bar_color.red(), bar_color.green(), bar_color.blue(), 100))
            grad.setColorAt(1.0, bar_color)

            painter.fillRect(QRectF(bx, by, bar_w, bh), QtGui.QBrush(grad))

            # Floating peak indicator cap
            cap_y = base_y - self.peak_heights[i] - 3
            painter.fillRect(QRectF(bx, cap_y, bar_w, 2), cap_color)

        # Header subtext
        painter.setPen(QtGui.QColor(0, 217, 246, 120))
        font_sub = QtGui.QFont("Consolas", 8, QtGui.QFont.Bold)
        painter.setFont(font_sub)
        painter.drawText(QRectF(12, 4, w - 24, 16), Qt.AlignLeft, "AUDIO FREQUENCY SPECTRUM :: 44.1 kHz")


# =============================================================================
# WIDGET: TERMINAL BOX (Hacker Typewriter Effect with Sci-Fi Framing)
# =============================================================================
class TerminalBox(QtWidgets.QTextEdit):
    """Terminal with high-tech typewriter animation and custom syntax colors."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setReadOnly(True)
        self.setStyleSheet(f"""
            QTextEdit {{
                background-color: rgba(2, 6, 12, 0.85);
                color: {COLOR_ACCENT};
                font-family: 'Consolas', monospace;
                font-size: 15px;
                font-weight: bold;
                border: 1px solid {COLOR_BORDER};
                border-top: 2px solid {COLOR_ACCENT}; 
                border-radius: 6px;
                padding: 10px;
            }}
        """)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        
        # Typewriter queue
        self.char_queue = []
        self.type_timer = QTimer(self)
        self.type_timer.timeout.connect(self._process_queue)
        self.type_timer.start(12) 

    @pyqtSlot(str)
    def log(self, text):
        self.char_queue.extend(list(f"> {text.upper()}\n"))

    def _process_queue(self):
        if self.char_queue:
            # Process up to 2 characters per tick for fluid typing
            chunk = ""
            for _ in range(min(2, len(self.char_queue))):
                chunk += self.char_queue.pop(0)
            self.moveCursor(QtGui.QTextCursor.End)
            self.insertPlainText(chunk)
            self.verticalScrollBar().setValue(self.verticalScrollBar().maximum())

    def paintEvent(self, event):
        super().paintEvent(event)
        painter = QtGui.QPainter(self.viewport())
        painter.setRenderHint(QtGui.QPainter.Antialiasing)
        draw_sci_fi_corners(painter, self.rect().adjusted(2, 2, -2, -2), COLOR_ACCENT, bracket_len=10, thickness=1)


# =============================================================================
# WIDGET: HOLOGRAPHIC CREDENTIALS VAULT & PROTOCOL CONFIGURATION
# =============================================================================
class SettingsDialog(QtWidgets.QDialog):
    """
    Holographic Sci-Fi Credentials Vault & Settings Dialog.
    Enables users (especially when running as a standalone .exe) to configure,
    test, and persist their API keys and credentials directly from the GUI.
    """
    sig_test_result = pyqtSignal(bool, str)

    def __init__(self, cypher_core, parent=None):
        super().__init__(parent)
        self.cypher = cypher_core
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Dialog)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setFixedSize(740, 720)
        self.oldPos = self.pos()

        self.tech_font = get_font_family("WarriotTechItalic-YqOoa.ttf")
        self.inputs = {}
        self.sig_test_result.connect(self._on_test_finished)

        # Outer root layout
        root_layout = QtWidgets.QVBoxLayout(self)
        root_layout.setContentsMargins(10, 10, 10, 10)

        # Main frame with dark obsidian glassmorphism
        frame = QtWidgets.QFrame()
        frame.setStyleSheet(f"""
            QFrame {{
                background-color: rgba(4, 9, 18, 0.96);
                border: 1px solid rgba(0, 217, 246, 0.55);
                border-radius: 8px;
            }}
        """)
        frame_layout = QtWidgets.QVBoxLayout(frame)
        frame_layout.setContentsMargins(20, 16, 20, 16)
        frame_layout.setSpacing(12)

        # 1. Header Bar
        header_bar = QtWidgets.QHBoxLayout()
        title_box = QtWidgets.QVBoxLayout()
        title_box.setSpacing(2)
        lbl_title = QtWidgets.QLabel("CYPHER CONFIGURATION PROTOCOL // CREDENTIAL VAULT")
        lbl_title.setStyleSheet(f"""
            color: {COLOR_ACCENT};
            font-family: 'Consolas', monospace;
            font-size: 15px;
            font-weight: bold;
            letter-spacing: 2px;
            border: none;
            background: transparent;
        """)
        lbl_sub = QtWidgets.QLabel("RUNTIME SYSTEM KEYS & NEURAL ENGINE ACCESS")
        lbl_sub.setStyleSheet("color: rgba(0, 217, 246, 0.6); font-family: 'Consolas', monospace; font-size: 10px; letter-spacing: 1px; border: none; background: transparent;")
        title_box.addWidget(lbl_title)
        title_box.addWidget(lbl_sub)
        header_bar.addLayout(title_box)

        header_bar.addStretch()

        btn_close = QtWidgets.QPushButton("✕")
        btn_close.setFixedSize(32, 26)
        btn_close.setCursor(Qt.PointingHandCursor)
        btn_close.clicked.connect(self.reject)
        btn_close.setStyleSheet(f"""
            QPushButton {{
                color: {COLOR_WARN};
                background: transparent;
                border: 1px solid {COLOR_WARN};
                border-radius: 4px;
                font-weight: bold;
                font-size: 12px;
            }}
            QPushButton:hover {{
                background-color: {COLOR_WARN};
                color: #ffffff;
            }}
        """)
        header_bar.addWidget(btn_close)
        frame_layout.addLayout(header_bar)

        # Divider
        divider = QtWidgets.QFrame()
        divider.setFrameShape(QtWidgets.QFrame.HLine)
        divider.setStyleSheet("border: none; background-color: rgba(0, 217, 246, 0.25); max-height: 1px;")
        frame_layout.addWidget(divider)

        # 2. Scrollable Credentials Container
        scroll = QtWidgets.QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("""
            QScrollArea {
                border: none;
                background: transparent;
            }
            QScrollBar:vertical {
                background: rgba(0, 20, 35, 0.4);
                width: 8px;
                margin: 0px;
                border-radius: 4px;
            }
            QScrollBar::handle:vertical {
                background: rgba(0, 217, 246, 0.4);
                min-height: 20px;
                border-radius: 4px;
            }
            QScrollBar::handle:vertical:hover {
                background: #00d9f6;
            }
        """)

        content_widget = QtWidgets.QWidget()
        content_widget.setStyleSheet("background: transparent;")
        content_layout = QtWidgets.QVBoxLayout(content_widget)
        content_layout.setContentsMargins(4, 4, 10, 4)
        content_layout.setSpacing(14)

        # Section 1: Neural Cores
        content_layout.addWidget(self._make_section_header("01 // NEURAL INTELLIGENCE ENGINE"))
        content_layout.addWidget(self._make_credential_row(
            key_name="GEMINI_API_KEY",
            label_text="Google Gemini API Key",
            is_required=True,
            helper_url="https://aistudio.google.com/app/apikey",
            helper_btn_text="🔑 GET FREE KEY",
            description="Required for conversational reasoning, general query synthesis, and AI workflows."
        ))
        content_layout.addWidget(self._make_credential_row(
            key_name="GROQ_API_KEY",
            label_text="Groq API Key",
            is_required=False,
            helper_url="https://console.groq.com/keys",
            helper_btn_text="⚡ GET KEY",
            description="High-speed fallback engine when Gemini is rate-limited or offline."
        ))

        # Section 2: Satellite & Telemetry
        content_layout.addWidget(self._make_section_header("02 // SATELLITE & TELEMETRY FEEDS"))
        content_layout.addWidget(self._make_credential_row(
            key_name="OPENWEATHER_KEY",
            label_text="OpenWeather API Key",
            is_required=False,
            helper_url="https://home.openweathermap.org/api_keys",
            helper_btn_text="⛅ GET KEY",
            description="Enables live real-time weather and temperature queries for any city."
        ))
        content_layout.addWidget(self._make_credential_row(
            key_name="NEWS_API_KEY",
            label_text="NewsData.io API Key",
            is_required=False,
            helper_url="https://newsdata.io/register",
            helper_btn_text="📰 GET KEY",
            description="Enables live world news and tech headline feeds."
        ))

        # Section 3: Communications
        content_layout.addWidget(self._make_section_header("03 // AUTOMATED COMMUNICATIONS"))
        content_layout.addWidget(self._make_credential_row(
            key_name="EMAIL_USER",
            label_text="Gmail Address",
            is_required=False,
            is_password=False,
            description="Your Gmail address for automated email dispatch and unread inbox checks."
        ))
        content_layout.addWidget(self._make_credential_row(
            key_name="EMAIL_PASS",
            label_text="Google App Password",
            is_required=False,
            helper_url="https://myaccount.google.com/apppasswords",
            helper_btn_text="🔐 APP PASSWORDS",
            description="16-character Google App Password (not your primary Google password)."
        ))

        scroll.setWidget(content_widget)
        frame_layout.addWidget(scroll, 1)

        # 3. Diagnostic Connection Test Bar
        test_frame = QtWidgets.QFrame()
        test_frame.setStyleSheet("""
            QFrame {
                background-color: rgba(2, 6, 14, 0.7);
                border: 1px solid rgba(0, 217, 246, 0.3);
                border-radius: 6px;
            }
        """)
        test_layout = QtWidgets.QHBoxLayout(test_frame)
        test_layout.setContentsMargins(10, 8, 10, 8)
        test_layout.setSpacing(10)

        self.btn_test = QtWidgets.QPushButton("🧪 TEST GEMINI KEY")
        self.btn_test.setCursor(Qt.PointingHandCursor)
        self.btn_test.setFixedHeight(30)
        self.btn_test.setStyleSheet(f"""
            QPushButton {{
                background-color: rgba(0, 217, 246, 0.15);
                color: {COLOR_ACCENT};
                border: 1px solid {COLOR_ACCENT};
                border-radius: 4px;
                font-family: 'Consolas', monospace;
                font-weight: bold;
                font-size: 11px;
                padding: 0 12px;
            }}
            QPushButton:hover {{
                background-color: {COLOR_ACCENT};
                color: #04070c;
            }}
            QPushButton:disabled {{
                border-color: #555555;
                color: #777777;
            }}
        """)
        self.btn_test.clicked.connect(self._run_connection_test)
        test_layout.addWidget(self.btn_test)

        self.lbl_test_status = QtWidgets.QLabel("PROBE READY :: VERIFY NEURAL CONNECTION BEFORE SAVING")
        self.lbl_test_status.setStyleSheet("color: rgba(0, 217, 246, 0.7); font-family: 'Consolas', monospace; font-size: 11px; border: none; background: transparent;")
        test_layout.addWidget(self.lbl_test_status, 1)

        frame_layout.addWidget(test_frame)

        # 4. Action Controls
        btn_bar = QtWidgets.QHBoxLayout()
        btn_bar.setSpacing(10)
        btn_bar.addStretch()

        btn_cancel = QtWidgets.QPushButton("CANCEL")
        btn_cancel.setFixedSize(100, 36)
        btn_cancel.setCursor(Qt.PointingHandCursor)
        btn_cancel.clicked.connect(self.reject)
        btn_cancel.setStyleSheet("""
            QPushButton {
                background: transparent;
                color: #999999;
                border: 1px solid #444444;
                border-radius: 4px;
                font-family: 'Consolas', monospace;
                font-size: 12px;
                font-weight: bold;
            }
            QPushButton:hover {
                color: #ffffff;
                border-color: #777777;
            }
        """)
        btn_bar.addWidget(btn_cancel)

        self.btn_save = QtWidgets.QPushButton("💾 SAVE && APPLY PROTOCOLS")
        self.btn_save.setFixedSize(220, 36)
        self.btn_save.setCursor(Qt.PointingHandCursor)
        self.btn_save.clicked.connect(self._save_credentials)
        self.btn_save.setStyleSheet(f"""
            QPushButton {{
                background-color: {COLOR_ACCENT};
                color: #04070c;
                border: 1px solid {COLOR_ACCENT};
                border-radius: 4px;
                font-family: 'Consolas', monospace;
                font-size: 12px;
                font-weight: bold;
                letter-spacing: 1px;
            }}
            QPushButton:hover {{
                background-color: #ffffff;
                color: #04070c;
                border-color: #ffffff;
            }}
        """)
        btn_bar.addWidget(self.btn_save)

        frame_layout.addLayout(btn_bar)
        root_layout.addWidget(frame)

    def _make_section_header(self, text):
        lbl = QtWidgets.QLabel(text)
        lbl.setStyleSheet(f"""
            color: {COLOR_SEC};
            font-family: 'Consolas', monospace;
            font-size: 11px;
            font-weight: bold;
            letter-spacing: 2px;
            padding-top: 6px;
            border: none;
            background: transparent;
        """)
        return lbl

    def _make_credential_row(self, key_name, label_text, is_required=False, helper_url=None, helper_btn_text="GET KEY", description="", is_password=True):
        row_widget = QtWidgets.QWidget()
        row_widget.setStyleSheet("background: transparent;")
        vbox = QtWidgets.QVBoxLayout(row_widget)
        vbox.setContentsMargins(0, 0, 0, 0)
        vbox.setSpacing(4)

        h_row = QtWidgets.QHBoxLayout()
        h_row.setSpacing(8)

        lbl_name = QtWidgets.QLabel(label_text)
        lbl_name.setStyleSheet("color: #ffffff; font-family: 'Consolas', monospace; font-size: 12px; font-weight: bold; border: none;")
        h_row.addWidget(lbl_name)

        badge = QtWidgets.QLabel("[REQUIRED]" if is_required else "[OPTIONAL]")
        badge_style = f"color: {COLOR_ACCENT}; background-color: rgba(0, 217, 246, 0.15); border: 1px solid {COLOR_ACCENT};" if is_required else "color: #778899; background: transparent; border: 1px solid #445566;"
        badge.setStyleSheet(f"{badge_style} font-family: 'Consolas', monospace; font-size: 9px; font-weight: bold; padding: 1px 6px; border-radius: 3px;")
        h_row.addWidget(badge)

        h_row.addStretch()

        if helper_url:
            btn_helper = QtWidgets.QPushButton(helper_btn_text)
            btn_helper.setCursor(Qt.PointingHandCursor)
            btn_helper.setFixedHeight(22)
            btn_helper.setStyleSheet(f"""
                QPushButton {{
                    color: {COLOR_ACCENT};
                    background: transparent;
                    border: 1px solid rgba(0, 217, 246, 0.4);
                    border-radius: 3px;
                    font-family: 'Consolas', monospace;
                    font-size: 10px;
                    font-weight: bold;
                    padding: 0 8px;
                }}
                QPushButton:hover {{
                    background-color: rgba(0, 217, 246, 0.2);
                    border-color: {COLOR_ACCENT};
                    color: #ffffff;
                }}
            """)
            btn_helper.clicked.connect(lambda _, url=helper_url: webbrowser.open(url))
            h_row.addWidget(btn_helper)

        vbox.addLayout(h_row)

        if description:
            lbl_desc = QtWidgets.QLabel(description)
            lbl_desc.setStyleSheet("color: rgba(200, 220, 240, 0.6); font-family: 'Consolas', monospace; font-size: 10px; border: none;")
            lbl_desc.setWordWrap(True)
            vbox.addWidget(lbl_desc)

        inp_row = QtWidgets.QHBoxLayout()
        inp_row.setSpacing(6)

        line_edit = QtWidgets.QLineEdit()
        line_edit.setText(os.getenv(key_name, ""))
        line_edit.setFixedHeight(34)
        line_edit.setStyleSheet(f"""
            QLineEdit {{
                background-color: rgba(2, 6, 12, 0.9);
                color: {COLOR_ACCENT};
                border: 1px solid rgba(0, 217, 246, 0.4);
                border-radius: 4px;
                padding: 4px 10px;
                font-family: 'Consolas', monospace;
                font-size: 13px;
            }}
            QLineEdit:focus {{
                border: 1px solid {COLOR_ACCENT};
                background-color: rgba(0, 20, 35, 0.95);
            }}
        """)
        if is_password:
            line_edit.setEchoMode(QtWidgets.QLineEdit.Password)

        inp_row.addWidget(line_edit, 1)

        if is_password:
            btn_eye = QtWidgets.QPushButton("👁")
            btn_eye.setFixedSize(34, 34)
            btn_eye.setCursor(Qt.PointingHandCursor)
            btn_eye.setStyleSheet(f"""
                QPushButton {{
                    background-color: rgba(0, 20, 35, 0.8);
                    color: {COLOR_ACCENT};
                    border: 1px solid rgba(0, 217, 246, 0.4);
                    border-radius: 4px;
                    font-size: 13px;
                }}
                QPushButton:hover {{
                    border-color: {COLOR_ACCENT};
                    background-color: rgba(0, 217, 246, 0.2);
                }}
            """)
            def toggle_echo(le=line_edit, btn=btn_eye):
                if le.echoMode() == QtWidgets.QLineEdit.Password:
                    le.setEchoMode(QtWidgets.QLineEdit.Normal)
                    btn.setText("🔒")
                else:
                    le.setEchoMode(QtWidgets.QLineEdit.Password)
                    btn.setText("👁")
            btn_eye.clicked.connect(toggle_echo)
            inp_row.addWidget(btn_eye)

        vbox.addLayout(inp_row)
        self.inputs[key_name] = line_edit
        return row_widget

    def _run_connection_test(self):
        gemini_key = self.inputs.get("GEMINI_API_KEY").text().strip() if "GEMINI_API_KEY" in self.inputs else ""
        if not gemini_key:
            self.lbl_test_status.setText("✖ ABORTED: GEMINI API KEY IS REQUIRED")
            self.lbl_test_status.setStyleSheet("color: #ff4455; font-family: 'Consolas', monospace; font-size: 11px;")
            return

        self.btn_test.setEnabled(False)
        self.lbl_test_status.setText("CONNECTING TO GOOGLE AI STUDIO (PROBING NEURAL CORE)...")
        self.lbl_test_status.setStyleSheet("color: #ffaa00; font-family: 'Consolas', monospace; font-size: 11px;")

        def worker():
            ok, msg = self.cypher.test_gemini_connection(gemini_key)
            self.sig_test_result.emit(ok, msg)

        threading.Thread(target=worker, daemon=True).start()

    @pyqtSlot(bool, str)
    def _on_test_finished(self, success, message):
        self.btn_test.setEnabled(True)
        if success:
            self.lbl_test_status.setText(f"✔ {message.upper()}")
            self.lbl_test_status.setStyleSheet(f"color: {COLOR_LISTEN}; font-family: 'Consolas', monospace; font-size: 11px; font-weight: bold;")
        else:
            self.lbl_test_status.setText(f"✖ {message.upper()[:75]}")
            self.lbl_test_status.setStyleSheet(f"color: {COLOR_WARN}; font-family: 'Consolas', monospace; font-size: 11px; font-weight: bold;")

    def _save_credentials(self):
        new_keys = {}
        for k, inp in self.inputs.items():
            new_keys[k] = inp.text().strip()

        save_env_keys(new_keys)
        self.cypher.reload_api_clients()
        self.accept()

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.oldPos = event.globalPos()

    def mouseMoveEvent(self, event):
        if event.buttons() == Qt.LeftButton:
            delta = QPointF(event.globalPos() - self.oldPos)
            self.move(int(self.x() + delta.x()), int(self.y() + delta.y()))
            self.oldPos = event.globalPos()

    def paintEvent(self, event):
        super().paintEvent(event)
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.Antialiasing)
        draw_sci_fi_corners(painter, self.rect().adjusted(10, 10, -10, -10), COLOR_ACCENT, bracket_len=14, thickness=2)


# =============================================================================
# MAIN WINDOW: CYPHER F.R.I.D.A.Y. HUD
# =============================================================================
class MainWindow(QtWidgets.QMainWindow):
    sig_log = pyqtSignal(str)
    sig_close = pyqtSignal()
    sig_state = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self.setWindowFlags(Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.resize(1440, 920)
        self.setWindowTitle("CYPHER VOICE ASSISTANT")
        self.tech_font = get_font_family("WarriotTechItalic-YqOoa.ttf")
        
        self.last_net = psutil.net_io_counters()

        # Central Root Frame with Sci-Fi Glassmorphism
        central = QtWidgets.QFrame()
        central.setStyleSheet(f"""
            QFrame#CentralRoot {{
                background-color: {COLOR_BG};
                border: 2px solid {COLOR_BORDER};
                border-radius: 20px;
            }}
        """)
        central.setObjectName("CentralRoot")
        self.setCentralWidget(central)

        main_layout = QtWidgets.QVBoxLayout(central)
        main_layout.setContentsMargins(26, 14, 26, 22)
        main_layout.setSpacing(10)

        # ---------------------------------------------------------------------
        # 1. TOP BAR: STATUS PILL + WINDOW CONTROLS
        # ---------------------------------------------------------------------
        top_bar = QtWidgets.QHBoxLayout()
        top_bar.setContentsMargins(0, 0, 0, 0)

        # Left: Sci-Fi Security Banner
        self.lbl_sec_badge = QtWidgets.QLabel("● PROTOCOL: CYPHER-V3 // NEURAL HUD ACTIVE")
        self.lbl_sec_badge.setStyleSheet(f"""
            color: {COLOR_ACCENT};
            font-family: 'Consolas', monospace;
            font-size: 12px;
            font-weight: bold;
            letter-spacing: 2px;
            border: none;
            background: transparent;
        """)
        top_bar.addWidget(self.lbl_sec_badge)
        top_bar.addStretch()

        # Center: Animated Holographic Mode Pill
        self.mode_pill = QtWidgets.QLabel("[ STANDBY ]")
        self.mode_pill.setStyleSheet(f"""
            color: {COLOR_ACCENT};
            background-color: rgba(0, 217, 246, 0.12);
            border: 1px solid {COLOR_ACCENT};
            border-radius: 12px;
            padding: 4px 18px;
            font-family: 'Consolas', monospace;
            font-size: 13px;
            font-weight: bold;
            letter-spacing: 2px;
        """)
        self.mode_pill.setAlignment(Qt.AlignCenter)
        top_bar.addWidget(self.mode_pill)
        top_bar.addStretch()

        # Right: Window Control Frame (Settings, Minimize & Close)
        control_frame = QtWidgets.QFrame()
        control_frame.setFixedSize(200, 36)
        control_frame.setStyleSheet(f"""
            QFrame {{
                background-color: rgba(0, 20, 35, 0.85);
                border: 1px solid {COLOR_BORDER};
                border-radius: 6px;
            }}
        """)
        ctrl_layout = QtWidgets.QHBoxLayout(control_frame)
        ctrl_layout.setContentsMargins(5, 3, 5, 3)
        ctrl_layout.setSpacing(4)

        # Config / Settings Button
        self.btn_config = QtWidgets.QPushButton("⚙ CONFIG")
        self.btn_config.setFixedSize(82, 28)
        self.btn_config.clicked.connect(self.open_settings)
        self.btn_config.setCursor(Qt.PointingHandCursor)
        self.btn_config.setStyleSheet(f"""
            QPushButton {{
                color: {COLOR_ACCENT};
                background-color: transparent;
                border: 1px solid {COLOR_SEC};
                border-radius: 4px;
                font-family: 'Consolas', monospace;
                font-weight: bold; 
                font-size: 11px;
                letter-spacing: 1px;
            }}
            QPushButton:hover {{
                background-color: rgba(0, 217, 246, 0.25);
                border: 1px solid {COLOR_ACCENT};
                color: #ffffff;
            }}
        """)

        # Minimize Button
        self.btn_min = QtWidgets.QPushButton("─")
        self.btn_min.setFixedSize(46, 28)
        self.btn_min.clicked.connect(self.showMinimized)
        self.btn_min.setCursor(Qt.PointingHandCursor)
        self.btn_min.setStyleSheet(f"""
            QPushButton {{
                color: {COLOR_ACCENT};
                background-color: transparent;
                border: 1px solid {COLOR_SEC};
                border-radius: 4px;
                font-weight: bold; 
                font-size: 14px;
            }}
            QPushButton:hover {{
                background-color: rgba(0, 217, 246, 0.25);
                border: 1px solid {COLOR_ACCENT};
                color: #ffffff;
            }}
        """)

        # Close Button
        self.btn_close = QtWidgets.QPushButton("✕")
        self.btn_close.setFixedSize(46, 28)
        self.btn_close.clicked.connect(self.close_safely)
        self.btn_close.setCursor(Qt.PointingHandCursor)
        self.btn_close.setStyleSheet(f"""
            QPushButton {{
                color: {COLOR_WARN};
                background-color: transparent;
                border: 1px solid {COLOR_WARN};
                border-radius: 4px;
                font-weight: bold; 
                font-size: 13px;
            }}
            QPushButton:hover {{
                background-color: {COLOR_WARN};
                color: #ffffff;
                border: 1px solid #ff6666;
            }}
        """)

        ctrl_layout.addWidget(self.btn_config)
        ctrl_layout.addWidget(self.btn_min)
        ctrl_layout.addWidget(self.btn_close)
        top_bar.addWidget(control_frame)

        main_layout.addLayout(top_bar)

        # ---------------------------------------------------------------------
        # 2. HEADER
        # ---------------------------------------------------------------------
        header = QtWidgets.QLabel("CYPHER VOICE ASSISTANT")
        header.setAlignment(Qt.AlignCenter)
        header.setStyleSheet(f"""
            color: {COLOR_ACCENT}; 
            font-family: '{self.tech_font}', 'Arial Black'; 
            font-size: 40px; 
            letter-spacing: 6px; 
            font-weight: 400; 
            border: none;
            background: transparent;
            font-style: italic;
        """)
        main_layout.addWidget(header)
        
        # ---------------------------------------------------------------------
        # 3. MIDDLE SECTION: DIAGNOSTICS | ARC REACTOR | SYSTEM STATUS
        # ---------------------------------------------------------------------
        middle_layout = QtWidgets.QHBoxLayout()
        middle_layout.setSpacing(18)

        # Left HUD: Diagnostics
        self.left_panel = HUDPanel("DIAGNOSTICS", self.tech_font, Qt.AlignLeft)
        self.left_panel.setFixedWidth(390)
        self.row_net_down = DataStreamRow("NET_DOWN")
        self.row_net_up   = DataStreamRow("NET_UP")
        self.gauge_disk   = SegmentedGauge("DISK_USED", self.tech_font)
        self.row_threads  = DataStreamRow("THRD_CNT")
        self.row_ai_core  = DataStreamRow("AI_CORE")
        self.row_v_mod    = DataStreamRow("V_MODULE")

        self.left_panel.content_layout.addWidget(self.row_net_down)
        self.left_panel.content_layout.addWidget(self.row_net_up)
        self.left_panel.content_layout.addWidget(self.gauge_disk)
        self.left_panel.content_layout.addWidget(self.row_threads)
        self.left_panel.content_layout.addWidget(self.row_ai_core)
        self.left_panel.content_layout.addWidget(self.row_v_mod)
        
        # Center: Multi-Ring Arc Reactor
        img_path = get_resource_path("image.png")
        self.core = RotatingCore(img_path)
        self.core.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Expanding)
        
        # Right HUD: System Status
        self.right_panel = HUDPanel("SYSTEM STATUS", self.tech_font, Qt.AlignRight)
        self.right_panel.setFixedWidth(390)
        self.gauge_cpu    = SegmentedGauge("CPU_LOAD", self.tech_font)
        self.gauge_ram    = SegmentedGauge("MEM_ALLOC", self.tech_font)
        self.gauge_bat    = SegmentedGauge("PWR_STATUS", self.tech_font)
        self.row_net_link = DataStreamRow("NET_LINK")
        self.row_clock    = DataStreamRow("SYS_CLOCK")
        self.row_sec      = DataStreamRow("SEC_PROTO")

        self.right_panel.content_layout.addWidget(self.gauge_cpu)
        self.right_panel.content_layout.addWidget(self.gauge_ram)
        self.right_panel.content_layout.addWidget(self.gauge_bat)
        self.right_panel.content_layout.addWidget(self.row_net_link)
        self.right_panel.content_layout.addWidget(self.row_clock)
        self.right_panel.content_layout.addWidget(self.row_sec)

        middle_layout.addWidget(self.left_panel)
        middle_layout.addWidget(self.core, 1) 
        middle_layout.addWidget(self.right_panel)
        main_layout.addLayout(middle_layout, 1)

        # ---------------------------------------------------------------------
        # 4. SOUND SPECTRUM FREQUENCY VISUALIZER
        # ---------------------------------------------------------------------
        self.visualizer = VoiceVisualizer()
        main_layout.addWidget(self.visualizer)

        # ---------------------------------------------------------------------
        # 5. BOTTOM SECTION: TERMINAL + ACTION BUTTON
        # ---------------------------------------------------------------------
        bottom_layout = QtWidgets.QVBoxLayout()
        bottom_layout.setSpacing(6)

        # Terminal Title Bar
        term_bar = QtWidgets.QHBoxLayout()
        lbl_term = QtWidgets.QLabel("COMMAND LINE INTERFACE // SUBSYSTEM LOGS")
        lbl_term.setStyleSheet(f"""
            color: {COLOR_SEC}; 
            font-family: 'Consolas', monospace; 
            font-size: 13px; 
            font-weight: bold;
            letter-spacing: 2px; 
            border: none;
            background: transparent;
        """)
        term_bar.addWidget(lbl_term)
        term_bar.addStretch()

        self.lbl_stream = QtWidgets.QLabel("STREAM: ACTIVE ●")
        self.lbl_stream.setStyleSheet(f"color: {COLOR_ACCENT}; font-family: 'Consolas', monospace; font-size: 11px; font-weight: bold; border: none;")
        term_bar.addWidget(self.lbl_stream)
        bottom_layout.addLayout(term_bar)
        
        # Terminal Box
        self.terminal = TerminalBox()
        self.terminal.setFixedHeight(180)
        bottom_layout.addWidget(self.terminal)
        
        # Action Protocol Button
        self.btn_action = QtWidgets.QPushButton("INITIATE PROTOCOL")
        self.btn_action.setCursor(Qt.PointingHandCursor)
        self.btn_action.setFixedHeight(56)
        self.btn_action.setStyleSheet(f"""
            QPushButton {{
                background-color: rgba(0, 217, 246, 0.1);
                color: {COLOR_ACCENT};
                border: 2px solid {COLOR_ACCENT};
                font-family: '{self.tech_font}'; 
                font-size: 22px; 
                letter-spacing: 3px;
                border-radius: 12px;
                font-style: italic;
            }}
            QPushButton:hover {{ 
                background-color: {COLOR_ACCENT}; 
                color: {COLOR_BG}; 
            }}
        """)
        self.btn_action.clicked.connect(self.toggle_system)
        bottom_layout.addWidget(self.btn_action)

        main_layout.addLayout(bottom_layout)

        # ---------------------------------------------------------------------
        # SIGNALS & BACKEND INTEGRATION
        # ---------------------------------------------------------------------
        self.sig_log.connect(self.terminal.log)
        self.sig_close.connect(self.close_safely)
        self.sig_state.connect(self.on_state_changed)
        self.cypher = CypherCore()

        # ESC shortcut to halt voice output
        self.esc_shortcut = QtWidgets.QShortcut(QtGui.QKeySequence("Esc"), self)
        self.esc_shortcut.activated.connect(self.cypher.stop_speaking)
        
        # Window Draggable Mechanics
        self.oldPos = self.pos()

        # Telemetry Timer (1000ms update rate)
        self.sys_timer = QTimer(self)
        self.sys_timer.timeout.connect(self.update_system_stats)
        self.sys_timer.start(1000) 
        self.update_system_stats()

        # Prompt configuration on startup if Gemini API key is missing
        if not os.getenv("GEMINI_API_KEY"):
            QTimer.singleShot(600, self.open_settings)

    @pyqtSlot(str)
    def on_state_changed(self, state):
        """Dispatches state updates to Arc Reactor, Voice Visualizer, and Mode Pill."""
        self.core.set_state(state)
        self.visualizer.set_state(state)

        if state == "listening":
            self.mode_pill.setText("[ LISTENING ]")
            self.mode_pill.setStyleSheet(f"""
                color: {COLOR_LISTEN};
                background-color: rgba(0, 255, 119, 0.15);
                border: 1px solid {COLOR_LISTEN};
                border-radius: 12px;
                padding: 4px 18px;
                font-family: 'Consolas', monospace;
                font-size: 13px;
                font-weight: bold;
                letter-spacing: 2px;
            """)
        elif state == "processing":
            self.mode_pill.setText("[ PROCESSING ]")
            self.mode_pill.setStyleSheet(f"""
                color: {COLOR_PROCESS};
                background-color: rgba(58, 134, 255, 0.15);
                border: 1px solid {COLOR_PROCESS};
                border-radius: 12px;
                padding: 4px 18px;
                font-family: 'Consolas', monospace;
                font-size: 13px;
                font-weight: bold;
                letter-spacing: 2px;
            """)
        elif state == "speaking":
            self.mode_pill.setText("[ VOCALIZING ]")
            self.mode_pill.setStyleSheet(f"""
                color: {COLOR_SPEAK};
                background-color: rgba(255, 0, 127, 0.15);
                border: 1px solid {COLOR_SPEAK};
                border-radius: 12px;
                padding: 4px 18px;
                font-family: 'Consolas', monospace;
                font-size: 13px;
                font-weight: bold;
                letter-spacing: 2px;
            """)
        else:
            self.mode_pill.setText("[ STANDBY ]" if self.core.is_active else "[ READY ]")
            self.mode_pill.setStyleSheet(f"""
                color: {COLOR_ACCENT};
                background-color: rgba(0, 217, 246, 0.12);
                border: 1px solid {COLOR_ACCENT};
                border-radius: 12px;
                padding: 4px 18px;
                font-family: 'Consolas', monospace;
                font-size: 13px;
                font-weight: bold;
                letter-spacing: 2px;
            """)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.oldPos = event.globalPos()

    def mouseMoveEvent(self, event):
        delta = event.globalPos() - self.oldPos
        self.move(self.x() + delta.x(), self.y() + delta.y())
        self.oldPos = event.globalPos()

    def update_system_stats(self):
        try:
            # 1. CPU & RAM
            cpu = psutil.cpu_percent()
            ram = psutil.virtual_memory().percent
            self.gauge_cpu.set_value(cpu)
            self.gauge_ram.set_value(ram)

            # 2. Battery Status
            battery = psutil.sensors_battery()
            if battery:
                sub = "[CHRG]" if battery.power_plugged else "[DISCHRG]"
                self.gauge_bat.set_value(battery.percent, sub)
            else:
                self.gauge_bat.set_value(100.0, "[AC_PWR]")

            # 3. Network Link Status
            addrs = psutil.net_if_stats()
            connected = any(nic.isup for nic in addrs.values())
            self.row_net_link.set_data("[ONLINE]" if connected else "[OFFLINE]")

            # 4. System Clock & Security
            self.row_clock.set_data(time.strftime("%H:%M:%S"))
            self.row_sec.set_data("ARMED :: ACTIVE")

            # 5. Network Throughput
            curr_net = psutil.net_io_counters()
            recv_speed = max(0.0, (curr_net.bytes_recv - self.last_net.bytes_recv) / 1024.0)
            sent_speed = max(0.0, (curr_net.bytes_sent - self.last_net.bytes_sent) / 1024.0)
            self.last_net = curr_net

            self.row_net_down.set_data(f"↓ {recv_speed:.1f} KB/s")
            self.row_net_up.set_data(f"↑ {sent_speed:.1f} KB/s")

            # 6. Disk & Threads
            disk_usage = psutil.disk_usage(os.getcwd()).percent
            self.gauge_disk.set_value(disk_usage)
            self.row_threads.set_data(f"{threading.active_count()} THREADS")

            # 7. Core & Voice Module Status
            self.row_ai_core.set_data("[ONLINE]" if self.core.is_active else "[STANDBY]")
            self.row_v_mod.set_data("SWARA NEURAL")

        except Exception:
            pass

    def toggle_system(self):
        if not self.core.is_active: 
            self.start_system()
        else: 
            self.stop_system()
            
    def open_settings(self):
        """Opens the Holographic Protocol Configuration / Credentials Vault dialog."""
        dialog = SettingsDialog(self.cypher, self)
        if dialog.exec_() == QtWidgets.QDialog.Accepted:
            self.terminal.log("CREDENTIALS VAULT :: PROTOCOLS UPDATED & SYNCHRONIZED.")

    def start_system(self):
        if self.core.is_active: 
            return
        if hasattr(self, 'ai_thread') and self.ai_thread and self.ai_thread.is_alive():
            self.terminal.log("Waiting for background tasks to terminate...")
            return

        if not os.getenv("GEMINI_API_KEY"):
            self.terminal.log("[SYSTEM ALERT] Gemini API key not configured. Opening credentials vault...")
            self.open_settings()
            return

        self.core.is_active = True
        self.btn_action.setText("TERMINATE SYSTEM")
        self.btn_action.setStyleSheet(f"""
            QPushButton {{
                background-color: rgba(255, 51, 68, 0.2); 
                color: #ff5566; 
                border: 2px solid #ff5566; 
                font-family: '{self.tech_font}'; 
                font-size: 22px; 
                letter-spacing: 3px; 
                border-radius: 12px;
                font-style: italic;
            }}
            QPushButton:hover {{
                background-color: #ff3344;
                color: #ffffff;
            }}
        """)
        
        # Pass callbacks directly to the core instance
        self.cypher.set_callbacks(
            self.update_log_threadsafe, 
            self.request_close_threadsafe, 
            self.update_state_threadsafe
        )
        
        self.on_state_changed("idle")
        self.update_log_threadsafe("Initializing Neural Network...")
        self.ai_thread = threading.Thread(target=self.run_ai)
        self.ai_thread.daemon = True
        self.ai_thread.start()

    def stop_system(self):
        self.cypher.stop_execution()
        self.core.is_active = False
        self.on_state_changed("idle")
        self.btn_action.setText("INITIATE PROTOCOL")
        self.btn_action.setStyleSheet(f"""
            QPushButton {{
                background-color: rgba(0, 217, 246, 0.1); 
                color: {COLOR_ACCENT}; 
                border: 2px solid {COLOR_ACCENT}; 
                font-family: '{self.tech_font}'; 
                font-size: 22px; 
                letter-spacing: 3px; 
                border-radius: 12px;
                font-style: italic;
            }}
            QPushButton:hover {{
                background-color: {COLOR_ACCENT};
                color: {COLOR_BG};
            }}
        """)
        self.terminal.log("System Halted.")

    def run_ai(self):
        try:
            self.cypher.check_env_variable()
            self.cypher.load_memory()
            self.cypher.activate_assistant()
        except Exception as e:
            self.update_log_threadsafe(f"CRITICAL ERROR: {e}")

    def update_log_threadsafe(self, text):
        if self.core.is_active:
            self.sig_log.emit(text)
    
    def request_close_threadsafe(self):
        self.sig_close.emit()
    
    def update_state_threadsafe(self, state):
        if self.core.is_active:
            self.sig_state.emit(state)
    
    @pyqtSlot()
    def close_safely(self):
        if self.core.is_active:
            self.stop_system()
        
        self.terminal.log("Shutdown Sequence Initiated...")
        self.btn_close.setEnabled(False)
        QTimer.singleShot(1000, self.close)


if __name__ == "__main__":
    app = QtWidgets.QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())