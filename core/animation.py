"""
Core AI - Sovereign 3D Terminal Animation Engine
Renders real-time mathematical 3D wireframe geometry, gyroscopic reactor rings,
4D hypercubes (tesseracts), and depth-shaded volumetric holograms into the 2D terminal space.
Supports 24-bit TrueColor, dynamic depth Z-buffering, and interactive real-time controls.
"""

import math
import os
import sys
import time
import shutil
from typing import List, Tuple, Optional, Dict, Any, Callable

# Windows UTF-8 console output setup
if sys.platform == "win32":
    try:
        if hasattr(sys.stdout, "reconfigure"):
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    try:
        import colorama
        colorama.init()
    except ImportError:
        os.system("")

# ANSI escape sequences
ESC = "\033"
CLEAR_SCREEN = f"{ESC}[2J"
CURSOR_HOME = f"{ESC}[H"
HIDE_CURSOR = f"{ESC}[?25l"
SHOW_CURSOR = f"{ESC}[?25h"
RESET_STYLE = f"{ESC}[0m"
BOLD = f"{ESC}[1m"
DIM = f"{ESC}[2m"

# Depth luminance ramp (far to near)
LUMINANCE_RAMP = " .·:;=+*#%@"


def rgb(r: int, g: int, b: int) -> str:
    """Return 24-bit TrueColor ANSI foreground escape sequence."""
    return f"{ESC}[38;2;{max(0, min(255, int(r)))};{max(0, min(255, int(g)))};{max(0, min(255, int(b)))}m"


def rgb_bg(r: int, g: int, b: int) -> str:
    """Return 24-bit TrueColor ANSI background escape sequence."""
    return f"{ESC}[48;2;{max(0, min(255, int(r)))};{max(0, min(255, int(g)))};{max(0, min(255, int(b)))}m"


# Color Themes
THEMES = {
    "cyan": {
        "name": "Cyber Cyan",
        "primary": (0, 245, 255),      # Neon electric cyan
        "secondary": (0, 110, 210),    # Cobalt blue
        "tertiary": (140, 40, 255),    # Cyber violet
        "core": (255, 255, 255),        # Pure white highlight
        "ambient": (0, 70, 120),
        "banner": (0, 230, 255)
    },
    "violet": {
        "name": "Sovereign Void",
        "primary": (225, 40, 220),     # Hot magenta
        "secondary": (110, 20, 180),   # Deep violet
        "tertiary": (255, 200, 40),    # Imperial gold
        "core": (255, 255, 255),
        "ambient": (70, 15, 110),
        "banner": (240, 60, 230)
    },
    "emerald": {
        "name": "Matrix Emerald",
        "primary": (0, 255, 120),      # Phosphor mint
        "secondary": (0, 160, 70),     # Terminal green
        "tertiary": (40, 220, 240),    # Ice teal
        "core": (240, 255, 240),
        "ambient": (10, 70, 35),
        "banner": (0, 255, 130)
    },
    "solar": {
        "name": "Solar Flare",
        "primary": (255, 165, 0),      # Radiant amber
        "secondary": (230, 60, 20),    # Crimson flare
        "tertiary": (255, 235, 60),    # Solar gold
        "core": (255, 255, 240),
        "ambient": (90, 35, 10),
        "banner": (255, 175, 20)
    },
    "monochrome": {
        "name": "Hyper Steel",
        "primary": (220, 230, 240),    # Bright silver
        "secondary": (120, 135, 150),  # Steel gray
        "tertiary": (180, 200, 220),   # Platinum
        "core": (255, 255, 255),
        "ambient": (50, 60, 70),
        "banner": (230, 240, 250)
    }
}


class FrameBuffer:
    """2D character and color buffer with float depth (Z-buffer) for terminal rasterization."""

    def __init__(self, width: int, height: int):
        self.width = width
        self.height = height
        self.chars = [[" " for _ in range(width)] for _ in range(height)]
        self.colors = [["" for _ in range(width)] for _ in range(height)]
        self.z_buffer = [[-float("inf") for _ in range(width)] for _ in range(height)]

    def clear(self):
        for y in range(self.height):
            for x in range(self.width):
                self.chars[y][x] = " "
                self.colors[y][x] = ""
                self.z_buffer[y][x] = -float("inf")

    def set_pixel(self, x: int, y: int, z: float, char: str, color_code: str):
        if 0 <= x < self.width and 0 <= y < self.height:
            if z > self.z_buffer[y][x]:
                self.z_buffer[y][x] = z
                self.chars[y][x] = char
                self.colors[y][x] = color_code

    def render(self) -> str:
        lines = []
        for y in range(self.height):
            line_parts = []
            cur_color = ""
            for x in range(self.width):
                color = self.colors[y][x]
                char = self.chars[y][x]
                if color != cur_color:
                    line_parts.append(color if color else RESET_STYLE)
                    cur_color = color
                line_parts.append(char)
            if cur_color:
                line_parts.append(RESET_STYLE)
            lines.append("".join(line_parts))
        return "\n".join(lines)


class Core3DRenderer:
    """
    Renders 3D wireframe models in 2D terminal space with perspective projection,
    depth buffering, dynamic lighting, and orbital particle trails.
    """

    def __init__(self, width: int = 80, height: int = 26, theme_name: str = "cyan", model_type: str = "core"):
        self.width = max(50, width)
        self.height = max(18, height)
        self.buffer = FrameBuffer(self.width, self.height)
        self.theme_name = theme_name if theme_name in THEMES else "cyan"
        self.model_type = model_type  # "core", "tesseract", "monolith"

        # Aspect ratio correction: terminal characters are ~2x taller than wide
        self.aspect_ratio = 2.15
        self.camera_dist = 3.65
        self.fov = 17.5

        # Manual rotation offsets for interactive mode
        self.manual_pitch = 0.0
        self.manual_yaw = 0.0

        # Model 1: Core Polyhedron (Octahedral double-pyramid crystal)
        self.core_vertices = [
            (0.0, 1.15, 0.0),    # Top apex
            (0.0, -1.15, 0.0),   # Bottom apex
            (0.95, 0.0, 0.0),    # Equator +X
            (-0.95, 0.0, 0.0),   # Equator -X
            (0.0, 0.0, 0.95),    # Equator +Z
            (0.0, 0.0, -0.95),   # Equator -Z
        ]
        self.core_edges = [
            (0, 2), (0, 3), (0, 4), (0, 5),
            (1, 2), (1, 3), (1, 4), (1, 5),
            (2, 4), (4, 3), (3, 5), (5, 2)
        ]

        # Inner pulsing nucleus (cube)
        s = 0.42
        self.nucleus_vertices = [
            (-s, -s, -s), (s, -s, -s), (s, s, -s), (-s, s, -s),
            (-s, -s, s), (s, -s, s), (s, s, s), (-s, s, s)
        ]
        self.nucleus_edges = [
            (0, 1), (1, 2), (2, 3), (3, 0),
            (4, 5), (5, 6), (6, 7), (7, 4),
            (0, 4), (1, 5), (2, 6), (3, 7)
        ]

        # Model 2: 4D Hypercube / Tesseract (16 vertices, 32 edges)
        self.tesseract_vertices = []
        for i in range(16):
            x = 1.0 if (i & 1) else -1.0
            y = 1.0 if (i & 2) else -1.0
            z = 1.0 if (i & 4) else -1.0
            w = 1.0 if (i & 8) else -1.0
            self.tesseract_vertices.append((x * 0.72, y * 0.72, z * 0.72, w * 0.72))

        self.tesseract_edges = []
        for i in range(16):
            for bit in (1, 2, 4, 8):
                j = i ^ bit
                if i < j:
                    self.tesseract_edges.append((i, j))

        # Model 3: Hexagonal Sovereign Monolith
        self.monolith_vertices = []
        hex_r = 1.2
        depth_h = 0.5
        for z in (-depth_h, depth_h):
            for i in range(6):
                ang = i * (math.pi / 3.0)
                hx = hex_r * math.cos(ang)
                hy = hex_r * math.sin(ang)
                self.monolith_vertices.append((hx, hy, z))
        # Center core points for monolith
        self.monolith_vertices.append((0.0, 0.0, -depth_h * 1.5))
        self.monolith_vertices.append((0.0, 0.0, depth_h * 1.5))

        self.monolith_edges = []
        # Front & back hex perimeters
        for layer in (0, 6):
            for i in range(6):
                self.monolith_edges.append((layer + i, layer + (i + 1) % 6))
        # Connecting side ribs
        for i in range(6):
            self.monolith_edges.append((i, i + 6))
        # Spire connections to center
        for i in range(6):
            self.monolith_edges.append((i, 12))
            self.monolith_edges.append((i + 6, 13))

        # Precompute parametric ring geometry
        self.ring_steps = 72
        self.ring1_radius = 2.05
        self.ring2_radius = 1.72
        self.ring3_radius = 1.40

    def get_theme(self) -> Dict[str, Any]:
        return THEMES.get(self.theme_name, THEMES["cyan"])

    def cycle_theme(self) -> str:
        keys = list(THEMES.keys())
        idx = (keys.index(self.theme_name) + 1) % len(keys)
        self.theme_name = keys[idx]
        return THEMES[self.theme_name]["name"]

    def cycle_model(self) -> str:
        models = ["core", "tesseract", "monolith"]
        idx = (models.index(self.model_type) + 1) % len(models)
        self.model_type = models[idx]
        names = {
            "core": "Quantum Gyroscopic Core",
            "tesseract": "4D Hypercube Tesseract",
            "monolith": "Hexagonal Sovereign Monolith"
        }
        return names.get(self.model_type, self.model_type)

    def rotate_point(self, x: float, y: float, z: float, roll: float, pitch: float, yaw: float) -> Tuple[float, float, float]:
        """Rotate point around X, Y, and Z axes."""
        # Pitch (X axis)
        c, s = math.cos(pitch), math.sin(pitch)
        y, z = y * c - z * s, y * s + z * c

        # Yaw (Y axis)
        c, s = math.cos(yaw), math.sin(yaw)
        x, z = x * c + z * s, -x * s + z * c

        # Roll (Z axis)
        c, s = math.cos(roll), math.sin(roll)
        x, y = x * c - y * s, x * s + y * c

        return x, y, z

    def project_point(self, x: float, y: float, z: float, center_x: float, center_y: float) -> Tuple[int, int, float, bool]:
        """Project 3D point to 2D screen coordinates with perspective division."""
        z_eff = z + self.camera_dist
        if z_eff <= 0.1:
            return 0, 0, -999.0, False

        px = int(center_x + (x * self.fov * self.aspect_ratio) / z_eff)
        py = int(center_y - (y * self.fov) / z_eff)
        return px, py, z, True

    def draw_3d_line(self, p1: Tuple[float, float, float], p2: Tuple[float, float, float],
                     center_x: float, center_y: float, color_rgb: Tuple[int, int, int],
                     char_override: Optional[str] = None):
        """Draw 3D line with perspective projection and depth-interpolated characters."""
        x1, y1, z1 = p1
        x2, y2, z2 = p2

        dist = math.sqrt((x2 - x1)**2 + (y2 - y1)**2 + (z2 - z1)**2)
        steps = max(1, int(dist * 36))

        cr, cg, cb = color_rgb

        for i in range(steps + 1):
            t = i / steps
            x = x1 + (x2 - x1) * t
            y = y1 + (y2 - y1) * t
            z = z1 + (z2 - z1) * t

            px, py, pz, valid = self.project_point(x, y, z, center_x, center_y)
            if not valid:
                continue

            # Normalized depth factor (0.0=far, 1.0=near)
            norm_z = (pz + 1.8) / 3.6
            norm_z = max(0.0, min(1.0, norm_z))

            if char_override:
                ch = char_override
            else:
                idx = int(norm_z * (len(LUMINANCE_RAMP) - 1))
                ch = LUMINANCE_RAMP[max(1, min(len(LUMINANCE_RAMP) - 1, idx))]

            # Compute depth shading
            depth_factor = 0.25 + 0.75 * (norm_z**1.2)
            r = int(cr * depth_factor)
            g = int(cg * depth_factor)
            b = int(cb * depth_factor)

            self.buffer.set_pixel(px, py, pz, ch, rgb(r, g, b))

    def render_frame(self, t: float, boot_progress: Optional[float] = None, status_text: Optional[str] = None) -> str:
        """Render a single 3D frame at timestamp t."""
        self.buffer.clear()
        theme = self.get_theme()

        # Center coordinates
        center_x = self.width / 2.0
        # Position 3D core in upper area
        banner_height = 7 if self.width >= 55 else 4
        center_y = max(7.0, (self.height - banner_height) / 2.0)

        # Dynamic multi-axis rotation angles
        rot_y = t * 1.35 + self.manual_yaw
        rot_x = math.sin(t * 0.7) * 0.45 + 0.35 + self.manual_pitch
        rot_z = math.cos(t * 0.5) * 0.25

        # -------------------------------------------------------------
        # Render Selected 3D Geometry
        # -------------------------------------------------------------
        if self.model_type == "core":
            self._render_quantum_core(t, center_x, center_y, rot_x, rot_y, rot_z, theme)
        elif self.model_type == "tesseract":
            self._render_tesseract(t, center_x, center_y, rot_x, rot_y, rot_z, theme)
        elif self.model_type == "monolith":
            self._render_monolith(t, center_x, center_y, rot_x, rot_y, rot_z, theme)

        # -------------------------------------------------------------
        # Ambient 3D Depth Particle Dust
        # -------------------------------------------------------------
        dust_count = 18
        for i in range(dust_count):
            p_phi = i * 2.39996
            p_theta = (i / float(dust_count)) * math.pi
            pr = 2.45 + math.sin(i * 11.0 + t) * 0.2
            px = pr * math.sin(p_theta) * math.cos(p_phi + t * 0.12)
            py = pr * math.cos(p_theta)
            pz = pr * math.sin(p_theta) * math.sin(p_phi + t * 0.12)

            scx, scy, scz, s_ok = self.project_point(px, py, pz, center_x, center_y)
            if s_ok and scy < self.height - banner_height:
                alpha = (scz + 2.5) / 5.0
                alpha = max(0.0, min(1.0, alpha))
                col = rgb(
                    int(theme["ambient"][0] + alpha * 100),
                    int(theme["ambient"][1] + alpha * 120),
                    int(theme["ambient"][2] + alpha * 140)
                )
                self.buffer.set_pixel(scx, scy, scz, "·" if alpha > 0.4 else ".", col)

        # -------------------------------------------------------------
        # Holographic Typography Banner & Status Display
        # -------------------------------------------------------------
        self._render_banner(t, banner_height, theme, boot_progress, status_text)

        return self.buffer.render()

    def _render_quantum_core(self, t: float, center_x: float, center_y: float,
                             rot_x: float, rot_y: float, rot_z: float, theme: Dict[str, Any]):
        """Render Quantum Gyroscopic Reactor with orbital rings and faceted crystal."""
        # 1. Outer Gyroscopic Ring 1
        ring1_pts = []
        for i in range(self.ring_steps):
            theta = (2.0 * math.pi * i) / self.ring_steps
            rx = self.ring1_radius * math.cos(theta)
            ry = self.ring1_radius * math.sin(theta) * 0.35
            rz = self.ring1_radius * math.sin(theta) * 0.92
            px, py, pz = self.rotate_point(rx, ry, rz, rot_x, rot_y + t * 0.2, rot_z)
            ring1_pts.append((px, py, pz))

        for i in range(self.ring_steps):
            p1 = ring1_pts[i]
            p2 = ring1_pts[(i + 1) % self.ring_steps]
            self.draw_3d_line(p1, p2, center_x, center_y, theme["primary"], char_override="·")

        # Travelling energy node on Ring 1
        node1_idx = int((t * 22) % self.ring_steps)
        n1 = ring1_pts[node1_idx]
        nx, ny, nz, valid = self.project_point(n1[0], n1[1], n1[2], center_x, center_y)
        if valid:
            self.buffer.set_pixel(nx, ny, nz + 0.2, "◆", BOLD + rgb(*theme["core"]))
            self.buffer.set_pixel(nx + 1, ny, nz + 0.1, "✧", rgb(*theme["primary"]))
            self.buffer.set_pixel(nx - 1, ny, nz + 0.1, "✧", rgb(*theme["primary"]))

        # 2. Middle Ring 2 (Vertical orientation, counter-rotating)
        ring2_pts = []
        for i in range(self.ring_steps):
            theta = (2.0 * math.pi * i) / self.ring_steps
            rx = self.ring2_radius * math.sin(theta) * 0.25
            ry = self.ring2_radius * math.cos(theta)
            rz = self.ring2_radius * math.sin(theta) * 0.96
            px, py, pz = self.rotate_point(rx, ry, rz, rot_x - 0.4, -rot_y * 1.2, rot_z + 0.3)
            ring2_pts.append((px, py, pz))

        for i in range(self.ring_steps):
            p1 = ring2_pts[i]
            p2 = ring2_pts[(i + 1) % self.ring_steps]
            self.draw_3d_line(p1, p2, center_x, center_y, theme["tertiary"], char_override=":")

        node2_idx = int((-t * 26) % self.ring_steps)
        n2 = ring2_pts[node2_idx]
        nx, ny, nz, valid = self.project_point(n2[0], n2[1], n2[2], center_x, center_y)
        if valid:
            self.buffer.set_pixel(nx, ny, nz + 0.2, "◈", BOLD + rgb(*theme["tertiary"]))

        # 3. Equatorial Ring 3 (Horizontal, pulsing)
        ring3_r = self.ring3_radius + math.sin(t * 3.0) * 0.06
        ring3_pts = []
        for i in range(self.ring_steps):
            theta = (2.0 * math.pi * i) / self.ring_steps
            rx = ring3_r * math.cos(theta)
            ry = 0.0
            rz = ring3_r * math.sin(theta)
            px, py, pz = self.rotate_point(rx, ry, rz, rot_x * 0.5, rot_y * 0.8, rot_z)
            ring3_pts.append((px, py, pz))

        for i in range(self.ring_steps):
            p1 = ring3_pts[i]
            p2 = ring3_pts[(i + 1) % self.ring_steps]
            self.draw_3d_line(p1, p2, center_x, center_y, theme["secondary"], char_override="=")

        # 4. Central 3D Octahedral Crystal
        pulse = 1.0 + math.sin(t * 4.0) * 0.08
        rot_core_y = -t * 1.8
        rot_core_x = t * 1.1

        transformed_core = []
        for vx, vy, vz in self.core_vertices:
            rx, ry, rz = self.rotate_point(vx * pulse, vy * pulse, vz * pulse, rot_core_x, rot_core_y, 0.0)
            transformed_core.append((rx, ry, rz))

        for u, v in self.core_edges:
            self.draw_3d_line(transformed_core[u], transformed_core[v], center_x, center_y, theme["primary"])

        # 5. Inner Pulsing Hyper-Nucleus
        nuc_scale = 0.65 + math.cos(t * 5.0) * 0.1
        transformed_nuc = []
        for vx, vy, vz in self.nucleus_vertices:
            rx, ry, rz = self.rotate_point(vx * nuc_scale, vy * nuc_scale, vz * nuc_scale, -rot_core_x * 1.3, -rot_core_y * 1.5, t)
            transformed_nuc.append((rx, ry, rz))

        for u, v in self.nucleus_edges:
            self.draw_3d_line(transformed_nuc[u], transformed_nuc[v], center_x, center_y, theme["tertiary"])

        # Central Emitter Spark
        c_proj_x, c_proj_y, _, c_valid = self.project_point(0, 0, 0, center_x, center_y)
        if c_valid:
            sparks = ["✦", "✶", "★", "✹"]
            s_ch = sparks[int(t * 8) % len(sparks)]
            self.buffer.set_pixel(c_proj_x, c_proj_y, 2.5, s_ch, BOLD + rgb(*theme["core"]))
            self.buffer.set_pixel(c_proj_x + 1, c_proj_y, 2.4, "·", rgb(*theme["primary"]))
            self.buffer.set_pixel(c_proj_x - 1, c_proj_y, 2.4, "·", rgb(*theme["primary"]))

    def _render_tesseract(self, t: float, center_x: float, center_y: float,
                          rot_x: float, rot_y: float, rot_z: float, theme: Dict[str, Any]):
        """Render 4D Hypercube (Tesseract) rotated in 4D space and projected into 3D."""
        # 4D rotation angles
        a = t * 1.1 + self.manual_yaw
        b = t * 0.8 + self.manual_pitch
        ca, sa = math.cos(a), math.sin(a)
        cb, sb = math.cos(b), math.sin(b)

        # 4D camera distance for perspective projection into 3D
        cam_4d = 2.4
        transformed_3d = []

        for x, y, z, w in self.tesseract_vertices:
            # 4D Rotation in X-W plane
            x_rot = x * ca - w * sa
            w_rot = x * sa + w * ca

            # 4D Rotation in Y-Z plane
            y_rot = y * cb - z * sb
            z_rot = y * sb + z * cb

            # Perspective division from 4D -> 3D
            div = cam_4d - w_rot
            factor = 1.3 / (div if div > 0.1 else 0.1)
            x3 = x_rot * factor
            y3 = y_rot * factor
            z3 = z_rot * factor

            # Apply 3D camera rotation
            rx, ry, rz = self.rotate_point(x3, y3, z3, rot_x * 0.4, rot_y * 0.6, rot_z * 0.2)
            transformed_3d.append((rx, ry, rz))

        # Render 32 hypercube edges
        for idx, (u, v) in enumerate(self.tesseract_edges):
            col = theme["primary"] if (idx % 2 == 0) else theme["tertiary"]
            self.draw_3d_line(transformed_3d[u], transformed_3d[v], center_x, center_y, col)

        # Center energy singularity
        cx, cy, _, cv = self.project_point(0, 0, 0, center_x, center_y)
        if cv:
            self.buffer.set_pixel(cx, cy, 2.5, "◈", BOLD + rgb(*theme["core"]))

    def _render_monolith(self, t: float, center_x: float, center_y: float,
                         rot_x: float, rot_y: float, rot_z: float, theme: Dict[str, Any]):
        """Render Hexagonal Sovereign Monolith with rotating diamond prism core."""
        pulse = 1.0 + math.sin(t * 3.0) * 0.05
        transformed = []
        for vx, vy, vz in self.monolith_vertices:
            rx, ry, rz = self.rotate_point(vx * pulse, vy * pulse, vz * pulse, rot_x, rot_y, rot_z)
            transformed.append((rx, ry, rz))

        for idx, (u, v) in enumerate(self.monolith_edges):
            col = theme["primary"] if idx < 12 else (theme["secondary"] if idx < 18 else theme["tertiary"])
            self.draw_3d_line(transformed[u], transformed[v], center_x, center_y, col)

        # Central spinning crystal inside monolith
        inner_pulse = 0.5 + math.cos(t * 4.0) * 0.08
        inner_pts = []
        for vx, vy, vz in self.core_vertices:
            rx, ry, rz = self.rotate_point(vx * inner_pulse, vy * inner_pulse, vz * inner_pulse, -rot_x * 1.5, -rot_y * 1.5, t)
            inner_pts.append((rx, ry, rz))

        for u, v in self.core_edges:
            self.draw_3d_line(inner_pts[u], inner_pts[v], center_x, center_y, theme["core"])

    def _render_banner(self, t: float, banner_height: int, theme: Dict[str, Any],
                       boot_progress: Optional[float] = None, status_text: Optional[str] = None):
        """Render glowing cyberpunk typography and status telemetry."""
        banner_start_y = self.height - banner_height
        # Clear banner viewport region with high depth priority to mask 3D background
        for by in range(banner_start_y, self.height):
            for bx in range(self.width):
                self.buffer.set_pixel(bx, by, 15.0, " ", "")

        glow = (math.sin(t * 3.5) + 1.0) / 2.0
        pr, pg, pb = theme["banner"]
        glow_col = rgb(
            int(pr * (0.8 + 0.2 * glow)),
            int(pg * (0.8 + 0.2 * glow)),
            int(pb * (0.8 + 0.2 * glow))
        )
        dim_col = rgb(*theme["secondary"])

        logo_lines = [
            "  ██████╗ ██████╗ ██████╗ ███████╗     █████╗ ██╗  ",
            " ██╔════╝██╔═══██╗██╔══██╗██╔════╝    ██╔══██╗██║  ",
            " ██║     ██║   ██║██████╔╝█████╗      ███████║██║  ",
            " ╚██████╗╚██████╔╝██║  ██╗███████╗    ██║  ██║██║  ",
            "  ╚═════╝ ╚═════╝ ╚═╝  ╚═╝╚══════╝    ╚═╝  ╚═╝╚═╝  "
        ]

        if self.width >= 56 and banner_start_y + 4 < self.height:
            for idx, line in enumerate(logo_lines):
                ly = banner_start_y + idx
                lx = max(0, int((self.width - len(line)) / 2))
                for col_idx, ch in enumerate(line):
                    if ch != " ":
                        self.buffer.set_pixel(lx + col_idx, ly, 20.0, ch, BOLD + glow_col)
        else:
            title = "◄◄  C O R E   A I  ►►"
            lx = max(0, int((self.width - len(title)) / 2))
            for col_idx, ch in enumerate(title):
                self.buffer.set_pixel(lx + col_idx, banner_start_y + 1, 20.0, ch, BOLD + glow_col)

        # Boot Progress Bar or Subtitle
        sub_y = min(self.height - 1, banner_start_y + (5 if self.width >= 56 else 2))

        if boot_progress is not None:
            # Render animated cybernetic progress bar
            pct = max(0.0, min(1.0, boot_progress))
            bar_w = min(40, max(20, self.width - 20))
            filled = int(bar_w * pct)
            bar_str = "█" * filled + "░" * (bar_w - filled)
            status_msg = f"[{bar_str}] {int(pct * 100):>3}%"
            if status_text:
                status_msg = f"{status_text}  {status_msg}"
            sx = max(0, int((self.width - len(status_msg)) / 2))
            for col_idx, ch in enumerate(status_msg):
                c = BOLD + rgb(*theme["primary"]) if ch == "█" else dim_col
                self.buffer.set_pixel(sx + col_idx, sub_y, 20.0, ch, c)
        else:
            subtitle = "[ C.O.R.E. v0.1.1-alpha · SOVEREIGN UBIQUITOUS LIFE OS ]"
            sx = max(0, int((self.width - len(subtitle)) / 2))
            for col_idx, ch in enumerate(subtitle):
                self.buffer.set_pixel(sx + col_idx, sub_y, 20.0, ch, dim_col)


def _check_key_pressed() -> Optional[str]:
    """Non-blocking keyboard reader supporting Windows and Unix."""
    if sys.platform == "win32":
        try:
            import msvcrt
            if msvcrt.kbhit():
                ch = msvcrt.getch()
                if ch in (b"\x00", b"\xe0"):  # Special keys prefix
                    ch2 = msvcrt.getch()
                    if ch2 == b"H": return "UP"
                    if ch2 == b"P": return "DOWN"
                    if ch2 == b"K": return "LEFT"
                    if ch2 == b"M": return "RIGHT"
                    return "SPECIAL"
                return ch.decode("utf-8", errors="ignore")
        except Exception:
            return None
    else:
        try:
            import select
            if select.select([sys.stdin], [], [], 0)[0]:
                return sys.stdin.read(1)
        except Exception:
            return None
    return None


def run_interactive_animation():
    """
    Full real-time 3D animation viewer with interactive controls:
      - [Space]       : Pause / Resume rotation
      - [T]           : Cycle Color Themes
      - [M]           : Switch 3D Model (Core, Tesseract, Monolith)
      - [Arrows/WASD] : Rotate Camera in 3D
      - [+ / -]       : Adjust Rotation Speed
      - [R]           : Reset Camera Angle
      - [Q / Esc]     : Return to Terminal
    """
    cols, rows = shutil.get_terminal_size((80, 26))
    renderer = Core3DRenderer(width=cols, height=rows - 2)

    sys.stdout.write(HIDE_CURSOR)
    sys.stdout.write(CLEAR_SCREEN)
    sys.stdout.flush()

    sim_time = 0.0
    last_frame = time.time()
    speed = 1.0
    paused = False
    status_toast = "Controls: [T] Theme | [M] Model | [Space] Pause | [Q] Exit"
    toast_expire = time.time() + 4.0

    try:
        while True:
            now = time.time()
            dt = now - last_frame
            last_frame = now

            if not paused:
                sim_time += dt * speed

            # Process input
            key = _check_key_pressed()
            if key:
                k = key.lower()
                if k in ("q", "\x1b", "\r", "\n"):  # Quit on Q, ESC, Enter
                    break
                elif k == " ":
                    paused = not paused
                    status_toast = "PAUSED" if paused else "RESUMED"
                    toast_expire = now + 1.5
                elif k == "t":
                    t_name = renderer.cycle_theme()
                    status_toast = f"Theme: {t_name}"
                    toast_expire = now + 2.0
                elif k == "m":
                    m_name = renderer.cycle_model()
                    status_toast = f"Model: {m_name}"
                    toast_expire = now + 2.0
                elif k in ("+", "="):
                    speed = min(3.0, speed + 0.25)
                    status_toast = f"Speed: {speed:.2f}x"
                    toast_expire = now + 1.5
                elif k in ("-", "_"):
                    speed = max(0.1, speed - 0.25)
                    status_toast = f"Speed: {speed:.2f}x"
                    toast_expire = now + 1.5
                elif k in ("w", "up"):
                    renderer.manual_pitch -= 0.15
                elif k in ("s", "down"):
                    renderer.manual_pitch += 0.15
                elif k in ("a", "left"):
                    renderer.manual_yaw -= 0.15
                elif k in ("d", "right"):
                    renderer.manual_yaw += 0.15
                elif k == "r":
                    renderer.manual_pitch = 0.0
                    renderer.manual_yaw = 0.0
                    status_toast = "Camera Angle Reset"
                    toast_expire = now + 1.5

            # Handle terminal resize
            cur_cols, cur_rows = shutil.get_terminal_size((80, 26))
            if cur_cols != renderer.width or (cur_rows - 2) != renderer.height:
                renderer = Core3DRenderer(width=cur_cols, height=max(18, cur_rows - 2),
                                          theme_name=renderer.theme_name, model_type=renderer.model_type)
                sys.stdout.write(CLEAR_SCREEN)

            frame = renderer.render_frame(t=sim_time)

            # Footer status toast
            footer_line = status_toast if now < toast_expire else "[T] Theme  [M] Model  [Arrows] Rotate  [Space] Pause  [Q] Exit"
            footer_padded = f" {footer_line:<{renderer.width - 2}} "
            theme = renderer.get_theme()
            footer_colored = BOLD + rgb_bg(*theme["ambient"]) + rgb(*theme["core"]) + footer_padded + RESET_STYLE

            sys.stdout.write(CURSOR_HOME)
            sys.stdout.write(frame)
            sys.stdout.write(f"\n{footer_colored}")
            sys.stdout.flush()

            sleep_left = 0.033 - (time.time() - now)  # Target ~30 FPS
            if sleep_left > 0:
                time.sleep(sleep_left)

    except KeyboardInterrupt:
        pass
    finally:
        sys.stdout.write(SHOW_CURSOR)
        sys.stdout.write(RESET_STYLE)
        sys.stdout.write(CLEAR_SCREEN)
        sys.stdout.write(CURSOR_HOME)
        sys.stdout.flush()


def play_boot_animation(duration: float = 2.4, steps: Optional[List[str]] = None, fps: int = 30) -> bool:
    """
    Plays a smooth cinematic 3D spin-up boot animation for Core AI microkernel initialization.
    Shows the 3D rotating core synchronizing while the boot steps illuminate.
    Returns True if completed, or False if skipped by user keypress.
    """
    cols, rows = shutil.get_terminal_size((80, 26))
    renderer = Core3DRenderer(width=cols, height=rows - 1, theme_name="cyan", model_type="core")

    sys.stdout.write(HIDE_CURSOR)
    sys.stdout.write(CLEAR_SCREEN)
    sys.stdout.flush()

    boot_steps = steps or [
        "Mounting SQLite State & Topologies",
        "Initializing EventBus Mesh",
        "Connecting Neural Model Router",
        "Configuring Spatial Audio Matrix",
        "Spawning Universal Edge Gateway"
    ]

    start_time = time.time()
    frame_interval = 1.0 / max(15, min(60, fps))
    completed_normally = True

    try:
        while True:
            now = time.time()
            elapsed = now - start_time
            if elapsed >= duration:
                break

            # Check if operator wants to skip
            key = _check_key_pressed()
            if key:
                completed_normally = False
                break

            progress = min(1.0, elapsed / duration)
            step_idx = min(len(boot_steps) - 1, int(progress * len(boot_steps)))
            current_step = boot_steps[step_idx]

            frame = renderer.render_frame(t=elapsed * 1.5, boot_progress=progress, status_text=current_step)

            sys.stdout.write(CURSOR_HOME)
            sys.stdout.write(frame)
            sys.stdout.flush()

            sleep_time = frame_interval - (time.time() - now)
            if sleep_time > 0:
                time.sleep(sleep_time)

    except KeyboardInterrupt:
        completed_normally = False
    finally:
        sys.stdout.write(SHOW_CURSOR)
        sys.stdout.write(RESET_STYLE)
        sys.stdout.write(CLEAR_SCREEN)
        sys.stdout.write(CURSOR_HOME)
        sys.stdout.flush()

    return completed_normally


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] in ("--boot", "-b"):
        play_boot_animation(duration=2.5)
    else:
        run_interactive_animation()
