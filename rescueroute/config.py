from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_ROOT / "data"
MODEL_DIR = PROJECT_ROOT / "models"
MODEL_PATH = MODEL_DIR / "arrival_time_model.joblib"
CASE_LOG_PATH = DATA_DIR / "case_log.csv"
SNAPSHOT_LOG_PATH = DATA_DIR / "dashboard_stats.csv"
EXTERNAL_TRIGGER_PATH = DATA_DIR / "external_requests.json"

SCREEN_WIDTH = 1180
SCREEN_HEIGHT = 760
MAP_WIDTH = 860
PANEL_WIDTH = SCREEN_WIDTH - MAP_WIDTH
FPS = 60

# City simulation timing
AUTO_EMERGENCY_MIN_SECONDS = 5.0
AUTO_EMERGENCY_MAX_SECONDS = 9.0
TRAFFIC_REFRESH_SECONDS = 10.0
SNAPSHOT_SECONDS = 2.0
MAX_ACTIVE_EMERGENCIES = 6

# Visual movement speed. Route ETA calculations are separate and use km/h.
BASE_AMBULANCE_PIXELS_PER_SECOND = 118.0
AMBULANCE_SPEED_KMPH = 48.0

TRAFFIC_LEVELS = {
    "Low": {"code": 1, "multiplier": 1.0, "color": (62, 174, 88)},
    "Medium": {"code": 2, "multiplier": 1.55, "color": (242, 181, 73)},
    "High": {"code": 3, "multiplier": 2.45, "color": (224, 90, 76)},
    "Blocked": {"code": 4, "multiplier": 9999.0, "color": (42, 42, 42)},
}

EMERGENCY_TYPES = {
    "Accident": {"severity": 4, "specialty": "trauma", "color": (230, 76, 60)},
    "Heart Attack": {"severity": 5, "specialty": "cardiac", "color": (190, 45, 80)},
    "Fire Injury": {"severity": 4, "specialty": "burn", "color": (246, 126, 45)},
    "Critical Patient": {"severity": 5, "specialty": "icu", "color": (151, 65, 202)},
    "Minor Injury": {"severity": 2, "specialty": "general", "color": (60, 145, 230)},
}

SEVERITY_RESPONSE_LIMIT_MINUTES = {
    1: 28.0,
    2: 22.0,
    3: 16.0,
    4: 12.0,
    5: 8.0,
}

COLORS = {
    "background": (15, 23, 42),      # Darker, more modern Slate-900
    "map_bg": (30, 41, 59),          # Slate-800
    "panel_bg": (15, 23, 42),        # Match background
    "panel_text": (248, 250, 252),   # Slate-50
    "muted_text": (148, 163, 184),   # Slate-400
    "node": (71, 85, 105),           # Slate-600
    "route": (56, 189, 248),         # Sky-400 (Neon Blue)
    "route_shadow": (7, 89, 133),    # Sky-800
    "hospital": (20, 184, 166),      # Teal-500
    "station": (99, 102, 241),       # Indigo-500
    "ambulance": (255, 255, 255),
    "ambulance_outline": (56, 189, 248),
    "success": (34, 197, 94),        # Green-500
    "warning": (234, 179, 8),        # Yellow-500
    "danger": (239, 68, 68),         # Red-500
    "black": (0, 0, 0),
    "white": (255, 255, 255),
    "neon_pink": (244, 114, 182),    # For special alerts
}

# Weather & Time System
WEATHER_EFFECTS = {
    "Clear": 1.0,
    "Rainy": 1.3,
    "Stormy": 1.8,
}
RUSH_HOUR_MULTIPLIER = 1.5
