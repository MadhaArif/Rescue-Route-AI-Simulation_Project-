from __future__ import annotations

import math
import random
from typing import Iterable

import networkx as nx

from .config import AMBULANCE_SPEED_KMPH, TRAFFIC_LEVELS
from .entities import Ambulance, Hospital, Node


def node_position(row: int, col: int) -> tuple[int, int]:
    """Convert a logical grid node into screen coordinates."""
    x0, y0 = 75, 70
    spacing_x, spacing_y = 135, 120
    # Slight row offsets make the map look less like a boring square grid.
    x = x0 + col * spacing_x + (18 if row % 2 else 0)
    y = y0 + row * spacing_y
    return x, y


def _distance_km(a: tuple[int, int], b: tuple[int, int]) -> float:
    pixels = math.dist(a, b)
    # Visual pixels are scaled to tiny-city kilometers.
    return max(0.25, pixels / 105.0)


def _traffic_choice(rng: random.Random) -> str:
    return rng.choices(["Low", "Medium", "High", "Blocked"], weights=[0.50, 0.30, 0.16, 0.04], k=1)[0]


def build_city_graph(seed: int = 11) -> tuple[nx.Graph, list[Hospital], list[Ambulance]]:
    """Build a small connected city graph with roads, hospitals, and ambulances."""
    rng = random.Random(seed)
    graph = nx.Graph(name="RescueRoute Mini City")

    rows, cols = 5, 6
    for row in range(rows):
        for col in range(cols):
            node: Node = (row, col)
            x, y = node_position(row, col)
            graph.add_node(node, pos=(x, y), label=f"{row},{col}")

    def add_road(a: Node, b: Node, road_type: str = "street") -> None:
        ax, ay = graph.nodes[a]["pos"]
        bx, by = graph.nodes[b]["pos"]
        graph.add_edge(
            a,
            b,
            distance_km=round(_distance_km((ax, ay), (bx, by)), 2),
            traffic=_traffic_choice(rng),
            road_type=road_type,
        )

    for row in range(rows):
        for col in range(cols):
            if col < cols - 1:
                add_road((row, col), (row, col + 1))
            if row < rows - 1:
                add_road((row, col), (row + 1, col))

    # A few diagonals/highways create route choice and make Dijkstra visibly useful.
    extra_roads: Iterable[tuple[Node, Node, str]] = [
        ((0, 1), (1, 2), "diagonal"),
        ((1, 2), (2, 3), "diagonal"),
        ((2, 3), (3, 4), "diagonal"),
        ((3, 4), (4, 5), "diagonal"),
        ((1, 0), (2, 1), "diagonal"),
        ((2, 1), (3, 2), "diagonal"),
        ((3, 2), (4, 3), "diagonal"),
        ((0, 4), (1, 3), "diagonal"),
        ((1, 3), (2, 2), "diagonal"),
        ((2, 2), (3, 1), "diagonal"),
        ((3, 1), (4, 0), "diagonal"),
    ]
    for a, b, road_type in extra_roads:
        add_road(a, b, road_type)

    hospitals = [
        Hospital(
            hospital_id="H1",
            name="NorthCare Hospital",
            node=(0, 5),
            beds_total=5,
            specialties={"cardiac", "trauma", "general", "icu"},
        ),
        Hospital(
            hospital_id="H2",
            name="City General Hospital",
            node=(4, 0),
            beds_total=4,
            specialties={"burn", "trauma", "general", "icu"},
        ),
    ]

    ambulances = []
    for ambulance_id, home_node in [("A1", (0, 0)), ("A2", (4, 5)), ("A3", (2, 2))]:
        x, y = graph.nodes[home_node]["pos"]
        ambulances.append(
            Ambulance(
                ambulance_id=ambulance_id,
                home_node=home_node,
                current_node=home_node,
                speed_kmph=AMBULANCE_SPEED_KMPH,
                x=float(x),
                y=float(y),
            )
        )

    return graph, hospitals, ambulances


def randomize_traffic(graph: nx.Graph, rng: random.Random, block_probability: float = 0.04) -> None:
    """Refresh road traffic. Blocked roads are rare so the map stays playable."""
    for _u, _v, data in graph.edges(data=True):
        data["traffic"] = rng.choices(
            ["Low", "Medium", "High", "Blocked"],
            weights=[0.54, 0.29, max(0.01, 1.0 - 0.54 - 0.29 - block_probability), block_probability],
            k=1,
        )[0]


def toggle_random_block(graph: nx.Graph, rng: random.Random) -> tuple[Node, Node, str]:
    """Toggle one random edge between blocked and low traffic."""
    edge = rng.choice(list(graph.edges()))
    u, v = edge
    data = graph[u][v]
    data["traffic"] = "Low" if data.get("traffic") == "Blocked" else "Blocked"
    return u, v, data["traffic"]


def traffic_color(level: str) -> tuple[int, int, int]:
    return TRAFFIC_LEVELS.get(level, TRAFFIC_LEVELS["Low"])["color"]
