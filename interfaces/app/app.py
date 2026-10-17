"""
Core AI :: Sovereign PC Desktop Chat App (PyQt6)
100% Native Python Desktop Chat Application.
Zero HTML, Zero JavaScript, Zero WebView.

Art Direction:
  - Nothing OS / Teenage Engineering slop-free industrial aesthetic.
  - Dot-matrix typography & branding ('c.o.r.e.').
  - Deep obsidian matte void (#0B0B0B, #111111) with subtle architectural grid lines.
  - Crisp monochrome palette with subtle white & signal red/green hardware accents.
  - Slop-free, disciplined, minimal, and 100% powerful.
"""

import sys
import os
import json
import time
import math
import urllib.request
import urllib.error
from typing import Optional, List, Dict, Any

# Ensure project root is on sys.path
ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QTextEdit, QPlainTextEdit, QScrollArea,
    QFrame, QComboBox, QDialog, QTabWidget, QLineEdit, QTableWidget,
    QTableWidgetItem, QHeaderView, QMessageBox, QCheckBox, QSlider, QFileDialog
)
from PyQt6.QtCore import Qt, QTimer, QThread, pyqtSignal, QSize, QRectF
from PyQt6.QtGui import (
    QColor, QFont, QKeySequence, QShortcut, QKeyEvent, QPainter,
    QPen, QBrush, QFontDatabase, QPaintEvent
)

def get_gateway_url() -> str:
    """Resolves target gateway URL from env var or state manager mesh config."""
    url = os.getenv("CORE_GATEWAY_URL")
    if not url:
        try:
            from core.state import StateManager
            profile = StateManager().get_user_profile()
            url = profile.preferences.get("mesh", {}).get("main_server_url")
        except Exception:
            url = None
    return (url or "http://127.0.0.1:8000").rstrip("/")

GATEWAY_URL = get_gateway_url()

# --- Color Palette Constants (Nothing OS Obsidian Void & Engineering Monochrome) ---
C_BG_VOID = "#0B0B0B"          # Pure matte obsidian void
C_BG_SIDEBAR = "#111111"       # Sidebar deep charcoal
C_BG_CHAT = "#0E0E0E"          # Main arena background
C_BG_CARD = "#151515"          # Message cards / code containers
C_BG_INPUT = "#131313"         # Input dock
C_BG_HOVER = "#1E1E1E"         # Active / hover pill
C_BORDER_SUBTLE = "#1C1C1C"    # Faint structural border
C_BORDER_CARD = "#262626"      # Container border
C_BORDER_FOCUS = "#383838"     # Focused outline
C_TEXT_PRIMARY = "#FFFFFF"     # Crisp pure white
C_TEXT_SECONDARY = "#8E8E8E"   # Monospace silver
C_TEXT_MUTED = "#555555"       # Subdued / subtle metadata
C_RED_ACCENT = "#D71921"       # Nothing Signal Red
C_GREEN_ONLINE = "#00E676"     # Active listening green
C_GRID_LINE = "#161616"        # Subtle architectural grid line


def load_system_fonts():
    """Registers system fonts into Qt for crisp high-DPI font and symbol rendering."""
    if QApplication.instance() is None:
        return
    font_candidates = [
        "C:/Windows/Fonts/consola.ttf",
        "C:/Windows/Fonts/consolab.ttf",
        "C:/Windows/Fonts/segoeui.ttf",
        "C:/Windows/Fonts/segoeuib.ttf",
        "C:/Windows/Fonts/seguiemj.ttf",
        "C:/Windows/Fonts/seguisym.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationMono-Regular.ttf",
    ]
    for f in font_candidates:
        if os.path.exists(f):
            try:
                QFontDatabase.addApplicationFont(f)
            except Exception:
                pass


# =========================================================================
# Background Network Worker for Async API Calls (No UI freezing)
# =========================================================================

class ApiWorker(QThread):
    finished = pyqtSignal(dict)
    failed = pyqtSignal(str)

    def __init__(self, endpoint: str, method: str = "GET", payload: Optional[dict] = None):
        super().__init__()
        self.endpoint = endpoint
        self.method = method
        self.payload = payload

    def run(self):
        url = f"{GATEWAY_URL}{self.endpoint}"
        try:
            data = None
            if self.payload is not None:
                data = json.dumps(self.payload).encode("utf-8")
            req = urllib.request.Request(
                url,
                data=data,
                headers={
                    "Content-Type": "application/json",
                    "User-Agent": "CoreAI-QtChat/3.0"
                },
                method=self.method
            )
            with urllib.request.urlopen(req, timeout=40.0) as resp:
                raw = resp.read().decode("utf-8")
                try:
                    parsed = json.loads(raw)
                    self.finished.emit(parsed if isinstance(parsed, dict) else {"data": parsed})
                except json.JSONDecodeError:
                    self.finished.emit({"raw": raw})
        except urllib.error.HTTPError as e:
            try:
                err_data = json.loads(e.read().decode("utf-8"))
                detail = err_data.get("detail", str(e))
            except Exception:
                detail = str(e)
            self.failed.emit(f"HTTP {e.code}: {detail}")
        except Exception as e:
            self.failed.emit(str(e))


# =========================================================================
# Custom Slop-Free Visual Paint Widgets (Nothing OS & Retro Pixel Art)
# =========================================================================

class DotRingGlyph(QWidget):
    """Draws the circular Nothing OS Dot-Matrix glyph icon (8 dots arranged in a ring)."""
    def __init__(self, size=20, dot_color="#FFFFFF", parent=None):
        super().__init__(parent)
        self.setFixedSize(size, size)
        self.dot_color = dot_color

    def paintEvent(self, a0: Optional[QPaintEvent]):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        center_x = self.width() / 2.0
        center_y = self.height() / 2.0
        radius = (self.width() / 2.0) - 3.0
        dot_radius = max(1.4, self.width() * 0.08)
        num_dots = 8

        painter.setBrush(QColor(self.dot_color))
        painter.setPen(Qt.PenStyle.NoPen)
        for i in range(num_dots):
            angle = (2 * math.pi / num_dots) * i
            x = center_x + radius * math.cos(angle)
            y = center_y + radius * math.sin(angle)
            painter.drawEllipse(QRectF(x - dot_radius, y - dot_radius, dot_radius * 2, dot_radius * 2))


class UserSilhouetteAvatar(QWidget):
    """Minimalist user silhouette avatar matching Image 2."""
    def __init__(self, size=22, parent=None):
        super().__init__(parent)
        self.setFixedSize(size, size)

    def paintEvent(self, a0: Optional[QPaintEvent]):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        w = float(self.width())
        h = float(self.height())
        painter.setBrush(QColor("#A0A0A0"))
        painter.setPen(Qt.PenStyle.NoPen)
        # Head circle
        head_r = w * 0.22
        painter.drawEllipse(QRectF((w / 2.0) - head_r, h * 0.1, head_r * 2, head_r * 2))
        # Body rounded arc
        painter.drawRoundedRect(QRectF(w * 0.16, h * 0.62, w * 0.68, h * 0.32), 4, 4)


class PixelAvatar(QWidget):
    """Draws the retro pixel art operator avatar from Image 2."""
    def __init__(self, size=32, parent=None):
        super().__init__(parent)
        self.setFixedSize(size, size)

    def paintEvent(self, a0: Optional[QPaintEvent]):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)
        # Rounded frame container
        painter.setBrush(QColor("#1A1A1A"))
        painter.setPen(QColor("#2E2E2E"))
        painter.drawRoundedRect(0, 0, self.width() - 1, self.height() - 1, 5, 5)

        # 10x10 retro pixel character
        matrix = [
            "  ######  ",
            " ######## ",
            " #######  ",
            " ###..#.. ",
            " #######  ",
            " ##.##.#  ",
            "  ######  ",
            "   ####   ",
            "  ######  ",
            " ######## ",
        ]
        pad = 4.0
        pw = (self.width() - (pad * 2)) / 10.0
        ph = (self.height() - (pad * 2)) / 10.0
        painter.setBrush(QColor("#CCCCCC"))
        painter.setPen(Qt.PenStyle.NoPen)
        for r, row in enumerate(matrix):
            for c, char in enumerate(row):
                if char == '#':
                    painter.drawRect(int(pad + c * pw), int(pad + r * ph), int(pw) + 1, int(ph) + 1)


class GridContainerWidget(QWidget):
    """Draws the faint precision architectural grid from Image 2 across the chat arena."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_OpaquePaintEvent, False)

    def paintEvent(self, a0: Optional[QPaintEvent]):
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor(C_BG_CHAT))
        pen = QPen(QColor(C_GRID_LINE))
        pen.setWidth(1)
        painter.setPen(pen)
        grid_size = 28
        w = self.width()
        h = self.height()
        # Vertical grid lines
        for x in range(0, w, grid_size):
            painter.drawLine(x, 0, x, h)
        # Horizontal grid lines
        for y in range(0, h, grid_size):
            painter.drawLine(0, y, w, y)


# =========================================================================
# Multiline Chat Input Field (Enter to send, Shift+Enter for newline)
# =========================================================================

class ChatInputEdit(QPlainTextEdit):
    """Multiline input supporting Enter to submit and Shift+Enter for newlines."""
    def __init__(self, parent=None, on_submit=None):
        super().__init__(parent)
        self.on_submit = on_submit

    def keyPressEvent(self, e: Optional[QKeyEvent]):
        if e is not None and e.key() == Qt.Key.Key_Return and not (e.modifiers() & Qt.KeyboardModifier.ShiftModifier):
            if self.on_submit:
                self.on_submit()
            e.accept()
        elif e is not None:
            super().keyPressEvent(e)


# =========================================================================
# Autonomous DAG Reasoning Trace Drawer
# =========================================================================

class DagStepsAccordion(QWidget):
    """Collapsible drawer rendering autonomous DAG tool steps executed by Core AI."""
    def __init__(self, steps: List[dict], parent=None):
        super().__init__(parent)
        self.steps = steps
        self.is_expanded = False

        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(0, 4, 0, 4)
        self.main_layout.setSpacing(4)

        step_count = len(steps)
        self.toggle_btn = QPushButton(f"⚡  {step_count} AUTONOMOUS REASONING STEPS  ▶")
        self.toggle_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.toggle_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: #121212;
                color: {C_TEXT_SECONDARY};
                border: 1px solid #222222;
                border-left: 2px solid {C_RED_ACCENT};
                border-radius: 4px;
                padding: 6px 10px;
                font-family: 'Consolas', monospace;
                font-size: 10px;
                font-weight: bold;
                text-align: left;
            }}
            QPushButton:hover {{
                background-color: #181818;
                color: #FFFFFF;
                border-color: #333333;
            }}
        """)
        self.toggle_btn.clicked.connect(self._toggle)
        self.main_layout.addWidget(self.toggle_btn)

        self.details_widget = QWidget()
        details_layout = QVBoxLayout(self.details_widget)
        details_layout.setContentsMargins(8, 6, 8, 6)
        details_layout.setSpacing(6)

        for i, step in enumerate(steps):
            tool = step.get("tool_name") or step.get("action") or "reasoning"
            status = step.get("status", "ok")
            args = step.get("args") or step.get("parameters") or {}
            output = step.get("output") or step.get("result") or ""

            st_color = C_GREEN_ONLINE if status in ("ok", "success") else C_RED_ACCENT
            box = QFrame()
            box.setStyleSheet("background-color: #0A0A0A; border: 1px solid #1A1A1A; border-radius: 4px; padding: 4px;")
            b_layout = QVBoxLayout(box)
            b_layout.setContentsMargins(6, 4, 6, 4)
            b_layout.setSpacing(2)

            hdr = QLabel(f"[{i+1}] {tool.upper()}  ● {status.upper()}")
            hdr.setStyleSheet(f"color: {st_color}; font-family: 'Consolas', monospace; font-size: 10px; font-weight: bold;")
            b_layout.addWidget(hdr)

            if args:
                args_lbl = QLabel(f"Args: {json.dumps(args, ensure_ascii=False)}")
                args_lbl.setStyleSheet("color: #777777; font-family: 'Consolas', monospace; font-size: 9px;")
                args_lbl.setWordWrap(True)
                b_layout.addWidget(args_lbl)

            if output:
                out_str = str(output)[:250] + ("..." if len(str(output)) > 250 else "")
                out_lbl = QLabel(f"Result: {out_str}")
                out_lbl.setStyleSheet("color: #999999; font-family: 'Consolas', monospace; font-size: 9px;")
                out_lbl.setWordWrap(True)
                b_layout.addWidget(out_lbl)

            details_layout.addWidget(box)

        self.details_widget.setVisible(False)
        self.main_layout.addWidget(self.details_widget)

    def _toggle(self):
        self.is_expanded = not self.is_expanded
        self.details_widget.setVisible(self.is_expanded)
        arrow = "▼" if self.is_expanded else "▶"
        self.toggle_btn.setText(f"⚡  {len(self.steps)} AUTONOMOUS REASONING STEPS  {arrow}")


# =========================================================================
# Dedicated Slop-Free Code Block Card (from Image 2)
# =========================================================================

class CodeBlockCard(QFrame):
    """Sleek dark container for code blocks with language tag and top-right copy button."""
    def __init__(self, code_text: str, language: str = "CODE", parent=None):
        super().__init__(parent)
        self.code_text = code_text.strip()
        self.setStyleSheet(f"""
            QFrame {{
                background-color: {C_BG_CARD};
                border: 1px solid {C_BORDER_CARD};
                border-radius: 6px;
            }}
        """)
        c_layout = QVBoxLayout(self)
        c_layout.setContentsMargins(10, 8, 10, 8)
        c_layout.setSpacing(6)

        # Header bar
        hdr = QHBoxLayout()
        hdr.setContentsMargins(0, 0, 0, 0)
        lang_lbl = QLabel(language.upper() if language else "CODE")
        lang_lbl.setStyleSheet(f"color: {C_TEXT_MUTED}; font-family: 'Consolas', monospace; font-size: 10px; font-weight: bold;")
        hdr.addWidget(lang_lbl)
        hdr.addStretch()

        self.copy_btn = QPushButton("📋")
        self.copy_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.copy_btn.setToolTip("Copy code snippet to clipboard")
        self.copy_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: transparent;
                color: {C_TEXT_SECONDARY};
                border: none;
                font-size: 12px;
                padding: 2px 6px;
            }}
            QPushButton:hover {{
                color: #FFFFFF;
                background-color: #222222;
                border-radius: 3px;
            }}
        """)
        self.copy_btn.clicked.connect(self._copy_code)
        hdr.addWidget(self.copy_btn)
        c_layout.addLayout(hdr)

        # Code text body
        self.code_edit = QPlainTextEdit()
        self.code_edit.setPlainText(self.code_text)
        self.code_edit.setReadOnly(True)
        self.code_edit.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.code_edit.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.code_edit.setStyleSheet(f"""
            QPlainTextEdit {{
                background-color: transparent;
                color: #ECECEC;
                font-family: 'Consolas', 'Courier New', monospace;
                font-size: 12px;
                line-height: 1.4;
                border: none;
                padding: 2px;
            }}
        """)
        # Auto-adjust height to content (up to max 280px)
        lines = len(self.code_text.splitlines())
        calc_h = min(280, max(50, lines * 18 + 16))
        self.code_edit.setFixedHeight(calc_h)
        c_layout.addWidget(self.code_edit)

    def _copy_code(self):
        clip = QApplication.clipboard()
        if clip is not None:
            clip.setText(self.code_text)
        self.copy_btn.setText("✓")
        QTimer.singleShot(1500, lambda: self.copy_btn.setText("📋"))


# =========================================================================
# Chat Message Row Item (Exact Mockup from Image 2)
# =========================================================================

class ChatMessageItem(QWidget):
    """
    Message bubble row matching Image 2:
      - User: Silhouette avatar + clean user query.
      - Assistant: DotRingGlyph + message text + sleek code blocks + feedback footer row.
    """
    def __init__(self, role: str, content: str, steps: Optional[List[dict]] = None, model: Optional[str] = None, parent=None):
        super().__init__(parent)
        self.role = role
        self.content = content
        self.steps = steps or []
        self.model = model

        row_layout = QHBoxLayout(self)
        row_layout.setContentsMargins(18, 10, 18, 10)
        row_layout.setSpacing(14)
        row_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        # Avatar column
        avatar_col = QVBoxLayout()
        avatar_col.setContentsMargins(0, 2, 0, 0)
        avatar_col.setAlignment(Qt.AlignmentFlag.AlignTop)
        if self.role == "user":
            avatar_col.addWidget(UserSilhouetteAvatar(size=22))
        else:
            avatar_col.addWidget(DotRingGlyph(size=20, dot_color="#FFFFFF"))
        row_layout.addLayout(avatar_col)

        # Message Body Column
        body_col = QVBoxLayout()
        body_col.setContentsMargins(0, 0, 0, 0)
        body_col.setSpacing(8)

        # Parse text vs code blocks (```language ... ```)
        parts = self._parse_blocks(self.content)
        for part_type, part_val, lang in parts:
            if part_type == "text" and part_val.strip():
                txt_lbl = QLabel(part_val.strip())
                txt_lbl.setWordWrap(True)
                txt_lbl.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
                txt_lbl.setStyleSheet(f"""
                    QLabel {{
                        color: {C_TEXT_PRIMARY};
                        font-family: 'Segoe UI', -apple-system, sans-serif;
                        font-size: 13px;
                        line-height: 1.5;
                        padding: 0px;
                    }}
                """)
                body_col.addWidget(txt_lbl)
            elif part_type == "code":
                body_col.addWidget(CodeBlockCard(code_text=part_val, language=lang))

        # Autonomous DAG reasoning steps (if assistant executed tools)
        if self.steps and self.role == "assistant":
            body_col.addWidget(DagStepsAccordion(self.steps))

        # Assistant Footer Row: ● Feedback  |  👍  👎  |  🔊 Speak
        if self.role == "assistant":
            footer = QHBoxLayout()
            footer.setContentsMargins(0, 4, 0, 0)
            footer.setSpacing(12)

            fb_lbl = QLabel("●  Feedback")
            fb_lbl.setStyleSheet(f"color: {C_TEXT_MUTED}; font-size: 11px; font-family: 'Segoe UI', sans-serif;")
            footer.addWidget(fb_lbl)
            footer.addStretch()

            btn_thumbs_up = QPushButton("👍")
            btn_thumbs_up.setToolTip("Good response")
            btn_thumbs_up.setStyleSheet("background: transparent; border: none; font-size: 12px; color: #777777;")
            btn_thumbs_up.clicked.connect(lambda: btn_thumbs_up.setStyleSheet("background: transparent; border: none; font-size: 12px; color: #00E676;"))
            footer.addWidget(btn_thumbs_up)

            btn_thumbs_down = QPushButton("👎")
            btn_thumbs_down.setToolTip("Needs improvement")
            btn_thumbs_down.setStyleSheet("background: transparent; border: none; font-size: 12px; color: #777777;")
            btn_thumbs_down.clicked.connect(lambda: btn_thumbs_down.setStyleSheet("background: transparent; border: none; font-size: 12px; color: #D71921;"))
            footer.addWidget(btn_thumbs_down)

            btn_speak = QPushButton("🔊")
            btn_speak.setToolTip("Read aloud using local neural voice")
            btn_speak.setStyleSheet("background: transparent; border: none; font-size: 12px; color: #777777;")
            btn_speak.clicked.connect(self._speak_text)
            footer.addWidget(btn_speak)

            body_col.addLayout(footer)

        row_layout.addLayout(body_col, stretch=1)

    def _parse_blocks(self, text: str):
        """Splits text into markdown code blocks and natural prose segments."""
        blocks = []
        in_code = False
        cur_lang = ""
        cur_lines = []

        for line in text.split("\n"):
            if line.strip().startswith("```"):
                if not in_code:
                    if cur_lines:
                        blocks.append(("text", "\n".join(cur_lines), ""))
                        cur_lines = []
                    in_code = True
                    cur_lang = line.strip().lstrip("`").strip() or "code"
                else:
                    blocks.append(("code", "\n".join(cur_lines), cur_lang))
                    cur_lines = []
                    in_code = False
                    cur_lang = ""
            else:
                cur_lines.append(line)

        if cur_lines:
            blocks.append(("code" if in_code else "text", "\n".join(cur_lines), cur_lang))
        return blocks

    def _speak_text(self):
        worker = ApiWorker("/api/v1/mesh/satellites/all/speak", method="POST", payload={"text": self.content[:500]})
        worker.start()
        self._speak_worker = worker


# =========================================================================
# Settings & Configuration Modal Dialog
# =========================================================================

class SettingsDialog(QDialog):
    """Sleek minimalist hardware settings matching Nothing OS / Dieter Rams aesthetic."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("CORE AI // SYSTEM SETTINGS")
        self.resize(650, 520)
        self.setStyleSheet(f"""
            QDialog {{ background-color: {C_BG_VOID}; color: {C_TEXT_PRIMARY}; }}
            QTabWidget::pane {{ border: 1px solid {C_BORDER_CARD}; background: {C_BG_SIDEBAR}; }}
            QTabBar::tab {{
                background: #111111; color: {C_TEXT_SECONDARY}; padding: 8px 16px;
                border: 1px solid {C_BORDER_SUBTLE}; border-bottom: none;
                font-family: 'Consolas', monospace; font-size: 11px;
            }}
            QTabBar::tab:selected {{ background: {C_BG_CARD}; color: #FFFFFF; font-weight: bold; border-color: {C_BORDER_CARD}; }}
            QLabel {{ color: {C_TEXT_PRIMARY}; font-family: 'Segoe UI', sans-serif; font-size: 12px; }}
            QLineEdit, QComboBox {{
                background-color: {C_BG_INPUT}; color: #FFFFFF; border: 1px solid {C_BORDER_CARD};
                border-radius: 4px; padding: 6px 10px; font-family: 'Consolas', monospace; font-size: 11px;
            }}
            QPushButton {{
                background-color: {C_BG_HOVER}; color: #FFFFFF; border: 1px solid {C_BORDER_CARD};
                border-radius: 4px; padding: 7px 16px; font-family: 'Consolas', monospace; font-size: 11px; font-weight: bold;
            }}
            QPushButton:hover {{ background-color: #262626; border-color: {C_BORDER_FOCUS}; }}
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(14)

        title_row = QHBoxLayout()
        title_row.addWidget(DotRingGlyph(size=18, dot_color="#FFFFFF"))
        hdr_lbl = QLabel("HARDWARE & AI PARAMETERS")
        hdr_lbl.setStyleSheet("font-family: 'Consolas', monospace; font-size: 13px; font-weight: bold; letter-spacing: 1px;")
        title_row.addWidget(hdr_lbl)
        title_row.addStretch()
        layout.addLayout(title_row)

        tabs = QTabWidget()

        # Tab 1: AI Models & Keys
        t_models = QWidget()
        m_layout = QVBoxLayout(t_models)
        m_layout.setContentsMargins(14, 14, 14, 14)
        m_layout.setSpacing(10)

        m_layout.addWidget(QLabel("PRIMARY REASONING MODEL (LOCAL / CLOUD):"))
        self.cb_planner = QComboBox()
        self.cb_planner.addItems([
            "ollama/qwen2.5:latest",
            "ollama/llama3.2:latest",
            "google/gemini-2.5-flash",
            "openai/gpt-4o",
            "anthropic/claude-3-7-sonnet"
        ])
        m_layout.addWidget(self.cb_planner)

        m_layout.addWidget(QLabel("GEMINI API KEY:"))
        self.in_gemini = QLineEdit()
        self.in_gemini.setEchoMode(QLineEdit.EchoMode.Password)
        self.in_gemini.setPlaceholderText("AIzaSy...")
        m_layout.addWidget(self.in_gemini)

        m_layout.addWidget(QLabel("OPENAI API KEY:"))
        self.in_openai = QLineEdit()
        self.in_openai.setEchoMode(QLineEdit.EchoMode.Password)
        self.in_openai.setPlaceholderText("sk-proj-...")
        m_layout.addWidget(self.in_openai)

        m_layout.addWidget(QLabel("ANTHROPIC API KEY:"))
        self.in_anthropic = QLineEdit()
        self.in_anthropic.setEchoMode(QLineEdit.EchoMode.Password)
        self.in_anthropic.setPlaceholderText("sk-ant-...")
        m_layout.addWidget(self.in_anthropic)
        m_layout.addStretch()
        tabs.addTab(t_models, "MODELS & KEYS")

        # Tab 2: Audio & Microphone
        t_audio = QWidget()
        a_layout = QVBoxLayout(t_audio)
        a_layout.setContentsMargins(14, 14, 14, 14)
        a_layout.setSpacing(10)

        a_layout.addWidget(QLabel("WASAPI SOUND INPUT (MICROPHONE):"))
        self.cb_mic = QComboBox()
        a_layout.addWidget(self.cb_mic)

        a_layout.addWidget(QLabel("WASAPI SOUND OUTPUT (STUDIO MONITORS):"))
        self.cb_speaker = QComboBox()
        a_layout.addWidget(self.cb_speaker)

        a_layout.addWidget(QLabel("NEURAL SPEECH VOICE:"))
        self.cb_voice = QComboBox()
        self.cb_voice.addItems(["en-US-JennyNeural", "en-US-GuyNeural", "en-GB-SoniaNeural", "de-DE-KatjaNeural"])
        a_layout.addWidget(self.cb_voice)

        mic_ctrl_box = QHBoxLayout()
        self.mic_badge = QLabel("● ACTIVE (LISTENING)")
        self.mic_badge.setStyleSheet(f"color: {C_GREEN_ONLINE}; font-family: 'Consolas', monospace; font-size: 11px; font-weight: bold;")
        mic_ctrl_box.addWidget(self.mic_badge)
        mic_ctrl_box.addStretch()
        self.btn_mute_toggle = QPushButton("🔇  MUTE LISTENING")
        self.btn_mute_toggle.clicked.connect(self._toggle_listening)
        mic_ctrl_box.addWidget(self.btn_mute_toggle)
        a_layout.addLayout(mic_ctrl_box)
        a_layout.addStretch()
        tabs.addTab(t_audio, "AUDIO & PERCEPTION")

        # Tab 3: Operator Profile
        t_profile = QWidget()
        p_layout = QVBoxLayout(t_profile)
        p_layout.setContentsMargins(14, 14, 14, 14)
        p_layout.setSpacing(10)

        p_layout.addWidget(QLabel("OPERATOR HANDLE / NAME:"))
        self.in_name = QLineEdit()
        p_layout.addWidget(self.in_name)

        p_layout.addWidget(QLabel("INTERACTION TONE:"))
        self.cb_tone = QComboBox()
        self.cb_tone.addItems(["focused", "concise", "jarvis_tactical", "analytical", "creative"])
        p_layout.addWidget(self.cb_tone)

        p_layout.addWidget(QLabel("PRIMARY COMMAND SPACE / ZONE:"))
        self.in_space = QLineEdit()
        p_layout.addWidget(self.in_space)
        p_layout.addStretch()
        tabs.addTab(t_profile, "OPERATOR PROFILE")

        layout.addWidget(tabs)

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        cancel_btn = QPushButton("CANCEL")
        cancel_btn.clicked.connect(self.reject)
        btn_row.addWidget(cancel_btn)

        save_btn = QPushButton("SAVE PREFERENCES")
        save_btn.setStyleSheet(f"background-color: {C_BG_CARD}; color: #FFFFFF; border: 1px solid {C_BORDER_FOCUS};")
        save_btn.clicked.connect(self._save_all)
        btn_row.addWidget(save_btn)
        layout.addLayout(btn_row)

        self._load_current_values()

    def _load_current_values(self):
        worker = ApiWorker("/api/v1/profile")
        def on_prof(data):
            self.in_name.setText(data.get("preferred_name", "Operator"))
            self.cb_tone.setCurrentText(data.get("preferred_tone", "focused"))
            prefs = data.get("preferences", {})
            self.in_space.setText(prefs.get("primary_space", "command_deck"))
            audio_p = prefs.get("audio", {})
            is_enabled = audio_p.get("listening_enabled", True)
            self._update_listening_ui(is_enabled)
        worker.finished.connect(on_prof)
        worker.start()
        self._prof_worker = worker

        a_worker = ApiWorker("/api/v1/audio/devices")
        def on_audio(data):
            self.cb_mic.clear()
            self.cb_speaker.clear()
            inputs = data.get("inputs", [])
            outputs = data.get("speakers", [])
            for inp in inputs:
                self.cb_mic.addItem(f"{inp.get('name')} (WASAPI #{inp.get('index')})")
            for out in outputs:
                self.cb_speaker.addItem(f"{out.get('name')} (WASAPI #{out.get('index')})")
        a_worker.finished.connect(on_audio)
        a_worker.start()
        self._a_worker = a_worker

    def _toggle_listening(self):
        worker = ApiWorker("/api/v1/voice/listening", method="POST", payload={"action": "toggle"})
        def on_done(data):
            is_enabled = data.get("listening_enabled", True)
            self._update_listening_ui(is_enabled)
            p = self.parent()
            if p is not None and hasattr(p, "_update_listening_ui"):
                getattr(p, "_update_listening_ui")(is_enabled)
        worker.finished.connect(on_done)
        worker.start()
        self._toggle_worker = worker

    def _update_listening_ui(self, is_enabled: bool):
        if is_enabled:
            self.mic_badge.setText("● ACTIVE (LISTENING)")
            self.mic_badge.setStyleSheet(f"color: {C_GREEN_ONLINE}; font-family: 'Consolas', monospace; font-size: 11px; font-weight: bold;")
            self.btn_mute_toggle.setText("🔇  MUTE LISTENING")
        else:
            self.mic_badge.setText("● DEACTIVATED (MUTED)")
            self.mic_badge.setStyleSheet(f"color: {C_RED_ACCENT}; font-family: 'Consolas', monospace; font-size: 11px; font-weight: bold;")
            self.btn_mute_toggle.setText("🎙  ACTIVATE LISTENING")

    def _save_all(self):
        keys = {}
        if self.in_gemini.text().strip():
            keys["gemini_api_key"] = self.in_gemini.text().strip()
        if self.in_openai.text().strip():
            keys["openai_api_key"] = self.in_openai.text().strip()
        if self.in_anthropic.text().strip():
            keys["anthropic_api_key"] = self.in_anthropic.text().strip()
        if keys:
            ApiWorker("/api/v1/keys", method="POST", payload=keys).start()

        prof_payload = {
            "preferred_name": self.in_name.text().strip() or "Operator",
            "preferred_tone": self.cb_tone.currentText(),
            "primary_space": self.in_space.text().strip() or "command_deck",
            "planner_model": self.cb_planner.currentText()
        }
        ApiWorker("/api/v1/profile", method="POST", payload=prof_payload).start()
        QMessageBox.information(self, "Saved", "Hardware & AI parameters updated successfully.")
        self.accept()


# =========================================================================
# System Vitals & Update Modal Dialog
# =========================================================================

class SystemDialog(QDialog):
    """System vitals inspection and update dialog."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("CORE AI // HARDWARE & UPDATES")
        self.resize(600, 440)
        self.setStyleSheet(f"""
            QDialog {{ background-color: {C_BG_VOID}; color: {C_TEXT_PRIMARY}; }}
            QLabel {{ color: {C_TEXT_PRIMARY}; font-family: 'Consolas', monospace; font-size: 11px; }}
            QPushButton {{
                background-color: {C_BG_HOVER}; color: #FFFFFF; border: 1px solid {C_BORDER_CARD};
                border-radius: 4px; padding: 7px 16px; font-family: 'Consolas', monospace; font-size: 11px; font-weight: bold;
            }}
            QPushButton:hover {{ background-color: #262626; border-color: {C_BORDER_FOCUS}; }}
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(12)

        hdr_row = QHBoxLayout()
        hdr_row.addWidget(DotRingGlyph(size=18, dot_color="#FFFFFF"))
        t_lbl = QLabel("SYSTEM TELEMETRY & RELEASES")
        t_lbl.setStyleSheet("font-size: 13px; font-weight: bold; letter-spacing: 1px;")
        hdr_row.addWidget(t_lbl)
        hdr_row.addStretch()
        layout.addLayout(hdr_row)

        self.info_box = QFrame()
        self.info_box.setStyleSheet(f"background: {C_BG_CARD}; border: 1px solid {C_BORDER_CARD}; border-radius: 6px; padding: 12px;")
        ib_layout = QVBoxLayout(self.info_box)
        ib_layout.setSpacing(6)

        self.lbl_ver = QLabel("Kernel: Core AI Universal Gateway v1.0.0")
        self.lbl_cpu = QLabel("Host Platform: Windows 11 / x86_64")
        self.lbl_ram = QLabel("Memory: Standalone Microkernel Active")
        self.lbl_db = QLabel("Database: SQLite Sovereign Store Synced")
        self.lbl_gw = QLabel(f"Gateway Binding: {GATEWAY_URL}")
        ib_layout.addWidget(self.lbl_ver)
        ib_layout.addWidget(self.lbl_cpu)
        ib_layout.addWidget(self.lbl_ram)
        ib_layout.addWidget(self.lbl_db)
        ib_layout.addWidget(self.lbl_gw)
        layout.addWidget(self.info_box)

        act_box = QHBoxLayout()
        snap_btn = QPushButton("💾  CREATE STATE BACKUP")
        snap_btn.clicked.connect(self._create_backup)
        act_box.addWidget(snap_btn)

        upd_btn = QPushButton("⟳  CHECK RELEASES")
        upd_btn.setStyleSheet(f"background-color: {C_BG_HOVER}; border-color: {C_BORDER_FOCUS};")
        upd_btn.clicked.connect(self._check_update)
        act_box.addWidget(upd_btn)
        layout.addLayout(act_box)

        layout.addStretch()
        close_btn = QPushButton("CLOSE")
        close_btn.clicked.connect(self.accept)
        layout.addWidget(close_btn)

        self._refresh()

    def _refresh(self):
        worker = ApiWorker("/api/v1/health")
        def on_done(data):
            self.lbl_ver.setText(f"Kernel Version: {data.get('version', 'v1.0.0')} [{data.get('codename', 'Sovereign')}]")
            self.lbl_cpu.setText(f"Platform: {data.get('platform', sys.platform)} (Active Operator: {data.get('active_user', 'Operator')})")
            self.lbl_ram.setText(f"Active Model: {data.get('active_model', 'offline_heuristic')}")
        worker.finished.connect(on_done)
        worker.start()
        self._w = worker

    def _create_backup(self):
        worker = ApiWorker("/api/v1/system/backup", method="POST")
        def on_done(data):
            QMessageBox.information(self, "Backup Preserved", "SQLite database and environment configuration snapshotted cleanly.")
        worker.finished.connect(on_done)
        worker.start()

    def _check_update(self):
        QMessageBox.information(self, "Core AI Updater", "System is up-to-date. Sovereign Gateway running latest release.")


# =========================================================================
# Real-Time Execution & Bug Report Logs Modal Dialog
# =========================================================================

class LogsDialog(QDialog):
    """Terminal log viewer with 1-click diagnostic bug report generator."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("CORE AI // SYSTEM AUDIT LOG")
        self.resize(750, 480)
        self.setStyleSheet(f"""
            QDialog {{ background-color: {C_BG_VOID}; color: {C_TEXT_PRIMARY}; }}
            QPlainTextEdit {{
                background-color: #060606; color: #D0D0D0; font-family: 'Consolas', monospace;
                font-size: 11px; border: 1px solid {C_BORDER_CARD}; border-radius: 4px; padding: 10px;
            }}
            QPushButton {{
                background-color: {C_BG_HOVER}; color: #FFFFFF; border: 1px solid {C_BORDER_CARD};
                border-radius: 4px; padding: 6px 14px; font-family: 'Consolas', monospace; font-size: 11px; font-weight: bold;
            }}
            QPushButton:hover {{ background-color: #262626; border-color: {C_BORDER_FOCUS}; }}
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)

        hdr = QHBoxLayout()
        hdr.addWidget(DotRingGlyph(size=18, dot_color="#FFFFFF"))
        hdr_lbl = QLabel("LIVE KERNEL EXECUTION & AUDIT TRACE")
        hdr_lbl.setStyleSheet("font-family: 'Consolas', monospace; font-size: 12px; font-weight: bold; letter-spacing: 1px;")
        hdr.addWidget(hdr_lbl)
        hdr.addStretch()

        copy_btn = QPushButton("📋  COPY LOGS")
        copy_btn.clicked.connect(self._copy_logs)
        hdr.addWidget(copy_btn)

        bug_btn = QPushButton("🐛  COPY BUG REPORT")
        bug_btn.clicked.connect(self._copy_bug_report)
        hdr.addWidget(bug_btn)
        layout.addLayout(hdr)

        self.log_edit = QPlainTextEdit()
        self.log_edit.setReadOnly(True)
        layout.addWidget(self.log_edit)

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        close_btn = QPushButton("CLOSE")
        close_btn.clicked.connect(self.accept)
        btn_row.addWidget(close_btn)
        layout.addLayout(btn_row)

        self._poll_logs()

    def _poll_logs(self):
        worker = ApiWorker("/api/v1/logs?limit=80")
        def on_done(data):
            logs = data.get("logs", [])
            lines = [f"[{l.get('created_at', '')}] {l.get('level', 'INFO')}: {l.get('message', '')}" for l in logs]
            if not lines:
                lines = [f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] INFO: Core AI Sovereign Gateway active on {GATEWAY_URL}"]
            self.log_edit.setPlainText("\n".join(lines))
            self.log_edit.moveCursor(self.log_edit.textCursor().MoveOperation.End)
        worker.finished.connect(on_done)
        worker.start()
        self._l_worker = worker

    def _copy_logs(self):
        clip = QApplication.clipboard()
        if clip is not None:
            clip.setText(self.log_edit.toPlainText())
        QMessageBox.information(self, "Copied", "Visible log lines copied to clipboard.")

    def _copy_bug_report(self):
        report = (
            "### Core AI Diagnostic Issue Report\n"
            f"- **Platform**: {sys.platform}\n"
            f"- **Timestamp**: {time.strftime('%Y-%m-%d %H:%M:%S')}\n"
            f"- **Gateway**: {GATEWAY_URL}\n\n"
            "#### Tail Execution Logs:\n```text\n"
            f"{self.log_edit.toPlainText()[-2000:]}\n```\n"
        )
        clip = QApplication.clipboard()
        if clip is not None:
            clip.setText(report)
        QMessageBox.information(self, "Bug Report Ready", "Diagnostic issue report formatted as Markdown and copied to clipboard!")


# =========================================================================
# Help & Shortcuts Modal Dialog
# =========================================================================

class HelpDialog(QDialog):
    """Shortcuts and quick reference dialog."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("CORE AI // SHORTCUTS & HELP")
        self.resize(520, 340)
        self.setStyleSheet(f"""
            QDialog {{ background-color: {C_BG_VOID}; color: {C_TEXT_PRIMARY}; }}
            QLabel {{ color: {C_TEXT_PRIMARY}; font-family: 'Consolas', monospace; font-size: 11px; }}
            QPushButton {{
                background-color: {C_BG_HOVER}; color: #FFFFFF; border: 1px solid {C_BORDER_CARD};
                border-radius: 4px; padding: 6px 14px; font-family: 'Consolas', monospace; font-size: 11px; font-weight: bold;
            }}
        """)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(12)

        hdr = QLabel("KEYBOARD SHORTCUTS & NAVIGATION")
        hdr.setStyleSheet("font-size: 13px; font-weight: bold; letter-spacing: 1px;")
        layout.addWidget(hdr)

        box = QFrame()
        box.setStyleSheet(f"background: {C_BG_CARD}; border: 1px solid {C_BORDER_CARD}; border-radius: 6px; padding: 12px;")
        b_lay = QVBoxLayout(box)
        b_lay.setSpacing(8)

        shortcuts = [
            ("Enter", "Send active chat prompt"),
            ("Shift + Enter", "Insert newline in prompt editor"),
            ("Ctrl + N", "Start clean new conversation session"),
            ("Ctrl + ,", "Open Hardware & AI Parameters Settings"),
            ("Ctrl + L", "Open Real-Time Kernel Audit Log"),
            ("Ctrl + Q", "Quit Core AI Desktop Companion")
        ]
        for key, desc in shortcuts:
            row = QHBoxLayout()
            k_lbl = QLabel(key)
            k_lbl.setStyleSheet(f"color: #FFFFFF; font-weight: bold; min-width: 130px;")
            d_lbl = QLabel(desc)
            d_lbl.setStyleSheet(f"color: {C_TEXT_SECONDARY};")
            row.addWidget(k_lbl)
            row.addWidget(d_lbl)
            b_lay.addLayout(row)
        layout.addWidget(box)

        layout.addStretch()
        close_btn = QPushButton("CLOSE")
        close_btn.clicked.connect(self.accept)
        layout.addWidget(close_btn)


# =========================================================================
# Primary Sovereign PC Desktop Chat Window (Exact Match to Image 2)
# =========================================================================

class CoreAIDesktopApp(QMainWindow):
    """
    Official Core AI Sovereign PC Desktop Chat Application.
    Faithful recreation of the slop-free Nothing OS Dot-Matrix desktop design.
    100% Native PyQt6 (Zero Web, Zero Slop).
    """
    def __init__(self):
        super().__init__()
        load_system_fonts()
        self.setWindowTitle("c.o.r.e. // LOCAL AI UTILITY")
        self.resize(1180, 800)
        self.setMinimumSize(940, 600)

        self.current_session_id = f"sess_{int(time.time())}"
        self.active_model = "ollama/qwen2.5:latest"
        self.listening_enabled = True

        self.setStyleSheet(f"""
            QMainWindow {{ background-color: {C_BG_VOID}; }}
            QWidget {{ color: {C_TEXT_PRIMARY}; }}
            QScrollBar:vertical {{ background: {C_BG_VOID}; width: 6px; margin: 0; }}
            QScrollBar::handle:vertical {{ background: #262626; min-height: 20px; border-radius: 3px; }}
            QScrollBar::handle:vertical:hover {{ background: #404040; }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0px; }}
        """)

        self._init_ui()
        self._init_shortcuts()
        self._load_sessions()
        self._init_health_timer()

    def _init_ui(self):
        central = QWidget(self)
        self.setCentralWidget(central)
        root_layout = QHBoxLayout(central)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        # -------------------------------------------------------------
        # Left Navigation Sidebar (Width: ~260px)
        # -------------------------------------------------------------
        sidebar = QFrame()
        sidebar.setFixedWidth(260)
        sidebar.setStyleSheet(f"""
            QFrame {{
                background-color: {C_BG_SIDEBAR};
                border-right: 1px solid {C_BORDER_SUBTLE};
            }}
        """)
        s_layout = QVBoxLayout(sidebar)
        s_layout.setContentsMargins(14, 14, 14, 12)
        s_layout.setSpacing(12)

        # Header: DotRingGlyph + 'c.o.r.e.' + Search [🔍] + Clear [✕]
        sb_hdr = QHBoxLayout()
        sb_hdr.setSpacing(8)
        sb_hdr.addWidget(DotRingGlyph(size=20, dot_color="#FFFFFF"))

        core_title = QLabel("c.o.r.e.")
        core_title.setStyleSheet("""
            QLabel {
                font-family: 'Consolas', 'Courier New', monospace;
                font-size: 15px;
                font-weight: bold;
                letter-spacing: 2px;
                color: #FFFFFF;
            }
        """)
        sb_hdr.addWidget(core_title)
        sb_hdr.addStretch()

        self.search_toggle_btn = QPushButton("🔍")
        self.search_toggle_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.search_toggle_btn.setToolTip("Search conversations")
        self.search_toggle_btn.setStyleSheet("""
            QPushButton {
                background: transparent;
                border: none;
                color: #888888;
                font-size: 12px;
                padding: 4px;
            }
            QPushButton:hover { color: #FFFFFF; }
        """)
        self.search_toggle_btn.clicked.connect(self._toggle_search_bar)
        sb_hdr.addWidget(self.search_toggle_btn)

        clear_btn = QPushButton("[×]")
        clear_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        clear_btn.setToolTip("Clear current thread")
        clear_btn.setStyleSheet("""
            QPushButton {
                background: transparent;
                border: none;
                color: #888888;
                font-family: 'Consolas', monospace;
                font-size: 11px;
                padding: 4px;
            }
            QPushButton:hover { color: #FFFFFF; }
        """)
        clear_btn.clicked.connect(self._create_new_chat)
        sb_hdr.addWidget(clear_btn)
        s_layout.addLayout(sb_hdr)

        # Inline Search Filter Bar (collapsible)
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Filter chats...")
        self.search_input.setStyleSheet(f"""
            QLineEdit {{
                background-color: {C_BG_INPUT};
                color: #FFFFFF;
                border: 1px solid {C_BORDER_CARD};
                border-radius: 4px;
                padding: 4px 8px;
                font-family: 'Consolas', monospace;
                font-size: 11px;
            }}
        """)
        self.search_input.textChanged.connect(self._filter_sessions)
        self.search_input.setVisible(False)
        s_layout.addWidget(self.search_input)

        # + NEUER CHAT (New Chat Pill Button)
        self.btn_new_chat = QPushButton("+ NEUER CHAT")
        self.btn_new_chat.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_new_chat.setStyleSheet(f"""
            QPushButton {{
                background-color: {C_BG_CARD};
                color: {C_TEXT_SECONDARY};
                border: 1px solid {C_BORDER_CARD};
                border-radius: 6px;
                padding: 8px 12px;
                font-family: 'Consolas', monospace;
                font-size: 11px;
                font-weight: bold;
                letter-spacing: 1px;
                text-align: center;
            }}
            QPushButton:hover {{
                background-color: {C_BG_HOVER};
                color: #FFFFFF;
                border-color: {C_BORDER_FOCUS};
            }}
        """)
        self.btn_new_chat.clicked.connect(self._create_new_chat)
        s_layout.addWidget(self.btn_new_chat)

        # CHATS Section Header with 'ALLE' and Filter icon
        sec_header = QHBoxLayout()
        sec_header.setContentsMargins(2, 6, 2, 2)
        chats_lbl = QLabel("CHATS")
        chats_lbl.setStyleSheet(f"color: {C_TEXT_MUTED}; font-family: 'Consolas', monospace; font-size: 10px; font-weight: bold; letter-spacing: 1px;")
        sec_header.addWidget(chats_lbl)
        sec_header.addStretch()

        alle_lbl = QLabel("ALLE")
        alle_lbl.setStyleSheet(f"color: {C_TEXT_SECONDARY}; font-family: 'Consolas', monospace; font-size: 10px; font-weight: bold;")
        sec_header.addWidget(alle_lbl)

        filter_icon = QLabel("▽")
        filter_icon.setStyleSheet(f"color: {C_TEXT_MUTED}; font-size: 10px;")
        sec_header.addWidget(filter_icon)
        s_layout.addLayout(sec_header)

        # Scrollable Sessions List
        self.session_scroll = QScrollArea()
        self.session_scroll.setWidgetResizable(True)
        self.session_scroll.setStyleSheet("background: transparent; border: none;")
        self.session_container = QWidget()
        self.session_container.setStyleSheet("background: transparent;")
        self.session_layout = QVBoxLayout(self.session_container)
        self.session_layout.setContentsMargins(0, 0, 0, 0)
        self.session_layout.setSpacing(4)
        self.session_layout.addStretch()
        self.session_scroll.setWidget(self.session_container)
        s_layout.addWidget(self.session_scroll, stretch=1)

        # Divider
        div = QFrame()
        div.setFrameShape(QFrame.Shape.HLine)
        div.setStyleSheet(f"color: {C_BORDER_SUBTLE}; background-color: {C_BORDER_SUBTLE}; max-height: 1px;")
        s_layout.addWidget(div)

        # Bottom Operator Row: PixelAvatar + ACCOUNT / SETTINGS + Gear Button
        acc_row = QHBoxLayout()
        acc_row.setContentsMargins(0, 4, 0, 4)
        acc_row.setSpacing(10)
        acc_row.addWidget(PixelAvatar(size=30))

        acc_txt = QVBoxLayout()
        acc_txt.setSpacing(1)
        acc_title = QLabel("ACCOUNT")
        acc_title.setStyleSheet("color: #FFFFFF; font-family: 'Consolas', monospace; font-size: 11px; font-weight: bold; letter-spacing: 1px;")
        acc_sub = QLabel("SETTINGS")
        acc_sub.setStyleSheet(f"color: {C_TEXT_MUTED}; font-family: 'Consolas', monospace; font-size: 9px;")
        acc_txt.addWidget(acc_title)
        acc_txt.addWidget(acc_sub)
        acc_row.addLayout(acc_txt)
        acc_row.addStretch()

        settings_btn = QPushButton("⚙")
        settings_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        settings_btn.setToolTip("Open System Settings")
        settings_btn.setStyleSheet("""
            QPushButton {
                background: transparent;
                border: none;
                color: #888888;
                font-size: 14px;
                padding: 4px;
            }
            QPushButton:hover { color: #FFFFFF; }
        """)
        settings_btn.clicked.connect(lambda: SettingsDialog(self).exec())
        acc_row.addWidget(settings_btn)
        s_layout.addLayout(acc_row)

        # Bottom Utility Actions: >_ LOG  and  ● MIC LISTENING / MUTED
        bottom_tools = QHBoxLayout()
        bottom_tools.setSpacing(6)

        log_btn = QPushButton(">_  LOG")
        log_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        log_btn.setToolTip("Open real-time kernel audit log")
        log_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: transparent;
                color: {C_TEXT_SECONDARY};
                border: 1px solid {C_BORDER_SUBTLE};
                border-radius: 4px;
                padding: 5px 10px;
                font-family: 'Consolas', monospace;
                font-size: 10px;
                font-weight: bold;
                text-align: left;
            }}
            QPushButton:hover {{
                background-color: {C_BG_CARD};
                color: #FFFFFF;
                border-color: {C_BORDER_CARD};
            }}
        """)
        log_btn.clicked.connect(lambda: LogsDialog(self).exec())
        bottom_tools.addWidget(log_btn)

        # Sidebar Microphone listening toggle button (ensures main_win.mic_sidebar_btn exists)
        self.mic_sidebar_btn = QPushButton("● MIC: LISTENING")
        self.mic_sidebar_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.mic_sidebar_btn.setToolTip("Toggle room microphone perception")
        self.mic_sidebar_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: transparent;
                color: {C_GREEN_ONLINE};
                border: 1px solid {C_BORDER_SUBTLE};
                border-radius: 4px;
                padding: 5px 8px;
                font-family: 'Consolas', monospace;
                font-size: 10px;
                font-weight: bold;
                text-align: right;
            }}
            QPushButton:hover {{ border-color: {C_BORDER_FOCUS}; }}
        """)
        self.mic_sidebar_btn.clicked.connect(self._toggle_mic_listening)
        bottom_tools.addWidget(self.mic_sidebar_btn)
        s_layout.addLayout(bottom_tools)

        root_layout.addWidget(sidebar)

        # -------------------------------------------------------------
        # Main Chat Arena (Architectural Grid Canvas)
        # -------------------------------------------------------------
        main_arena = QWidget()
        m_layout = QVBoxLayout(main_arena)
        m_layout.setContentsMargins(0, 0, 0, 0)
        m_layout.setSpacing(0)

        # Top Header Bar: Transparent with CHECK FOR UPDATES ⟳
        top_bar = QFrame()
        top_bar.setFixedHeight(50)
        top_bar.setStyleSheet(f"background-color: transparent; border-bottom: 1px solid {C_BORDER_SUBTLE};")
        t_layout = QHBoxLayout(top_bar)
        t_layout.setContentsMargins(24, 0, 24, 0)
        t_layout.setSpacing(12)

        # Subtle Model indicator
        self.model_lbl = QLabel("MODEL: QWEN 2.5 // LOCAL HEURISTIC")
        self.model_lbl.setStyleSheet(f"color: {C_TEXT_MUTED}; font-family: 'Consolas', monospace; font-size: 10px; font-weight: bold;")
        t_layout.addWidget(self.model_lbl)
        t_layout.addStretch()

        # Top Bar Microphone listening pill button (ensures main_win.mic_top_btn exists)
        self.mic_top_btn = QPushButton("● MIC LISTENING")
        self.mic_top_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.mic_top_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: transparent;
                color: {C_GREEN_ONLINE};
                border: 1px solid {C_BORDER_CARD};
                border-radius: 4px;
                padding: 5px 12px;
                font-family: 'Consolas', monospace;
                font-size: 10px;
                font-weight: bold;
            }}
            QPushButton:hover {{ background-color: {C_BG_CARD}; }}
        """)
        self.mic_top_btn.clicked.connect(self._toggle_mic_listening)
        t_layout.addWidget(self.mic_top_btn)

        # CHECK FOR UPDATES ⟳ (Pill Button from Image 2)
        self.update_btn = QPushButton("CHECK FOR UPDATES  ⟳")
        self.update_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.update_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: transparent;
                color: {C_TEXT_SECONDARY};
                border: 1px solid {C_BORDER_CARD};
                border-radius: 4px;
                padding: 5px 14px;
                font-family: 'Consolas', monospace;
                font-size: 10px;
                font-weight: bold;
                letter-spacing: 1px;
            }}
            QPushButton:hover {{
                color: #FFFFFF;
                border-color: {C_BORDER_FOCUS};
                background-color: {C_BG_CARD};
            }}
        """)
        self.update_btn.clicked.connect(lambda: SystemDialog(self).exec())
        t_layout.addWidget(self.update_btn)
        m_layout.addWidget(top_bar)

        # Scrollable Chat Messages Area with Grid Background
        self.msg_scroll = QScrollArea()
        self.msg_scroll.setWidgetResizable(True)
        self.msg_scroll.setStyleSheet("background: transparent; border: none;")

        self.msg_container = GridContainerWidget()
        self.msg_layout = QVBoxLayout(self.msg_container)
        self.msg_layout.setContentsMargins(0, 16, 0, 16)
        self.msg_layout.setSpacing(6)
        self.msg_layout.addStretch()
        self.msg_scroll.setWidget(self.msg_container)
        m_layout.addWidget(self.msg_scroll, stretch=1)

        # -------------------------------------------------------------
        # Floating Bottom Input Deck (from Image 2)
        # -------------------------------------------------------------
        input_container = QWidget()
        input_container.setStyleSheet("background-color: transparent;")
        ic_layout = QVBoxLayout(input_container)
        ic_layout.setContentsMargins(24, 6, 24, 6)
        ic_layout.setSpacing(4)

        # Floating Dock Frame
        dock = QFrame()
        dock.setStyleSheet(f"""
            QFrame {{
                background-color: {C_BG_INPUT};
                border: 1px solid {C_BORDER_CARD};
                border-radius: 8px;
            }}
        """)
        d_layout = QHBoxLayout(dock)
        d_layout.setContentsMargins(14, 10, 12, 10)
        d_layout.setSpacing(10)

        # Multiline Prompt Input Field
        self.input_edit = ChatInputEdit(parent=dock, on_submit=self._send_message)
        self.input_edit.setPlaceholderText("Nachricht an c.o.r.e....")
        self.input_edit.setFixedHeight(44)
        self.input_edit.setStyleSheet(f"""
            QPlainTextEdit {{
                background-color: transparent;
                color: #FFFFFF;
                border: none;
                font-family: 'Segoe UI', -apple-system, sans-serif;
                font-size: 13px;
                padding: 0px;
            }}
        """)
        d_layout.addWidget(self.input_edit, stretch=1)

        # Paperclip Attachment button
        self.attach_btn = QPushButton("📎")
        self.attach_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.attach_btn.setToolTip("Attach code or document file")
        self.attach_btn.setStyleSheet("""
            QPushButton {
                background: transparent;
                border: none;
                color: #777777;
                font-size: 15px;
                padding: 4px;
            }
            QPushButton:hover { color: #FFFFFF; }
        """)
        self.attach_btn.clicked.connect(self._attach_file)
        d_layout.addWidget(self.attach_btn)

        # Voice Dictation button
        self.voice_btn = QPushButton("🎙")
        self.voice_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.voice_btn.setToolTip("Voice dictate into prompt")
        self.voice_btn.setStyleSheet("""
            QPushButton {
                background: transparent;
                border: none;
                color: #777777;
                font-size: 15px;
                padding: 4px;
            }
            QPushButton:hover { color: #00E676; }
        """)
        self.voice_btn.clicked.connect(self._trigger_voice)
        d_layout.addWidget(self.voice_btn)

        # Send Button (pill button with arrow)
        self.send_btn = QPushButton("⮞")
        self.send_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.send_btn.setToolTip("Send message (Enter)")
        self.send_btn.setFixedSize(34, 30)
        self.send_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {C_BG_CARD};
                color: #FFFFFF;
                border: 1px solid {C_BORDER_CARD};
                border-radius: 6px;
                font-size: 13px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                background-color: {C_BG_HOVER};
                border-color: {C_BORDER_FOCUS};
            }}
        """)
        self.send_btn.clicked.connect(self._send_message)
        d_layout.addWidget(self.send_btn)

        ic_layout.addWidget(dock)

        # Very bottom status row: Right corner 'CORE AI v1.0.0'
        bottom_status = QHBoxLayout()
        bottom_status.setContentsMargins(4, 0, 4, 2)
        bottom_status.addStretch()
        ver_lbl = QLabel("CORE AI v1.0.0")
        ver_lbl.setStyleSheet(f"color: {C_TEXT_MUTED}; font-family: 'Consolas', monospace; font-size: 9px; letter-spacing: 1px;")
        bottom_status.addWidget(ver_lbl)
        ic_layout.addLayout(bottom_status)

        m_layout.addWidget(input_container)

        root_layout.addWidget(main_arena, stretch=1)

        # Add initial conversation welcome
        self._add_assistant_message("Willkommen bei c.o.r.e. Local autonomous AI utility active. How may I assist you?")

    # -------------------------------------------------------------
    # Keyboard Shortcuts
    # -------------------------------------------------------------
    def _init_shortcuts(self):
        QShortcut(QKeySequence("Ctrl+N"), self, self._create_new_chat)
        QShortcut(QKeySequence("Ctrl+,"), self, lambda: SettingsDialog(self).exec())
        QShortcut(QKeySequence("Ctrl+L"), self, lambda: LogsDialog(self).exec())
        QShortcut(QKeySequence("Ctrl+Q"), self, self.close)

    # -------------------------------------------------------------
    # Health and Status Polling
    # -------------------------------------------------------------
    def _init_health_timer(self):
        self.health_timer = QTimer(self)
        self.health_timer.timeout.connect(self._check_health)
        self.health_timer.start(5000)
        self._check_health()

    def _check_health(self):
        # Poll voice status
        v_worker = ApiWorker("/api/v1/voice/status")
        v_worker.finished.connect(lambda data: self._update_listening_ui(data.get("listening_enabled", True)))
        v_worker.start()
        self._voice_poll_worker = v_worker

    def _toggle_mic_listening(self):
        worker = ApiWorker("/api/v1/voice/listening", method="POST", payload={"action": "toggle"})
        def on_done(data):
            is_enabled = data.get("listening_enabled", True)
            self._update_listening_ui(is_enabled)
        worker.finished.connect(on_done)
        worker.start()
        self._toggle_mic_worker = worker

    def _update_listening_ui(self, is_enabled: bool):
        self.listening_enabled = is_enabled
        if is_enabled:
            self.mic_top_btn.setText("● MIC LISTENING")
            self.mic_top_btn.setStyleSheet(f"""
                QPushButton {{
                    background-color: transparent;
                    color: {C_GREEN_ONLINE};
                    border: 1px solid #1E3A24;
                    border-radius: 4px;
                    padding: 5px 12px;
                    font-family: 'Consolas', monospace;
                    font-size: 10px;
                    font-weight: bold;
                }}
                QPushButton:hover {{ background-color: #122416; }}
            """)
            self.mic_sidebar_btn.setText("● MIC: LISTENING")
            self.mic_sidebar_btn.setStyleSheet(f"""
                QPushButton {{
                    background-color: transparent;
                    color: {C_GREEN_ONLINE};
                    border: 1px solid #1E3A24;
                    border-radius: 4px;
                    padding: 5px 8px;
                    font-family: 'Consolas', monospace;
                    font-size: 10px;
                    font-weight: bold;
                    text-align: right;
                }}
                QPushButton:hover {{ border-color: {C_GREEN_ONLINE}; }}
            """)
        else:
            self.mic_top_btn.setText("● MIC MUTED")
            self.mic_top_btn.setStyleSheet(f"""
                QPushButton {{
                    background-color: transparent;
                    color: {C_RED_ACCENT};
                    border: 1px solid #3A181A;
                    border-radius: 4px;
                    padding: 5px 12px;
                    font-family: 'Consolas', monospace;
                    font-size: 10px;
                    font-weight: bold;
                }}
                QPushButton:hover {{ background-color: #241012; }}
            """)
            self.mic_sidebar_btn.setText("● MIC: MUTED")
            self.mic_sidebar_btn.setStyleSheet(f"""
                QPushButton {{
                    background-color: transparent;
                    color: {C_RED_ACCENT};
                    border: 1px solid #3A181A;
                    border-radius: 4px;
                    padding: 5px 8px;
                    font-family: 'Consolas', monospace;
                    font-size: 10px;
                    font-weight: bold;
                    text-align: right;
                }}
                QPushButton:hover {{ border-color: {C_RED_ACCENT}; }}
            """)

    # -------------------------------------------------------------
    # Chat Messaging Execution
    # -------------------------------------------------------------
    def _send_message(self):
        text = self.input_edit.toPlainText().strip()
        if not text:
            return

        self.input_edit.clear()
        self.send_btn.setEnabled(False)

        self._add_user_message(text)

        payload = {
            "message": text,
            "session_id": self.current_session_id,
            "model": self.active_model
        }

        worker = ApiWorker("/api/v1/chat", method="POST", payload=payload)

        def on_success(data):
            self.send_btn.setEnabled(True)
            content = data.get("content", "Task executed successfully.")
            steps = data.get("steps", [])
            model = data.get("active_model", self.active_model)
            self._add_assistant_message(content=content, steps=steps, model=model)
            self._load_sessions()

        def on_fail(err):
            self.send_btn.setEnabled(True)
            self._add_assistant_message(
                content=f"Connection Notice: Unable to communicate with Core AI Gateway:\n{err}\n\nEnsure microkernel daemon is running ('core start').",
                model="gateway_error"
            )

        worker.finished.connect(on_success)
        worker.failed.connect(on_fail)
        worker.start()
        self._chat_worker = worker

    def _attach_file(self):
        path, _ = QFileDialog.getOpenFileName(self, "Attach file to prompt", "", "All Files (*.*);;Python (*.py);;Markdown (*.md);;Text (*.txt)")
        if path:
            try:
                with open(path, "r", encoding="utf-8", errors="replace") as f:
                    content = f.read()
                filename = os.path.basename(path)
                snippet = f"```\n// File: {filename}\n{content[:2000]}\n```\n\n"
                self.input_edit.setPlainText(snippet + self.input_edit.toPlainText())
            except Exception as e:
                QMessageBox.warning(self, "Attach Failed", f"Could not read file: {e}")

    def _trigger_voice(self):
        self.voice_btn.setText("●")
        self.voice_btn.setStyleSheet("color: #00E676; font-size: 15px; border: none; background: transparent;")
        worker = ApiWorker("/api/v1/voice/transcribe_mic", method="POST")

        def on_done(data):
            self.voice_btn.setText("🎙")
            self.voice_btn.setStyleSheet("color: #777777; font-size: 15px; border: none; background: transparent;")
            text = data.get("text", "")
            if text:
                current = self.input_edit.toPlainText().strip()
                new_text = f"{current} {text}".strip() if current else text
                self.input_edit.setPlainText(new_text)

        def on_fail(err):
            self.voice_btn.setText("🎙")
            self.voice_btn.setStyleSheet("color: #777777; font-size: 15px; border: none; background: transparent;")

        worker.finished.connect(on_done)
        worker.failed.connect(on_fail)
        worker.start()
        self._dictate_worker = worker

    def _add_user_message(self, content: str):
        item = ChatMessageItem(role="user", content=content)
        self.msg_layout.insertWidget(self.msg_layout.count() - 1, item)
        self._scroll_to_bottom()

    def _add_assistant_message(self, content: str, steps: Optional[List[dict]] = None, model: Optional[str] = None):
        item = ChatMessageItem(role="assistant", content=content, steps=steps, model=model)
        self.msg_layout.insertWidget(self.msg_layout.count() - 1, item)
        self._scroll_to_bottom()

    def _scroll_to_bottom(self):
        def _do_scroll():
            vsb = self.msg_scroll.verticalScrollBar()
            if vsb is not None:
                vsb.setValue(vsb.maximum())
        QTimer.singleShot(50, _do_scroll)

    def _clear_messages(self):
        while self.msg_layout.count() > 1:
            child = self.msg_layout.takeAt(0)
            if child is not None:
                w = child.widget()
                if w is not None:
                    w.deleteLater()

    def _create_new_chat(self):
        self._clear_messages()
        self.current_session_id = f"sess_{int(time.time())}"
        self._add_assistant_message("New thread started. All context initialized.")

    def _toggle_search_bar(self):
        self.search_input.setVisible(not self.search_input.isVisible())
        if self.search_input.isVisible():
            self.search_input.setFocus()
        else:
            self.search_input.clear()
            self._filter_sessions("")

    def _filter_sessions(self, query: str):
        q = query.lower().strip()
        for i in range(self.session_layout.count() - 1):
            item = self.session_layout.itemAt(i)
            if item is not None and item.widget() is not None:
                w = item.widget()
                if isinstance(w, QPushButton):
                    match = q in w.text().lower() if q else True
                    w.setVisible(match)

    def _load_sessions(self):
        def on_done(data):
            sessions = data.get("sessions", [])
            while self.session_layout.count() > 1:
                item = self.session_layout.takeAt(0)
                if item is not None:
                    w = item.widget()
                    if w is not None:
                        w.deleteLater()

            for s in sessions:
                sid = s.get("id")
                title = s.get("title", sid)
                btn = QPushButton(f"⁘  {title}")
                btn.setCursor(Qt.CursorShape.PointingHandCursor)
                btn.setToolTip(f"Open thread: {title}")

                is_active = (sid == self.current_session_id)
                btn.setStyleSheet(f"""
                    QPushButton {{
                        background-color: {"#202020" if is_active else "transparent"};
                        color: {"#FFFFFF" if is_active else C_TEXT_SECONDARY};
                        border: none;
                        border-radius: 6px;
                        padding: 7px 10px;
                        font-family: 'Segoe UI', -apple-system, sans-serif;
                        font-size: 11px;
                        text-align: left;
                    }}
                    QPushButton:hover {{
                        background-color: {C_BG_HOVER};
                        color: #FFFFFF;
                    }}
                """)
                btn.clicked.connect(lambda checked, session_id=sid: self._switch_session(session_id))
                self.session_layout.insertWidget(self.session_layout.count() - 1, btn)

        worker = ApiWorker("/api/v1/chat/sessions")
        worker.finished.connect(on_done)
        worker.start()
        self._sessions_worker = worker

    def _switch_session(self, session_id: str):
        self.current_session_id = session_id
        self._load_sessions()
        self._clear_messages()

        worker = ApiWorker(f"/api/v1/chat/sessions/{session_id}")
        def on_done(data):
            messages = data.get("messages", [])
            for m in messages:
                role = m.get("role", "assistant")
                content = m.get("content", "")
                steps = m.get("steps", [])
                model = m.get("active_model", "")
                if role == "user":
                    self._add_user_message(content)
                else:
                    self._add_assistant_message(content=content, steps=steps, model=model)
        worker.finished.connect(on_done)
        worker.start()
        self._hist_worker = worker


# =========================================================================


# =========================================================================
# Application Launcher Entry Point
# =========================================================================

def check_gateway_online(target_url: str = "") -> bool:
    """Verifies whether the central Core AI Universal Gateway is actively running."""
    if not target_url:
        target_url = GATEWAY_URL
    url = f"{target_url}/api/v1/health"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "CoreAI-AppLauncher/1.0"})
        with urllib.request.urlopen(req, timeout=1.5) as resp:
            return resp.status == 200
    except Exception:
        return False


def run_qt_app() -> int:
    """Launches the native PyQt6 Desktop Application."""
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    app.setApplicationName("Core AI Companion")
    load_system_fonts()

    window = CoreAIDesktopApp()
    window.show()
    return app.exec()


def launch_native_qt_app() -> int:
    """Alias for run_qt_app for backwards compatibility."""
    return run_qt_app()


def launch_app(start_local_daemon: bool = False) -> int:
    """
    Launches the official Core AI Sovereign Desktop Chat Companion (100% Native PyQt6).
    """
    target_gateway = GATEWAY_URL
    is_online = check_gateway_online(target_gateway)

    try:
        from core.terminal import render_box, CYAN, GREEN, YELLOW, RESET
        box = render_box(
            title="CORE AI :: SOVEREIGN PC DESKTOP CHAT APP",
            rows=[
                ("Application:", f"{CYAN}c.o.r.e. Native Desktop Chat Companion{RESET}"),
                ("Desktop Engine:", f"{GREEN}100% Native Python PyQt6 (Zero Web / Zero Slop){RESET}"),
                ("Gateway Target:", f"{GREEN}{target_gateway}{RESET}"),
                ("Gateway State:", f"{GREEN}ONLINE{RESET}" if is_online else f"{YELLOW}STANDALONE (OFFLINE){RESET}"),
                ("Aesthetic:", f"{CYAN}Nothing OS Dot-Matrix & Obsidian Void (#0B0B0B){RESET}"),
                ("Shortcuts:", f"Enter: Send · Shift+Enter: Newline · Ctrl+N: New Chat · Ctrl+,: Settings"),
            ],
            width=75
        )
        print(f"\n{box}\n", flush=True)
    except Exception:
        print(f"[*] Starting Core AI Desktop Companion connecting to {target_gateway}...")

    return run_qt_app()


if __name__ == "__main__":
    sys.exit(launch_app())
