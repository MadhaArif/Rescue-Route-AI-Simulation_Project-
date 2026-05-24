from __future__ import annotations

import math
from typing import Iterable

import pygame

from .city import traffic_color
from .config import COLORS, EMERGENCY_TYPES, MAP_WIDTH, SCREEN_HEIGHT, SCREEN_WIDTH, TRAFFIC_LEVELS
from .entities import Ambulance, Emergency, Hospital, Node
from .simulation import Simulation


def _font(size: int, bold: bool = False) -> pygame.font.Font:
    return pygame.font.SysFont("arial", size, bold=bold)


def _draw_text(
    surface: pygame.Surface,
    text: str,
    pos: tuple[int, int],
    size: int = 18,
    color: tuple[int, int, int] = COLORS["black"],
    bold: bool = False,
) -> None:
    rendered = _font(size, bold).render(text, True, color)
    surface.blit(rendered, pos)


def _draw_center_text(
    surface: pygame.Surface,
    text: str,
    center: tuple[int, int],
    size: int = 16,
    color: tuple[int, int, int] = COLORS["black"],
    bold: bool = False,
) -> None:
    rendered = _font(size, bold).render(text, True, color)
    rect = rendered.get_rect(center=center)
    surface.blit(rendered, rect)


def _format_minutes(value: float | None) -> str:
    if value is None or not math.isfinite(float(value)):
        return "N/A"
    return f"{float(value):.1f} min"


def draw(sim: Simulation, screen: pygame.Surface) -> None:
    screen.fill(COLORS["background"])
    _draw_map_panel(sim, screen)
    _draw_side_panel(sim, screen)


def _draw_map_panel(sim: Simulation, screen: pygame.Surface) -> None:
    map_rect = pygame.Rect(0, 0, MAP_WIDTH, SCREEN_HEIGHT)
    pygame.draw.rect(screen, COLORS["map_bg"], map_rect)

    _draw_roads(sim, screen)
    _draw_active_routes(sim, screen)
    _draw_nodes(sim, screen)
    _draw_hospitals(sim, screen)
    _draw_stations(sim, screen)
    _draw_emergencies(sim, screen)
    _draw_ambulances(sim, screen)
    _draw_legend(screen)


def _edge_points(sim: Simulation, u: Node, v: Node) -> tuple[tuple[int, int], tuple[int, int]]:
    return sim.graph.nodes[u]["pos"], sim.graph.nodes[v]["pos"]


def _draw_roads(sim: Simulation, screen: pygame.Surface) -> None:
    for u, v, data in sim.graph.edges(data=True):
        start, end = _edge_points(sim, u, v)
        level = str(data.get("traffic", "Low"))
        width = {"Low": 4, "Medium": 5, "High": 7, "Blocked": 7}.get(level, 4)
        pygame.draw.line(screen, traffic_color(level), start, end, width)
        if level == "Blocked":
            mx = int((start[0] + end[0]) / 2)
            my = int((start[1] + end[1]) / 2)
            pygame.draw.line(screen, COLORS["danger"], (mx - 8, my - 8), (mx + 8, my + 8), 3)
            pygame.draw.line(screen, COLORS["danger"], (mx - 8, my + 8), (mx + 8, my - 8), 3)


def _route_color(status: str) -> tuple[int, int, int]:
    if status == "to_emergency":
        return (33, 115, 220)
    if status == "to_hospital":
        return (133, 79, 210)
    if status == "returning":
        return (96, 112, 128)
    return COLORS["route"]


def _draw_path(sim: Simulation, screen: pygame.Surface, path: list[Node], color: tuple[int, int, int], width: int = 8) -> None:
    if len(path) < 2:
        return
    points = [sim.graph.nodes[node]["pos"] for node in path]
    pygame.draw.lines(screen, COLORS["route_shadow"], False, points, width + 4)
    pygame.draw.lines(screen, color, False, points, width)


def _draw_active_routes(sim: Simulation, screen: pygame.Surface) -> None:
    for ambulance in sim.ambulances:
        if ambulance.status != "idle" and ambulance.route:
            remaining = ambulance.route[max(0, ambulance.route_index) :]
            _draw_path(sim, screen, remaining, _route_color(ambulance.status), width=6)


def _draw_nodes(sim: Simulation, screen: pygame.Surface) -> None:
    for node, data in sim.graph.nodes(data=True):
        x, y = data["pos"]
        pygame.draw.circle(screen, COLORS["white"], (x, y), 9)
        pygame.draw.circle(screen, COLORS["node"], (x, y), 5)


def _draw_hospitals(sim: Simulation, screen: pygame.Surface) -> None:
    for hospital in sim.hospitals:
        x, y = sim.graph.nodes[hospital.node]["pos"]
        rect = pygame.Rect(x - 22, y - 22, 44, 44)
        pygame.draw.rect(screen, COLORS["hospital"], rect, border_radius=8)
        pygame.draw.rect(screen, COLORS["white"], rect, 3, border_radius=8)
        _draw_center_text(screen, "H", (x, y - 2), 24, COLORS["white"], bold=True)
        label = hospital.name.split()[0]
        _draw_center_text(screen, label, (x, y + 34), 13, COLORS["black"], bold=True)
        _draw_center_text(screen, f"{hospital.beds_available}/{hospital.beds_total} beds", (x, y + 50), 12, COLORS["hospital"])


def _draw_stations(sim: Simulation, screen: pygame.Surface) -> None:
    station_nodes = sorted({ambulance.home_node for ambulance in sim.ambulances})
    for node in station_nodes:
        x, y = sim.graph.nodes[node]["pos"]
        pygame.draw.circle(screen, COLORS["station"], (x, y), 17)
        pygame.draw.circle(screen, COLORS["white"], (x, y), 17, 2)
        _draw_center_text(screen, "S", (x, y), 16, COLORS["white"], bold=True)


def _draw_emergencies(sim: Simulation, screen: pygame.Surface) -> None:
    for emergency in sim.active_emergencies:
        if emergency.status == "picked_up":
            continue
        x, y = sim.graph.nodes[emergency.node]["pos"]
        color = EMERGENCY_TYPES.get(emergency.event_type, {}).get("color", COLORS["danger"])
        pulse = 2 if int(sim.sim_time * 2) % 2 == 0 else 0
        pygame.draw.circle(screen, color, (x, y), 17 + pulse)
        pygame.draw.circle(screen, COLORS["white"], (x, y), 17 + pulse, 3)
        _draw_center_text(screen, "!", (x, y - 1), 24, COLORS["white"], bold=True)
        _draw_center_text(screen, f"#{emergency.emergency_id}", (x, y + 31), 13, COLORS["danger"], bold=True)


def _draw_ambulances(sim: Simulation, screen: pygame.Surface) -> None:
    for ambulance in sim.ambulances:
        x, y = int(ambulance.x), int(ambulance.y)
        rect = pygame.Rect(x - 18, y - 12, 36, 24)
        pygame.draw.rect(screen, COLORS["ambulance"], rect, border_radius=6)
        pygame.draw.rect(screen, COLORS["ambulance_outline"], rect, 3, border_radius=6)
        pygame.draw.rect(screen, COLORS["danger"], pygame.Rect(x - 3, y - 9, 6, 18))
        pygame.draw.rect(screen, COLORS["danger"], pygame.Rect(x - 10, y - 2, 20, 6))
        _draw_center_text(screen, ambulance.ambulance_id, (x, y + 23), 13, COLORS["ambulance_outline"], bold=True)


def _draw_legend(screen: pygame.Surface) -> None:
    legend_x, legend_y = 20, SCREEN_HEIGHT - 140
    panel = pygame.Rect(legend_x - 10, legend_y - 10, 195, 118)
    pygame.draw.rect(screen, (255, 255, 255), panel, border_radius=10)
    pygame.draw.rect(screen, (205, 214, 224), panel, 1, border_radius=10)
    _draw_text(screen, "Traffic legend", (legend_x, legend_y), 16, COLORS["black"], bold=True)
    y = legend_y + 28
    for name in ["Low", "Medium", "High", "Blocked"]:
        pygame.draw.line(screen, traffic_color(name), (legend_x, y + 8), (legend_x + 42, y + 8), 6)
        _draw_text(screen, name, (legend_x + 52, y), 14, COLORS["black"])
        y += 22


def _metric_box(
    screen: pygame.Surface,
    rect: pygame.Rect,
    label: str,
    value: str,
    accent: tuple[int, int, int],
) -> None:
    pygame.draw.rect(screen, (38, 49, 64), rect, border_radius=10)
    pygame.draw.rect(screen, accent, rect, 2, border_radius=10)
    _draw_text(screen, label, (rect.x + 10, rect.y + 8), 13, COLORS["muted_text"])
    _draw_text(screen, value, (rect.x + 10, rect.y + 27), 22, COLORS["panel_text"], bold=True)


def _draw_side_panel(sim: Simulation, screen: pygame.Surface) -> None:
    panel_rect = pygame.Rect(MAP_WIDTH, 0, SCREEN_WIDTH - MAP_WIDTH, SCREEN_HEIGHT)
    pygame.draw.rect(screen, COLORS["panel_bg"], panel_rect)
    x = MAP_WIDTH + 18
    y = 18

    _draw_text(screen, "RescueRoute AI", (x, y), 26, COLORS["panel_text"], bold=True)
    _draw_text(screen, "Smart Ambulance Dispatch", (x, y + 32), 15, COLORS["muted_text"])
    y += 68

    box_w = 92
    _metric_box(screen, pygame.Rect(x, y, box_w, 64), "Saved", str(sim.saved_cases), COLORS["success"])
    _metric_box(screen, pygame.Rect(x + box_w + 12, y, box_w, 64), "Delayed", str(sim.delayed_cases), COLORS["danger"])
    _metric_box(screen, pygame.Rect(x + 2 * (box_w + 12), y, box_w, 64), "Active", str(len(sim.active_emergencies)), COLORS["warning"])
    y += 82

    _draw_text(screen, "Live KPIs", (x, y), 18, COLORS["panel_text"], bold=True)
    y += 28
    kpis = [
        ("Avg response", _format_minutes(sim.avg_response_minutes)),
        ("Available ambulances", str(sim.available_ambulances)),
        ("Open hospital beds", str(sim.open_beds)),
        ("Generated cases", str(sim.generated_cases)),
    ]
    for label, value in kpis:
        _draw_text(screen, label, (x, y), 14, COLORS["muted_text"])
        _draw_text(screen, value, (x + 170, y), 14, COLORS["panel_text"], bold=True)
        y += 22

    y += 8
    _draw_text(screen, "Route comparison", (x, y), 18, COLORS["panel_text"], bold=True)
    y += 28
    optimized = sim.last_route_compare.get("optimized", 0.0)
    normal = sim.last_route_compare.get("normal", 0.0)
    _draw_text(screen, f"AI optimized: {_format_minutes(optimized)}", (x, y), 14, COLORS["panel_text"])
    y += 20
    _draw_text(screen, f"Normal route:   {_format_minutes(normal)}", (x, y), 14, COLORS["panel_text"])
    y += 20
    saved = max(0.0, float(normal or 0) - float(optimized or 0)) if normal and optimized else 0.0
    _draw_text(screen, f"Time saved:     {saved:.1f} min", (x, y), 14, COLORS["success"] if saved > 0 else COLORS["muted_text"], bold=True)
    y += 34

    _draw_text(screen, "Hospitals", (x, y), 18, COLORS["panel_text"], bold=True)
    y += 28
    for hospital in sim.hospitals:
        _draw_hospital_row(screen, hospital, x, y)
        y += 50

    y += 6
    _draw_text(screen, "Ambulances", (x, y), 18, COLORS["panel_text"], bold=True)
    y += 28
    for ambulance in sim.ambulances:
        status = ambulance.status.replace("_", " ").title()
        note = ambulance.path_note if ambulance.path_note else "Ready"
        _draw_text(screen, f"{ambulance.ambulance_id}: {status}", (x, y), 14, COLORS["panel_text"], bold=True)
        _draw_text(screen, _truncate(note, 31), (x + 96, y), 14, COLORS["muted_text"])
        y += 22

    y += 8
    _draw_text(screen, "ML ETA model", (x, y), 18, COLORS["panel_text"], bold=True)
    y += 25
    mae = sim.predictor.metrics.get("mae_minutes")
    r2 = sim.predictor.metrics.get("r2")
    if mae is not None and r2 is not None:
        _draw_text(screen, f"Random Forest MAE: {mae:.2f} min, R²: {r2:.2f}", (x, y), 13, COLORS["muted_text"])
    else:
        _draw_text(screen, "Using formula fallback", (x, y), 13, COLORS["muted_text"])
    y += 36

    _draw_text(screen, "Controls", (x, y), 18, COLORS["panel_text"], bold=True)
    y += 25
    controls = ["SPACE emergency", "T traffic", "B block road", "C clear traffic", "ESC quit"]
    for item in controls:
        _draw_text(screen, item, (x, y), 13, COLORS["muted_text"])
        y += 18

    y += 8
    _draw_text(screen, "Event log", (x, y), 18, COLORS["panel_text"], bold=True)
    y += 25
    for message in list(sim.messages)[:6]:
        _draw_text(screen, _truncate(message, 42), (x, y), 12, COLORS["panel_text"])
        y += 18


def _draw_hospital_row(screen: pygame.Surface, hospital: Hospital, x: int, y: int) -> None:
    _draw_text(screen, hospital.name, (x, y), 14, COLORS["panel_text"], bold=True)
    beds = int(hospital.beds_available or 0)
    _draw_text(screen, f"Beds: {beds}/{hospital.beds_total}", (x + 178, y), 14, COLORS["muted_text"])
    bar = pygame.Rect(x, y + 22, 260, 10)
    pygame.draw.rect(screen, (55, 66, 82), bar, border_radius=5)
    fill_width = int(bar.width * (beds / max(1, hospital.beds_total)))
    pygame.draw.rect(screen, COLORS["success"] if beds else COLORS["danger"], pygame.Rect(bar.x, bar.y, fill_width, bar.height), border_radius=5)


def _truncate(text: str, length: int) -> str:
    return text if len(text) <= length else text[: max(0, length - 1)] + "…"
