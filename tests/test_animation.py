import pytest
import re
from core.animation import FrameBuffer, Core3DRenderer, THEMES, play_boot_animation

def test_frame_buffer_depth_sorting():
    fb = FrameBuffer(width=10, height=5)
    # Write a background pixel at depth z = 1.0
    fb.set_pixel(2, 2, z=1.0, char="B", color_code="blue")
    assert fb.chars[2][2] == "B"
    assert fb.colors[2][2] == "blue"

    # Overwrite with a closer pixel at depth z = 2.0
    fb.set_pixel(2, 2, z=2.0, char="F", color_code="cyan")
    assert fb.chars[2][2] == "F"
    assert fb.colors[2][2] == "cyan"

    # Attempt to overwrite with a further pixel at depth z = 0.5 (should be rejected by z-buffer)
    fb.set_pixel(2, 2, z=0.5, char="X", color_code="red")
    assert fb.chars[2][2] == "F"
    assert fb.colors[2][2] == "cyan"

def test_frame_buffer_bounds_protection():
    fb = FrameBuffer(width=10, height=5)
    # These should be silently ignored and not throw IndexError
    fb.set_pixel(-1, 0, 1.0, "A", "")
    fb.set_pixel(10, 0, 1.0, "A", "")
    fb.set_pixel(0, -1, 1.0, "A", "")
    fb.set_pixel(0, 5, 1.0, "A", "")

def test_3d_renderer_all_models_and_themes():
    renderer = Core3DRenderer(width=70, height=22)
    models = ["core", "tesseract", "monolith"]
    themes = list(THEMES.keys())

    for model in models:
        renderer.model_type = model
        for theme in themes:
            renderer.theme_name = theme
            frame = renderer.render_frame(t=1.5)
            assert isinstance(frame, str)
            assert len(frame) > 100
            # Check ANSI reset styling present
            assert "\033[0m" in frame

def test_banner_and_status_progress():
    renderer = Core3DRenderer(width=70, height=22)
    # With boot progress
    frame = renderer.render_frame(t=2.0, boot_progress=0.75, status_text="Mounting SQLite State")
    clean = re.sub(r"\x1b\[[0-9;]*m", "", frame)

    assert "Mounting SQLite State" in clean
    assert "75%" in clean
    assert "██" in clean

    # Without boot progress (displays subtitle)
    normal_frame = renderer.render_frame(t=2.0)
    clean_normal = re.sub(r"\x1b\[[0-9;]*m", "", normal_frame)
    assert "SOVEREIGN UBIQUITOUS LIFE OS" in clean_normal

def test_theme_and_model_cycling():
    renderer = Core3DRenderer(width=60, height=20, theme_name="cyan", model_type="core")
    first_theme = renderer.theme_name
    second_theme = renderer.cycle_theme()
    assert first_theme != renderer.theme_name

    first_model = renderer.model_type
    second_model = renderer.cycle_model()
    assert first_model != renderer.model_type
