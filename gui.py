import sys
import threading
import time
import psutil 
import os
from PyQt5 import QtCore, QtGui, QtWidgets
from PyQt5.QtCore import Qt, QTimer, pyqtSlot, pyqtSignal
import main 

# --- CONFIGURATION ---
COLOR_BG = "#05080d"        # Deep Space Black
COLOR_ACCENT = "#00d9f6"    # Cyan Neon
COLOR_SEC = "#005f7f"       # Dimmer Cyan
COLOR_TEXT = "#ffffff"
COLOR_WARN = "#ff3333"      # Red for Close

# --- CONTEXT COLORS ---
COLOR_LISTEN = "#00ff00"    # Green for Listening
COLOR_PROCESS = "#0088ff"   # Deep Blue for Processing

# --- FONT LOADER ---
def get_font_family(file_name):
    current_dir = os.path.dirname(os.path.abspath(__file__))
    font_path = os.path.join(current_dir, "font", file_name)
    if not os.path.exists(font_path): return "Segoe UI Black"
    font_id = QtGui.QFontDatabase.addApplicationFont(font_path)
    if font_id == -1: return "Segoe UI Black"
    return QtGui.QFontDatabase.applicationFontFamilies(font_id)[0]

class HUDPanel(QtWidgets.QWidget):
    """Side Panels simulating Jarvis Data Streams"""
    def __init__(self, title, font_family, alignment=Qt.AlignLeft, parent=None):
        super().__init__(parent)
        layout = QtWidgets.QVBoxLayout(self)
        self.labels = [] 
        
        # TITLE
        self.title = QtWidgets.QLabel(title)
        self.title.setAlignment(alignment)
        self.title.setStyleSheet(f"""
            color: {COLOR_ACCENT}; 
            font-family: '{font_family}', 'Impact'; 
            font-size: 30px; 
            letter-spacing: 3px; 
            text-transform: uppercase;
            font-style: italic;
        """)
        layout.addWidget(self.title)
        
        # DATA LINES
        for i in range(6):
            lbl = QtWidgets.QLabel(f"INITIALIZING...")
            lbl.setStyleSheet(f"""
                color: rgba(0, 217, 246, 180); 
                font-family: 'Consolas', monospace; 
                font-size: 16px;
                letter-spacing: 1px;
                font-weight: bold;
            """)
            lbl.setAlignment(alignment)
            layout.addWidget(lbl)
            self.labels.append(lbl)
        
        layout.addStretch()

    def update_data(self, data_list):
        for i, text in enumerate(data_list):
            if i < len(self.labels):
                self.labels[i].setText(text)

class RotatingCore(QtWidgets.QWidget):
    """The Centerpiece - Optimized for Low CPU Usage"""
    def __init__(self, image_path="image.png", parent=None):
        super().__init__(parent)
        self.angle_1 = 0
        self.angle_2 = 0
        self.angle_3 = 0
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.animate)
        self.timer.start(20) 
        self.is_active = False 
        self.state = "idle"
        
        # Pulse Effect Variables
        self.pulse_alpha = 50
        self.pulse_dir = 5
        
        self.pixmap = QtGui.QPixmap(image_path)
        if self.pixmap.isNull():
            self.pixmap = QtGui.QPixmap(300, 300)
            self.pixmap.fill(Qt.transparent)
            
        # Cache for the scaled image (Optimization)
        self.cached_pixmap = None 

    def set_state(self, state):
        self.state = state
        self.update()

    def animate(self):
        # Adjusted speeds for smoother animation
        speed = 2
        if self.state == "processing": speed = 8
        elif self.state == "listening": speed = 4
        elif self.is_active: speed = 5
        
        # Pulse Logic (Breathing Effect)
        if self.state == "listening":
            self.pulse_alpha += self.pulse_dir
            if self.pulse_alpha >= 150 or self.pulse_alpha <= 30:
                self.pulse_dir *= -1
        
        self.angle_1 = (self.angle_1 + speed) % 360
        self.angle_2 = (self.angle_2 - (speed * 0.5)) % 360
        self.angle_3 = (self.angle_3 + (speed * 0.2)) % 360
        self.update()

    def resizeEvent(self, event):
        # OPTIMIZATION: Scale the image ONLY when resized, not every frame
        w, h = self.width(), self.height()
        radius = min(w, h) // 2 - 60
        if radius > 0:
            self.cached_pixmap = self.pixmap.scaled(
                radius*2, radius*2, 
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
        radius = min(w, h) // 2 - 60
        if radius <= 0:
            return
        # Color Logic
        if self.state == "listening":
            base_color = QtGui.QColor(COLOR_LISTEN)
            arc_color = QtGui.QColor(0, 255, 0, 200)
            dot_color = QtGui.QColor(0, 255, 0, 100)
        elif self.state == "processing":
            base_color = QtGui.QColor(COLOR_PROCESS)
            arc_color = QtGui.QColor(0, 136, 255, 200)
            dot_color = QtGui.QColor(0, 136, 255, 100)
        else:
            base_color = QtGui.QColor(COLOR_ACCENT)
            arc_color = QtGui.QColor(0, 217, 246, 200)
            dot_color = QtGui.QColor(0, 217, 246, 100)
        
        # IMPROVEMENT: Draw Pulse Effect
        if self.state == "listening":
            painter.save()
            brush_color = QtGui.QColor(COLOR_LISTEN)
            brush_color.setAlpha(self.pulse_alpha)
            painter.setBrush(QtGui.QBrush(brush_color))
            painter.setPen(Qt.NoPen)
            # Draw a glowing circle slightly larger than the core
            painter.drawEllipse(cx - radius - 15, cy - radius - 15, (radius + 15)*2, (radius + 15)*2)
            painter.restore()

        # Optimization: Draw the cached pixmap
        if self.cached_pixmap:
            img_x = cx - self.cached_pixmap.width() // 2
            img_y = cy - self.cached_pixmap.height() // 2
            
            path = QtGui.QPainterPath()
            path.addEllipse(cx - radius + 30, cy - radius + 30, (radius - 30)*2, (radius - 30)*2)
            painter.setClipPath(path)
            painter.drawPixmap(img_x, img_y, self.cached_pixmap)
            painter.setClipping(False)

        # Drawing Arcs
        pen = QtGui.QPen(base_color)
        pen.setWidth(3)
        
        painter.save()
        painter.translate(cx, cy)
        painter.rotate(self.angle_1)
        pen.setColor(arc_color)
        painter.setPen(pen)
        painter.drawArc(QtCore.QRectF(-radius+10, -radius+10, (radius-10)*2, (radius-10)*2), 0, 100 * 16)
        painter.drawArc(QtCore.QRectF(-radius+10, -radius+10, (radius-10)*2, (radius-10)*2), 180 * 16, 100 * 16)
        painter.restore()

        painter.save()
        painter.translate(cx, cy)
        painter.rotate(self.angle_2)
        pen.setColor(dot_color)
        pen.setStyle(Qt.DotLine)
        pen.setWidth(2)
        painter.setPen(pen)
        painter.drawEllipse(QtCore.QRectF(-radius, -radius, radius*2, radius*2))
        painter.restore()
        
        painter.setPen(base_color)
        font = QtGui.QFont("Consolas", 12, QtGui.QFont.Bold)
        font.setLetterSpacing(QtGui.QFont.AbsoluteSpacing, 3)
        painter.setFont(font)
        text_rect = QtCore.QRect(0, cy + radius + 15, w, 30)
        
        status_text = "CORE_ONLINE"
        if self.state == "listening": status_text = "LISTENING..."
        elif self.state == "processing": status_text = "PROCESSING..."
        
        painter.drawText(text_rect, Qt.AlignCenter, status_text)

class TerminalBox(QtWidgets.QTextEdit):
    """Terminal with 'Hacker' Typewriter Effect"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setReadOnly(True)
        self.setStyleSheet(f"""
            QTextEdit {{
                background-color: rgba(0, 0, 0, 0.6);
                color: {COLOR_ACCENT};
                font-family: 'Consolas', monospace;
                font-size: 16px;
                font-weight: bold;
                border: 2px solid {COLOR_SEC};
                border-top: 3px solid {COLOR_ACCENT}; 
            }}
        """)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        
        # --- NEW: Typewriter Logic ---
        self.char_queue = []
        self.type_timer = QTimer(self)
        self.type_timer.timeout.connect(self._process_queue)
        self.type_timer.start(15) # Typing Speed (Lower = Faster)

    @pyqtSlot(str)
    def log(self, text):
        # Add text to queue instead of displaying immediately
        self.char_queue.extend(list(f"> {text.upper()}\n"))

    def _process_queue(self):
        if self.char_queue:
            char = self.char_queue.pop(0)
            self.moveCursor(QtGui.QTextCursor.End)
            self.insertPlainText(char)
            self.verticalScrollBar().setValue(self.verticalScrollBar().maximum())

class MainWindow(QtWidgets.QMainWindow):
    sig_log = pyqtSignal(str)
    sig_close = pyqtSignal()
    sig_state = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self.setWindowFlags(Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.resize(1400, 900)
        self.setWindowTitle("CYPHER VOICE ASSISTANT")
        self.tech_font = get_font_family("WarriotTechItalic-YqOoa.ttf")
        
        self.last_net = psutil.net_io_counters()
        central = QtWidgets.QFrame()
        central.setStyleSheet(f"""
            QFrame {{
                background-color: {COLOR_BG};
                border: 3px solid {COLOR_SEC};
                border-radius: 20px;
            }}
        """)
        self.setCentralWidget(central)
        main_layout = QtWidgets.QVBoxLayout(central)
        main_layout.setContentsMargins(25, 10, 25, 25)

        # --- WINDOW CONTROLS ---
        top_bar = QtWidgets.QHBoxLayout()
        top_bar.addStretch() 

        # Control Panel Frame
        control_frame = QtWidgets.QFrame()
        control_frame.setFixedSize(120, 40)
        control_frame.setStyleSheet(f"""
            QFrame {{
                background-color: rgba(0, 20, 30, 0.8);
                border: 1px solid {COLOR_SEC};
                border-radius: 5px;
            }}
        """)
        ctrl_layout = QtWidgets.QHBoxLayout(control_frame)
        ctrl_layout.setContentsMargins(5, 5, 5, 5)
        ctrl_layout.setSpacing(5)

        # Minimize Button
        self.btn_min = QtWidgets.QPushButton("─")
        self.btn_min.setFixedSize(50, 30)
        self.btn_min.clicked.connect(self.showMinimized)
        self.btn_min.setCursor(Qt.PointingHandCursor)
        self.btn_min.setStyleSheet(f"""
            QPushButton {{
                color: {COLOR_ACCENT};
                background-color: transparent;
                border: 1px solid {COLOR_SEC};
                border-radius: 3px;
                font-weight: bold; font-size: 14px;
            }}
            QPushButton:hover {{
                background-color: rgba(0, 217, 246, 0.3);
                border: 1px solid {COLOR_ACCENT};
                color: #ffffff;
            }}
        """)

        # Close Button
        self.btn_close = QtWidgets.QPushButton("✕")
        self.btn_close.setFixedSize(50, 30)
        self.btn_close.clicked.connect(self.close_safely)
        self.btn_close.setCursor(Qt.PointingHandCursor)
        self.btn_close.setStyleSheet(f"""
            QPushButton {{
                color: {COLOR_WARN};
                background-color: transparent;
                border: 1px solid {COLOR_WARN};
                border-radius: 3px;
                font-weight: bold; font-size: 14px;
            }}
            QPushButton:hover {{
                background-color: {COLOR_WARN};
                color: #ffffff;
                border: 1px solid #ff5555;
            }}
        """)

        ctrl_layout.addWidget(self.btn_min)
        ctrl_layout.addWidget(self.btn_close)
        
        top_bar.addWidget(control_frame)
        main_layout.addLayout(top_bar)

        # --- HEADER ---
        header = QtWidgets.QLabel("CYPHER VOICE ASSISTANT")
        header.setAlignment(Qt.AlignCenter)
        header.setStyleSheet(f"""
            color: {COLOR_ACCENT}; 
            font-family: '{self.tech_font}', 'Arial Black'; 
            font-size: 42px; 
            letter-spacing: 5px; 
            font-weight: 400; 
            border: none;
            font-style: italic;
        """)
        main_layout.addWidget(header)
        
        # --- MIDDLE SECTION ---
        middle_layout = QtWidgets.QHBoxLayout()
        
        self.left_panel = HUDPanel("DIAGNOSTICS", self.tech_font, Qt.AlignLeft)
        self.left_panel.setFixedWidth(400)
        
        img_path = os.path.join(os.path.dirname(__file__), "image.png")
        self.core = RotatingCore(img_path)

        self.core.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Expanding)
        
        self.right_panel = HUDPanel("SYSTEM STATUS", self.tech_font, Qt.AlignRight)
        self.right_panel.setFixedWidth(400)
        
        middle_layout.addWidget(self.left_panel)
        middle_layout.addWidget(self.core, 1) 
        middle_layout.addWidget(self.right_panel)
        main_layout.addLayout(middle_layout)

        # --- BOTTOM SECTION ---
        bottom_layout = QtWidgets.QVBoxLayout()
        lbl_term = QtWidgets.QLabel("COMMAND LINE INTERFACE")
        lbl_term.setStyleSheet(f"color: {COLOR_SEC}; font-family: '{self.tech_font}'; font-size: 16px; letter-spacing: 2px; border:none; font-style: italic;")
        bottom_layout.addWidget(lbl_term)
        
        self.terminal = TerminalBox()
        self.terminal.setFixedHeight(220)
        bottom_layout.addWidget(self.terminal)
        
        self.btn_action = QtWidgets.QPushButton("INITIATE PROTOCOL")
        self.btn_action.setCursor(Qt.PointingHandCursor)
        self.btn_action.setFixedHeight(65)
        self.btn_action.setStyleSheet(f"""
            QPushButton {{
                background-color: rgba(0, 217, 246, 0.1);
                color: {COLOR_ACCENT};
                border: 2px solid {COLOR_ACCENT};
                font-family: '{self.tech_font}'; 
                font-size: 24px; 
                letter-spacing: 2px;
                border-bottom-left-radius: 15px; 
                border-bottom-right-radius: 15px;
                font-style: italic;
            }}
            QPushButton:hover {{ background-color: {COLOR_ACCENT}; color: {COLOR_BG}; }}
        """)
        self.btn_action.clicked.connect(self.toggle_system)
        bottom_layout.addWidget(self.btn_action)
        main_layout.addLayout(bottom_layout)

        # --- SIGNALS & LOGIC ---
        self.sig_log.connect(self.terminal.log)
        self.sig_close.connect(self.close_safely)
        self.sig_state.connect(self.core.set_state)
        
        self.oldPos = self.pos()
        self.sys_timer = QTimer(self)
        self.sys_timer.timeout.connect(self.update_system_stats)
        self.sys_timer.start(1000) 

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.oldPos = event.globalPos()

    def mouseMoveEvent(self, event):
        delta = event.globalPos() - self.oldPos
        self.move(self.x() + delta.x(), self.y() + delta.y())
        self.oldPos = event.globalPos()

    def update_system_stats(self):
        try:
            cpu = psutil.cpu_percent()
            ram = psutil.virtual_memory().percent
            
            battery = psutil.sensors_battery()
            if battery:
                if battery.power_plugged:
                    status = "CHARGING" if battery.percent < 100 else "FULLY CHRG"
                else:
                    status = "DISCHARGING"
                bat_str = f"PWR_STATUS :: {battery.percent}% [{status}]"
            else:
                bat_str = "PWR_STATUS :: AC_CONNECTED"
            
            addrs = psutil.net_if_stats()
            connected = any(nic.isup for nic in addrs.values())
            net_str = f"NET_LINK  :: {'[ONLINE]' if connected else '[OFFLINE]'}"
            time_str = f"SYS_CLOCK :: {time.strftime('%H:%M:%S')}"
            
            self.right_panel.update_data([f"CPU_LOAD  :: {cpu}%", f"MEM_ALLOC :: {ram}%", bat_str, net_str, time_str, "SEC_PROTO :: ACTIVE"])

            curr_net = psutil.net_io_counters()
            recv_speed = (curr_net.bytes_recv - self.last_net.bytes_recv) / 1024 
            sent_speed = (curr_net.bytes_sent - self.last_net.bytes_sent) / 1024 
            self.last_net = curr_net 

            disk_usage = psutil.disk_usage(os.getcwd()).percent
            
            self.left_panel.update_data([
                f"NET_DOWN  :: {recv_speed:.1f} KB/s",
                f"NET_UP    :: {sent_speed:.1f} KB/s",
                f"DISK_USED :: {disk_usage}%",
                f"THRD_CNT  :: {threading.active_count()}",
                "AI_CORE   :: " + ("ONLINE" if self.core.is_active else "STANDBY"),
                "V_MODULE  :: READY"
            ])

        except Exception as e:
            pass

    def toggle_system(self):
        if not self.core.is_active: self.start_system()
        else: self.stop_system()
            
    def start_system(self):
        if self.core.is_active:
            return
        self.core.is_active = True
        self.btn_action.setText("TERMINATE SYSTEM")
        self.btn_action.setStyleSheet(f"""
            background-color: rgba(255, 50, 50, 0.2); color: #ff5555; border: 2px solid #ff5555; font-family: '{self.tech_font}'; font-size: 24px; letter-spacing: 2px; border-bottom-left-radius: 15px; border-bottom-right-radius: 15px; font-style: italic;
        """)
        main.set_ui_callback(self.update_log_threadsafe)
        main.set_close_callback(self.request_close_threadsafe)
        main.set_ui_state_callback(self.update_state_threadsafe)
        
        self.update_log_threadsafe("Initializing Neural Network...")
        t = threading.Thread(target=self.run_ai)
        t.daemon = True
        t.start()
        
    def stop_system(self):
        main.stop_execution()
        self.core.is_active = False
        self.core.set_state("idle")
        self.btn_action.setText("INITIATE PROTOCOL")
        self.btn_action.setStyleSheet(f"""
            background-color: rgba(0, 217, 246, 0.1); color: {COLOR_ACCENT}; border: 2px solid {COLOR_ACCENT}; font-family: '{self.tech_font}'; font-size: 24px; letter-spacing: 2px; border-bottom-left-radius: 15px; border-bottom-right-radius: 15px; font-style: italic;
        """)
        self.update_log_threadsafe("System Halted.")

    def run_ai(self):
        try:
            main.check_env_variable()
            main.activateAssistant()
        except Exception as e:
            self.update_log_threadsafe(f"CRITICAL ERROR: {e}")

    def update_log_threadsafe(self, text):
        self.sig_log.emit(text)
    
    def request_close_threadsafe(self):
        self.sig_close.emit()
    
    def update_state_threadsafe(self, state):
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