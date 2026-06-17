from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Callable, Optional

import networkx as nx

from .config import SEVERITY_RESPONSE_LIMIT_MINUTES, TRAFFIC_LEVELS
from .entities import Ambulance, Emergency, Hospital, Node


@dataclass
class RouteResult:
    path: list[Node]
    minutes: float
    distance_km: float
    avg_traffic_code: float
    blocked_edges: int

    @property
    def is_valid(self) -> bool:
        return bool(self.path) and math.isfinite(self.minutes)


@dataclass
class AmbulanceChoice:
    ambulance: Ambulance
    route: RouteResult
    predicted_minutes: float
    normal_route_minutes: float


@dataclass
class HospitalChoice:
    hospital: Hospital
    route: RouteResult
    score: float


def traffic_code(level: str) -> int:
    return int(TRAFFIC_LEVELS.get(level, TRAFFIC_LEVELS["Low"])["code"])


def traffic_multiplier(level: str, weather: str = "Clear", is_rush_hour: bool = False) -> float:
    from .config import WEATHER_EFFECTS, RUSH_HOUR_MULTIPLIER
    base = float(TRAFFIC_LEVELS.get(level, TRAFFIC_LEVELS["Low"])["multiplier"])
    weather_mod = float(WEATHER_EFFECTS.get(weather, 1.0))
    rush_mod = RUSH_HOUR_MULTIPLIER if is_rush_hour else 1.0
    return base * weather_mod * rush_mod


def edge_travel_minutes(data: dict, speed_kmph: float, weather: str = "Clear", is_rush_hour: bool = False) -> float:
    level = data.get("traffic", "Low")
    if level == "Blocked":
        return math.inf
    distance_km = float(data.get("distance_km", 1.0))
    return (distance_km / max(speed_kmph, 1.0)) * 60.0 * traffic_multiplier(level, weather, is_rush_hour)


def _edge_weight(speed_kmph: float, weather: str = "Clear", is_rush_hour: bool = False) -> Callable[[Node, Node, dict], float]:
    def weight(_u: Node, _v: Node, data: dict) -> float:
        return edge_travel_minutes(data, speed_kmph, weather, is_rush_hour)

    return weight


def summarize_path(graph: nx.Graph, path: list[Node], speed_kmph: float, weather: str = "Clear", is_rush_hour: bool = False) -> RouteResult:
    if not path or len(path) == 1:
        return RouteResult(path=path[:], minutes=0.0, distance_km=0.0, avg_traffic_code=1.0, blocked_edges=0)

    total_minutes = 0.0
    total_distance = 0.0
    traffic_sum = 0
    blocked_edges = 0

    for u, v in zip(path[:-1], path[1:]):
        data = graph[u][v]
        level = data.get("traffic", "Low")
        if level == "Blocked":
            blocked_edges += 1
        total_distance += float(data.get("distance_km", 1.0))
        traffic_sum += traffic_code(level)
        segment_minutes = edge_travel_minutes(data, speed_kmph, weather, is_rush_hour)
        total_minutes += segment_minutes

    edge_count = max(1, len(path) - 1)
    return RouteResult(
        path=path[:],
        minutes=total_minutes,
        distance_km=total_distance,
        avg_traffic_code=traffic_sum / edge_count,
        blocked_edges=blocked_edges,
    )


def fastest_route(graph: nx.Graph, source: Node, target: Node, speed_kmph: float, weather: str = "Clear", is_rush_hour: bool = False) -> RouteResult:
    """Shortest-time route using current traffic as edge weights."""
    try:
        path = nx.shortest_path(graph, source=source, target=target, weight=_edge_weight(speed_kmph, weather, is_rush_hour), method="dijkstra")
    except (nx.NetworkXNoPath, nx.NodeNotFound):
        return RouteResult([], math.inf, math.inf, 4.0, 999)

    result = summarize_path(graph, path, speed_kmph, weather, is_rush_hour)
    if not math.isfinite(result.minutes):
        return RouteResult([], math.inf, math.inf, 4.0, 999)
    return result


def distance_route(graph: nx.Graph, source: Node, target: Node, speed_kmph: float, weather: str = "Clear", is_rush_hour: bool = False) -> RouteResult:
    """Shortest-distance route. Used as the 'normal route' baseline."""
    try:
        path = nx.shortest_path(graph, source=source, target=target, weight="distance_km", method="dijkstra")
    except (nx.NetworkXNoPath, nx.NodeNotFound):
        return RouteResult([], math.inf, math.inf, 4.0, 999)
    return summarize_path(graph, path, speed_kmph, weather, is_rush_hour)


def select_ambulance(
    graph: nx.Graph,
    ambulances: list[Ambulance],
    emergency: Emergency,
    predictor: Optional[object] = None,
    weather: str = "Clear",
    is_rush_hour: bool = False,
) -> Optional[AmbulanceChoice]:
    """Pick the idle ambulance with the lowest predicted ETA to the emergency."""
    choices: list[AmbulanceChoice] = []
    for ambulance in ambulances:
        if not ambulance.is_idle:
            continue
        route = fastest_route(graph, ambulance.current_node, emergency.node, ambulance.speed_kmph, weather, is_rush_hour)
        if not route.is_valid:
            continue
        normal = distance_route(graph, ambulance.current_node, emergency.node, ambulance.speed_kmph, weather, is_rush_hour)

        if predictor is not None:
            predicted = float(
                predictor.predict(
                    distance_km=route.distance_km,
                    avg_traffic_level=route.avg_traffic_code,
                    road_block_count=route.blocked_edges,
                    ambulance_speed_kmph=ambulance.speed_kmph,
                    emergency_severity=emergency.severity,
                )
            )
        else:
            predicted = route.minutes

        # Penalize serious cases very slightly if route is close to response limit.
        response_limit = SEVERITY_RESPONSE_LIMIT_MINUTES.get(emergency.severity, 16.0)
        risk_penalty = max(0.0, predicted - response_limit) * 0.35
        choices.append(
            AmbulanceChoice(
                ambulance=ambulance,
                route=route,
                predicted_minutes=predicted + risk_penalty,
                normal_route_minutes=normal.minutes,
            )
        )

    if not choices:
        return None
    return min(choices, key=lambda c: c.predicted_minutes)


def select_hospital(
    graph: nx.Graph,
    hospitals: list[Hospital],
    emergency: Emergency,
    source_node: Node,
    speed_kmph: float,
    weather: str = "Clear",
    is_rush_hour: bool = False,
) -> Optional[HospitalChoice]:
    """Recommend a hospital using time, open beds, specialty match, and current load."""
    candidates: list[HospitalChoice] = []
    for hospital in hospitals:
        if not hospital.can_accept:
            continue
        route = fastest_route(graph, source_node, hospital.node, speed_kmph, weather, is_rush_hour)
        if not route.is_valid:
            continue
        specialty_penalty = 0.0 if emergency.specialty_needed in hospital.specialties else 7.5
        load_penalty = hospital.load_ratio * 5.0
        bed_bonus = min(3.0, (hospital.beds_available or 0) * 0.4)
        severity_urgency = max(0.0, emergency.severity - 3) * 0.25
        score = route.minutes + specialty_penalty + load_penalty - bed_bonus - severity_urgency
        candidates.append(HospitalChoice(hospital=hospital, route=route, score=score))

    if not candidates:
        return None
    return min(candidates, key=lambda c: c.score)
