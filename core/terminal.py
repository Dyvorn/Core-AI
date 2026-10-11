"""
Core AI :: Sovereign Terminal & ANSI Alignment Matrix
Ensures pixel-perfect box rendering, prompt alignment, and cross-platform
compatibility between Linux (GNU Readline/bash) and Windows (PowerShell/CMD).
"""

import os
import re
import sys
from typing import List, Tuple, Optional

# Match ANSI escape sequences: \033[...m or \x1b[...]
ANSI_ESCAPE_RE = re.compile(r"\x1b\[[0-9;]*[a-zA-Z]")

# Terminal Colors
try:
    from colorama import Fore, Style
    CYAN = Fore.CYAN
    GREEN = Fore.GREEN
    YELLOW = Fore.YELLOW
    RED = Fore.RED
    MAGENTA = Fore.MAGENTA
    WHITE = Fore.WHITE
    BOLD = Style.BRIGHT
    RESET = Style.RESET_ALL
except ImportError:
    CYAN = GREEN = YELLOW = RED = MAGENTA = WHITE = BOLD = RESET = ""


def strip_ansi(text: str) -> str:
    """Removes ANSI color and style escape sequences to compute true printable visual width."""
    return ANSI_ESCAPE_RE.sub("", text)


def visible_len(text: str) -> int:
    """Calculates visible character count of a string ignoring invisible ANSI escapes."""
    # Also strip readline markers if present
    clean = strip_ansi(text).replace("\001", "").replace("\002", "")
    return len(clean)


def make_readline_safe_prompt(prompt_str: str) -> str:
    """
    On POSIX systems (Linux/macOS), GNU Readline handles terminal prompts for Python's input().
    Non-printing escape sequences (ANSI colors/styles) MUST be enclosed within \\001 and \\002.
    Without these markers, Readline counts ANSI escape bytes as visible character columns,
    causing severe prompt cursor misalignment, broken backspacing, and weird line wrapping.
    On Windows, returns prompt as-is since Windows console host handles ANSI directly.
    """
    if os.name == "nt":
        return prompt_str

    # Clean existing markers to prevent double-wrapping
    clean = prompt_str.replace("\001", "").replace("\002", "")

    # Wrap every ANSI escape sequence in \001...\002
    return ANSI_ESCAPE_RE.sub(lambda m: f"\001{m.group(0)}\002", clean)


def render_box(
    title: str,
    rows: List[Tuple[str, str]],
    width: int = 71,
    border_color: str = CYAN,
    title_color: str = BOLD,
    border_style: str = "ascii"
) -> str:
    """
    Renders a perfectly aligned status/version/overview card.
    Guarantees that every row has the EXACT same visual width down to 1 space,
    preventing ragged or crooked right borders across all terminals.
    """
    inner_width = max(width - 2, 40)

    # Border style characters
    if border_style == "unicode" and sys.stdout and getattr(sys.stdout, "encoding", "").lower().startswith("utf"):
        tl, tr, bl, br = "┌", "┐", "└", "┘"
        h, v = "─", "│"
        sep_l, sep_r = "├", "┤"
    else:
        tl, tr, bl, br = "+", "+", "+", "+"
        h, v = "=", "|"
        sep_l, sep_r = "+", "+"

    lines = []

    # Top border
    lines.append(f"{border_color}{tl}{h * inner_width}{tr}{RESET}")

    # Title header
    clean_title = strip_ansi(title).strip()
    left_padding = 3
    title_visible_space = inner_width - left_padding
    formatted_title = f"{' ' * left_padding}{title_color}{title}{RESET}"
    trailing_spaces = inner_width - (left_padding + len(clean_title))
    if trailing_spaces < 0:
        trailing_spaces = 0
    lines.append(f"{border_color}{v}{RESET}{formatted_title}{' ' * trailing_spaces}{border_color}{v}{RESET}")

    # Divider below title
    lines.append(f"{border_color}{sep_l}{h * inner_width}{sep_r}{RESET}")

    # Body rows
    for label, val in rows:
        clean_lbl = strip_ansi(label)
        clean_val = strip_ansi(val)

        # Standard indentation: 3 spaces
        prefix = "   "
        row_content = f"{prefix}{label:<22} {val}"
        row_vis_len = len(prefix) + max(len(clean_lbl), 22) + 1 + len(clean_val)
        
        # Exact padding to match inner_width
        pad = inner_width - row_vis_len
        if pad < 0:
            pad = 0

        lines.append(f"{border_color}{v}{RESET}{row_content}{' ' * pad}{border_color}{v}{RESET}")

    # Bottom border
    lines.append(f"{border_color}{bl}{h * inner_width}{br}{RESET}")

    return "\n".join(lines)
