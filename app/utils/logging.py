"""
Structured logging for the BAS World chatbot agent.

Provides colorful, formatted terminal output showing:
  - Agent reasoning steps
  - Tool calls with parameters
  - Search results summaries
  - Timing information
"""

import json
import logging
import sys
import time
from contextlib import contextmanager
from functools import wraps

# ---------------------------------------------------------------------------
# ANSI color codes (Windows 10+ supports these natively)
# ---------------------------------------------------------------------------

RESET = "\033[0m"
BOLD = "\033[1m"
DIM = "\033[2m"

# Foreground
RED = "\033[91m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
BLUE = "\033[94m"
MAGENTA = "\033[95m"
CYAN = "\033[96m"
WHITE = "\033[97m"
GRAY = "\033[90m"

# Background
BG_BLUE = "\033[44m"
BG_GREEN = "\033[42m"
BG_YELLOW = "\033[43m"
BG_RED = "\033[41m"
BG_MAGENTA = "\033[45m"

# ---------------------------------------------------------------------------
# Icons
# ---------------------------------------------------------------------------

ICON_USER = "👤"
ICON_BOT = "🤖"
ICON_TOOL = "🔧"
ICON_SEARCH = "🔍"
ICON_COMPARE = "⚖️"
ICON_DETAIL = "📋"
ICON_OK = "✅"
ICON_WARN = "⚠️"
ICON_ERROR = "❌"
ICON_TIME = "⏱️"
ICON_ARROW = "→"
ICON_TRUCK = "🚛"
ICON_GRAPH = "📊"

# ---------------------------------------------------------------------------
# Logger setup
# ---------------------------------------------------------------------------

logger = logging.getLogger("bas_world")


class FlushHandler(logging.StreamHandler):
    """StreamHandler that flushes after every emit — ensures logs show
    immediately in cmd.exe / Windows Terminal even when stdout is buffered."""

    def emit(self, record):
        super().emit(record)
        self.flush()


class AgentFormatter(logging.Formatter):
    """Custom formatter that passes through pre-formatted messages."""

    def format(self, record):
        return record.getMessage()


def _enable_ansi_windows():
    """Enable ANSI escape codes on Windows consoles (cmd.exe, PowerShell)."""
    if sys.platform != "win32":
        return
    try:
        import ctypes
        kernel32 = ctypes.windll.kernel32
        # Enable VIRTUAL_TERMINAL_PROCESSING on stdout (-11) AND stderr (-12)
        for handle_id in (-11, -12):
            handle = kernel32.GetStdHandle(handle_id)
            mode = ctypes.c_ulong()
            kernel32.GetConsoleMode(handle, ctypes.byref(mode))
            kernel32.SetConsoleMode(handle, mode.value | 0x0004)
    except Exception:
        pass  # Fallback: colors won't work but everything else will


def setup_logging(level=logging.INFO):
    """Configure the BAS World agent logger."""
    _enable_ansi_windows()

    # Use stderr so output is unbuffered and appears immediately
    handler = FlushHandler(sys.stderr)
    handler.setFormatter(AgentFormatter())
    handler.setLevel(level)

    logger.setLevel(level)
    logger.handlers.clear()
    logger.addHandler(handler)
    logger.propagate = False


# ---------------------------------------------------------------------------
# Logging helpers
# ---------------------------------------------------------------------------

def _separator(char="─", length=70, color=GRAY):
    return f"{color}{char * length}{RESET}"


def log_separator():
    logger.info(_separator())


def log_header(text, icon="", color=CYAN):
    logger.info("")
    logger.info(_separator("═", 70, color))
    logger.info(f"{color}{BOLD}  {icon}  {text}{RESET}")
    logger.info(_separator("═", 70, color))


def log_section(text, icon="", color=BLUE):
    logger.info(f"\n{color}{BOLD}{icon}  {text}{RESET}")
    logger.info(_separator("─", 60, DIM))


def log_step(text, icon=ICON_ARROW, color=WHITE):
    logger.info(f"  {color}{icon} {text}{RESET}")


def log_kv(key, value, indent=4):
    """Log a key-value pair."""
    spaces = " " * indent
    logger.info(f"{spaces}{CYAN}{key}:{RESET} {WHITE}{value}{RESET}")


def log_success(text):
    logger.info(f"  {GREEN}{ICON_OK} {text}{RESET}")


def log_warning(text):
    logger.info(f"  {YELLOW}{ICON_WARN} {text}{RESET}")


def log_error(text):
    logger.info(f"  {RED}{ICON_ERROR} {text}{RESET}")


# ---------------------------------------------------------------------------
# Chat-specific logging
# ---------------------------------------------------------------------------

def log_user_message(session_id: str, message: str):
    """Log an incoming user message."""
    log_header(f"NEW CHAT REQUEST  [{session_id[:8]}...]", ICON_USER, MAGENTA)
    # Truncate long messages
    display = message[:200] + "..." if len(message) > 200 else message
    log_kv("Message", display, 2)


def log_agent_thinking():
    """Log that the agent is processing."""
    log_section("AGENT REASONING", ICON_BOT, BLUE)
    log_step("LLM is processing the message...", "💭", DIM)


def log_agent_response(response_text: str, tool_calls: list = None):
    """Log the agent's response."""
    if tool_calls:
        log_section(f"AGENT DECISION → Call {len(tool_calls)} tool(s)", ICON_BOT, YELLOW)
        for tc in tool_calls:
            name = tc.get("name", "unknown")
            args = tc.get("args", {})
            icon = {
                "search_inventory": ICON_SEARCH,
                "compare_vehicles": ICON_COMPARE,
                "get_vehicle_details": ICON_DETAIL,
            }.get(name, ICON_TOOL)
            log_step(f"{icon}  {BOLD}{name}{RESET}", "", YELLOW)
            if args:
                # Parse args for better display
                for k, v in args.items():
                    if isinstance(v, str) and len(v) > 100:
                        v = v[:100] + "..."
                    log_kv(k, v, 8)
    else:
        log_section("AGENT RESPONSE (final)", ICON_BOT, GREEN)
        display = response_text[:300] + "..." if len(response_text) > 300 else response_text
        for line in display.split("\n")[:8]:
            logger.info(f"    {GREEN}{line}{RESET}")
        if len(response_text) > 300:
            logger.info(f"    {DIM}... ({len(response_text)} chars total){RESET}")


def log_tool_call(tool_name: str, filters: dict = None):
    """Log a tool being executed."""
    icon = {
        "search_inventory": ICON_SEARCH,
        "compare_vehicles": ICON_COMPARE,
        "get_vehicle_details": ICON_DETAIL,
    }.get(tool_name, ICON_TOOL)

    log_section(f"TOOL EXECUTING: {tool_name}", icon, CYAN)

    if filters:
        log_step("Filters applied:", "📝", WHITE)
        for k, v in filters.items():
            if k == "limit":
                continue
            emoji = {
                "brand": "🏷️", "configuration": "⚙️", "euro": "🇪🇺",
                "gearbox": "🔄", "min_power": "⚡", "max_power": "⚡",
                "min_price": "💰", "max_price": "💰", "cabin": "🛏️",
                "has_retarder": "🛑", "has_airco": "❄️", "fuel": "⛽",
                "sort_by": "📊", "is_new": "✨", "max_mileage": "📏",
            }.get(k, "•")
            log_kv(f"{emoji} {k}", v, 8)


def log_search_results(count: int, vehicles: list):
    """Log search results summary."""
    if count == 0:
        log_warning(f"No vehicles matched the filters")
    else:
        log_success(f"Found {count} matching vehicle(s)")
        for v in vehicles[:5]:
            brand = v.get("brand", "?")
            model = v.get("model_extended", "?")
            vid = v.get("vehicle_id", "?")
            power = v.get("power", "?")
            price = v.get("internet_price", 0)
            euro = v.get("euro", "?")
            price_str = f"€{price:,.0f}" if price else "N/A"
            logger.info(
                f"    {ICON_TRUCK} {WHITE}{BOLD}{brand} {model}{RESET}"
                f"  {DIM}ID:{vid} | {power}HP | Euro {euro} | {price_str}{RESET}"
            )


def log_compare_results(vehicle_ids: list):
    """Log comparison tool usage."""
    log_success(f"Comparing {len(vehicle_ids)} vehicles: {vehicle_ids}")


def log_detail_result(vehicle_id):
    """Log vehicle detail lookup."""
    log_success(f"Retrieved details for vehicle ID: {vehicle_id}")


def log_vehicle_cards(cards: list):
    """Log which vehicle cards are being sent to the frontend."""
    if cards:
        log_section(f"VEHICLE CARDS → Frontend ({len(cards)} cards)", "🃏", MAGENTA)
        for c in cards:
            brand = getattr(c, 'brand', '?')
            model = getattr(c, 'model_extended', '?')
            vid = getattr(c, 'vehicle_id', '?')
            logger.info(f"    🃏 {WHITE}{brand} {model}{RESET} {DIM}(ID: {vid}){RESET}")


def log_chat_complete(duration_ms: float, cards_count: int):
    """Log the end of a chat request."""
    color = GREEN if duration_ms < 10000 else YELLOW if duration_ms < 20000 else RED
    log_section("REQUEST COMPLETE", ICON_TIME, color)
    log_kv("Duration", f"{duration_ms:.0f}ms", 4)
    log_kv("Cards sent", str(cards_count), 4)
    logger.info("")


def log_startup(port: int, model: str):
    """Log server startup info."""
    logger.info("")
    logger.info(f"{CYAN}{BOLD}{'═' * 60}{RESET}")
    logger.info(f"{CYAN}{BOLD}  {ICON_TRUCK}  BAS World AI Tractor Head Finder{RESET}")
    logger.info(f"{CYAN}{BOLD}{'═' * 60}{RESET}")
    logger.info(f"  {WHITE}Server:{RESET}  http://localhost:{port}")
    logger.info(f"  {WHITE}Model:{RESET}   {model}")
    logger.info(f"  {WHITE}Logs:{RESET}    Agent tracing enabled ✓")
    logger.info(f"{CYAN}{BOLD}{'═' * 60}{RESET}")
    logger.info("")
