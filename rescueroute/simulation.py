from __future__ import annotations

import csv
import math
import random
from collections import deque
from pathlib import Path
from typing import Optional

from .city import build_city_graph, randomize_traffic as refresh_city_traffic, toggle_random_block as city_toggle_random_block
from .config import (
    AUTO_EMERGENCY_MAX_SECONDS,
    AUTO_EMERGENCY_MIN_SECONDS,
    BASE_AMBULANCE_PIXELS_PER_SECOND,
    CASE_LOG_PATH,
    DATA_DIR,
    EMERGENCY_TYPES,
    MAX_ACTIVE_EMERGENCIES,
    SEVERITY_RESPONSE_LIMIT_MINUTES,
    SNAPSHOT_LOG_PATH,
    SNAPSHOT_SECONDS,
    TRAFFIC_LEVELS,
    TRAFFIC_REFRESH_SECONDS,
)
from .entities import Ambulance, Emergency, Hospital, Node
from .ml_model import ArrivalTimePredictor
from .routing import distance_route, fastest_route, select_ambulance, select_hospital, traffic_multiplier


class Simulation:
    """Core emergency dispatch simulation independent of Pygame drawing."""

    def __init__(self, seed: int = 7) -> None:
        self.rng = random.Random(seed)
        self.graph, self.hospitals, self.ambulances = build_city_graph(seed=seed)
        self.predictor = ArrivalTimePredictor(auto_train=True)

        self.sim_time = 0.0
        self.next_emergency_in = self.rng.uniform(AUTO_EMERGENCY_MIN_SECONDS, AUTO_EMERGENCY_MAX_SECONDS)
        self.traffic_timer = 0.0
        self.dispatch_retry_timer = 0.0
        self.snapshot_timer = 0.0
        self.next_emergency_id = 1

        self.emergencies: dict[int, Emergency] = {}
        self.messages: deque[str] = deque(maxlen=8)
        self.generated_cases = 0
        self.saved_cases = 0
        self.delayed_cases = 0
        self.total_response_minutes = 0.0
        self.completed_cases = 0
        self.last_route_compare = {"optimized": 0.0, "normal": 0.0}
        self.last_completed: Optional[Emergency] = None

        DATA_DIR.mkdir(parents=True, exist_ok=True)
        self._ensure_log_headers()
        self.add_message("System online. Press SPACE to create an emergency.")

    @property
    def active_emergencies(self) -> list[Emergency]:
        return [e for e in self.emergencies.values() if e.status not in {"completed", "closed"}]

    @property
    def waiting_emergencies(self) -> list[Emergency]:
        return [e for e in self.active_emergencies if e.status == "waiting"]

    @property
    def available_ambulances(self) -> int:
        return sum(1 for ambulance in self.ambulances if ambulance.is_idle)

    @property
    def open_beds(self) -> int:
        return sum(int(h.beds_available or 0) for h in self.hospitals)

    @property
    def avg_response_minutes(self) -> float:
        if self.completed_cases == 0:
            return 0.0
        return self.total_response_minutes / self.completed_cases

    def add_message(self, text: str) -> None:
        self.messages.appendleft(text)

    def update(self, dt: float) -> None:
        self.sim_time += dt
        self.next_emergency_in -= dt
        self.traffic_timer += dt
        self.dispatch_retry_timer += dt
        self.snapshot_timer += dt

        if self.next_emergency_in <= 0:
            self.spawn_emergency(force=False)
            self.next_emergency_in = self.rng.uniform(AUTO_EMERGENCY_MIN_SECONDS, AUTO_EMERGENCY_MAX_SECONDS)

        if self.traffic_timer >= TRAFFIC_REFRESH_SECONDS:
            self.randomize_traffic(show_message=True)
            self.traffic_timer = 0.0

        if self.dispatch_retry_timer >= 1.25:
            self.retry_waiting_dispatches()
            self.dispatch_retry_timer = 0.0

        self._release_hospital_beds()
        self._mark_long_waits()

        for ambulance in self.ambulances:
            self._update_ambulance(ambulance, dt)

        if self.snapshot_timer >= SNAPSHOT_SECONDS:
            self.write_snapshot()
            self.snapshot_timer = 0.0

    def spawn_emergency(self, force: bool = True) -> Optional[Emergency]:
        if not force and len(self.active_emergencies) >= MAX_ACTIVE_EMERGENCIES:
            return None

        hospital_nodes = {hospital.node for hospital in self.hospitals}
        active_nodes = {emergency.node for emergency in self.active_emergencies}
        candidate_nodes = [node for node in self.graph.nodes if node not in hospital_nodes and node not in active_nodes]
        if not candidate_nodes:
            return None

        node = self.rng.choice(candidate_nodes)
        event_type = self.rng.choices(
            list(EMERGENCY_TYPES.keys()),
            weights=[0.26, 0.22, 0.18, 0.20, 0.14],
            k=1,
        )[0]
        meta = EMERGENCY_TYPES[event_type]
        emergency = Emergency(
            emergency_id=self.next_emergency_id,
            node=node,
            event_type=event_type,
            severity=int(meta["severity"]),
            specialty_needed=str(meta["specialty"]),
            created_at=self.sim_time,
        )
        self.next_emergency_id += 1
        self.generated_cases += 1
        self.emergencies[emergency.emergency_id] = emergency
        self.add_message(f"Emergency #{emergency.emergency_id}: {event_type} at node {node}.")
        self.dispatch(emergency)
        return emergency

    def dispatch(self, emergency: Emergency) -> bool:
        if emergency.status != "waiting":
            return False
        choice = select_ambulance(self.graph, self.ambulances, emergency, predictor=self.predictor)
        if choice is None:
            self.add_message(f"Emergency #{emergency.emergency_id} waiting: no reachable idle ambulance.")
            return False

        ambulance = choice.ambulance
        emergency.status = "dispatched"
        emergency.ambulance_id = ambulance.ambulance_id
        emergency.eta_to_patient_min = choice.predicted_minutes
        emergency.optimized_route_min = choice.route.minutes
        emergency.normal_route_min = choice.normal_route_minutes
        self.last_route_compare = {
            "optimized": choice.route.minutes,
            "normal": choice.normal_route_minutes if math.isfinite(choice.normal_route_minutes) else choice.route.minutes,
        }

        ambulance.assign_route(
            route=choice.route.path,
            status="to_emergency",
            emergency_id=emergency.emergency_id,
            note=f"To emergency #{emergency.emergency_id}",
        )
        self.add_message(
            f"Dispatch {ambulance.ambulance_id} → emergency #{emergency.emergency_id} "
            f"ETA {choice.predicted_minutes:.1f} min."
        )
        return True

    def retry_waiting_dispatches(self) -> None:
        for emergency in list(self.waiting_emergencies):
            self.dispatch(emergency)

    def randomize_traffic(self, show_message: bool = False) -> None:
        refresh_city_traffic(self.graph, self.rng)
        if show_message:
            self.add_message("Traffic updated: jams and blocked roads changed.")

    def toggle_random_block(self) -> None:
        u, v, status = city_toggle_random_block(self.graph, self.rng)
        self.add_message(f"Road {u} ↔ {v} set to {status}.")

    def reset_traffic_low(self) -> None:
        for _u, _v, data in self.graph.edges(data=True):
            data["traffic"] = "Low"
        self.add_message("All roads cleared to low traffic.")

    def _update_ambulance(self, ambulance: Ambulance, dt: float) -> None:
        if ambulance.status == "idle":
            return

        if not ambulance.route or ambulance.route_index >= len(ambulance.route) - 1:
            self._handle_ambulance_arrival(ambulance)
            return

        start_node = ambulance.route[ambulance.route_index]
        target_node = ambulance.route[ambulance.route_index + 1]
        target_x, target_y = self.graph.nodes[target_node]["pos"]
        dx = target_x - ambulance.x
        dy = target_y - ambulance.y
        distance_pixels = math.hypot(dx, dy)
        if distance_pixels <= 0.01:
            ambulance.x = float(target_x)
            ambulance.y = float(target_y)
            ambulance.current_node = target_node
            ambulance.route_index += 1
            if ambulance.route_index >= len(ambulance.route) - 1:
                self._handle_ambulance_arrival(ambulance)
            return

        edge_data = self.graph.get_edge_data(start_node, target_node, default={"traffic": "Medium"})
        level = str(edge_data.get("traffic", "Medium"))
        multiplier = traffic_multiplier(level)
        if level == "Blocked" or multiplier > 50:
            # Already committed to the segment; move very slowly instead of freezing.
            multiplier = 3.2
        speed = BASE_AMBULANCE_PIXELS_PER_SECOND / multiplier
        step = speed * dt

        if step >= distance_pixels:
            ambulance.x = float(target_x)
            ambulance.y = float(target_y)
            ambulance.current_node = target_node
            ambulance.route_index += 1
            if ambulance.route_index >= len(ambulance.route) - 1:
                self._handle_ambulance_arrival(ambulance)
        else:
            ambulance.x += (dx / distance_pixels) * step
            ambulance.y += (dy / distance_pixels) * step

    def _handle_ambulance_arrival(self, ambulance: Ambulance) -> None:
        if ambulance.status == "to_emergency":
            emergency = self.emergencies.get(int(ambulance.assigned_emergency_id or -1))
            if emergency is None or emergency.status in {"completed", "closed"}:
                ambulance.clear_assignment()
                return
            emergency.status = "picked_up"
            self.add_message(f"{ambulance.ambulance_id} reached emergency #{emergency.emergency_id}.")

            hospital_choice = select_hospital(
                self.graph,
                self.hospitals,
                emergency,
                source_node=emergency.node,
                speed_kmph=ambulance.speed_kmph,
            )
            if hospital_choice is None:
                self._close_case_without_hospital(emergency, ambulance)
                return

            hospital = hospital_choice.hospital
            hospital.reserve_bed()
            emergency.hospital_id = hospital.hospital_id
            emergency.hospital_name = hospital.name
            emergency.eta_to_hospital_min = hospital_choice.route.minutes
            ambulance.assign_route(
                route=hospital_choice.route.path,
                status="to_hospital",
                emergency_id=emergency.emergency_id,
                hospital_id=hospital.hospital_id,
                note=f"To {hospital.name}",
            )
            self.add_message(
                f"Hospital selected: {hospital.name} "
                f"({hospital.beds_available}/{hospital.beds_total} beds open)."
            )
            return

        if ambulance.status == "to_hospital":
            emergency = self.emergencies.get(int(ambulance.assigned_emergency_id or -1))
            hospital = self._find_hospital(ambulance.assigned_hospital_id)
            if emergency is not None:
                self._complete_case(emergency, ambulance, hospital)
            self._send_ambulance_home(ambulance)
            return

        if ambulance.status == "returning":
            ambulance.current_node = ambulance.home_node
            ambulance.clear_assignment()
            self.add_message(f"{ambulance.ambulance_id} returned to station.")

    def _send_ambulance_home(self, ambulance: Ambulance) -> None:
        route = fastest_route(self.graph, ambulance.current_node, ambulance.home_node, ambulance.speed_kmph)
        if route.is_valid:
            ambulance.assign_route(route=route.path, status="returning", note="Returning to station")
        else:
            home_x, home_y = self.graph.nodes[ambulance.home_node]["pos"]
            ambulance.x = float(home_x)
            ambulance.y = float(home_y)
            ambulance.current_node = ambulance.home_node
            ambulance.clear_assignment()

    def _close_case_without_hospital(self, emergency: Emergency, ambulance: Ambulance) -> None:
        emergency.status = "completed"
        emergency.completed_at = self.sim_time
        emergency.delayed_flag = True
        emergency.hospital_name = "No hospital available"
        self.delayed_cases += 1
        self.completed_cases += 1
        self.last_completed = emergency
        self.write_case_log(emergency, outcome="Delayed")
        self.add_message(f"Case #{emergency.emergency_id} delayed: no hospital beds/path available.")
        self._send_ambulance_home(ambulance)

    def _complete_case(self, emergency: Emergency, ambulance: Ambulance, hospital: Optional[Hospital]) -> None:
        emergency.status = "completed"
        emergency.completed_at = self.sim_time
        response = float(emergency.eta_to_patient_min or 0.0)
        limit = SEVERITY_RESPONSE_LIMIT_MINUTES.get(emergency.severity, 16.0)
        outcome = "Saved" if response <= limit else "Delayed"
        emergency.delayed_flag = outcome != "Saved"

        if outcome == "Saved":
            self.saved_cases += 1
        else:
            self.delayed_cases += 1

        self.completed_cases += 1
        self.total_response_minutes += response
        self.last_completed = emergency
        self.write_case_log(emergency, outcome=outcome)

        if hospital is not None:
            release_after = self.rng.uniform(24.0, 42.0)
            hospital.release_times.append(self.sim_time + release_after)

        self.add_message(
            f"Case #{emergency.emergency_id} {outcome.lower()} at "
            f"{emergency.hospital_name or 'hospital'}; response {response:.1f} min."
        )

    def _find_hospital(self, hospital_id: Optional[str]) -> Optional[Hospital]:
        if hospital_id is None:
            return None
        return next((hospital for hospital in self.hospitals if hospital.hospital_id == hospital_id), None)

    def _release_hospital_beds(self) -> None:
        for hospital in self.hospitals:
            pending = []
            released = 0
            for release_time in hospital.release_times:
                if self.sim_time >= release_time:
                    hospital.release_bed()
                    released += 1
                else:
                    pending.append(release_time)
            hospital.release_times = pending
            if released:
                self.add_message(f"{hospital.name}: {released} bed released.")

    def _mark_long_waits(self) -> None:
        for emergency in self.active_emergencies:
            if emergency.delayed_flag:
                continue
            if emergency.status == "waiting" and (self.sim_time - emergency.created_at) > 18.0:
                emergency.delayed_flag = True
                self.add_message(f"Emergency #{emergency.emergency_id} is at risk due to long wait.")

    def _ensure_log_headers(self) -> None:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        if not CASE_LOG_PATH.exists():
            with CASE_LOG_PATH.open("w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=self._case_log_fields())
                writer.writeheader()
        if not SNAPSHOT_LOG_PATH.exists():
            with SNAPSHOT_LOG_PATH.open("w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=self._snapshot_fields())
                writer.writeheader()

    @staticmethod
    def _case_log_fields() -> list[str]:
        return [
            "sim_time_seconds",
            "case_id",
            "event_type",
            "severity",
            "ambulance_id",
            "hospital",
            "eta_to_patient_min",
            "eta_to_hospital_min",
            "total_eta_min",
            "optimized_route_min",
            "normal_route_min",
            "outcome",
        ]

    @staticmethod
    def _snapshot_fields() -> list[str]:
        return [
            "sim_time_seconds",
            "generated_cases",
            "active_emergencies",
            "available_ambulances",
            "open_hospital_beds",
            "saved_cases",
            "delayed_cases",
            "completed_cases",
            "avg_response_min",
            "last_optimized_route_min",
            "last_normal_route_min",
        ]

    def write_case_log(self, emergency: Emergency, outcome: str) -> None:
        row = {
            "sim_time_seconds": round(self.sim_time, 2),
            "case_id": emergency.emergency_id,
            "event_type": emergency.event_type,
            "severity": emergency.severity,
            "ambulance_id": emergency.ambulance_id or "",
            "hospital": emergency.hospital_name or "",
            "eta_to_patient_min": round(float(emergency.eta_to_patient_min or 0), 2),
            "eta_to_hospital_min": round(float(emergency.eta_to_hospital_min or 0), 2),
            "total_eta_min": round(float(emergency.total_eta_min or 0), 2),
            "optimized_route_min": round(float(emergency.optimized_route_min or 0), 2),
            "normal_route_min": round(float(emergency.normal_route_min or 0), 2),
            "outcome": outcome,
        }
        with CASE_LOG_PATH.open("a", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=self._case_log_fields())
            writer.writerow(row)

    def write_snapshot(self) -> None:
        row = {
            "sim_time_seconds": round(self.sim_time, 2),
            "generated_cases": self.generated_cases,
            "active_emergencies": len(self.active_emergencies),
            "available_ambulances": self.available_ambulances,
            "open_hospital_beds": self.open_beds,
            "saved_cases": self.saved_cases,
            "delayed_cases": self.delayed_cases,
            "completed_cases": self.completed_cases,
            "avg_response_min": round(self.avg_response_minutes, 2),
            "last_optimized_route_min": round(float(self.last_route_compare.get("optimized", 0.0)), 2),
            "last_normal_route_min": round(float(self.last_route_compare.get("normal", 0.0)), 2),
        }
        with SNAPSHOT_LOG_PATH.open("a", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=self._snapshot_fields())
            writer.writerow(row)

    def export_demo_data(self) -> dict[str, Path]:
        self.write_snapshot()
        return {"cases": CASE_LOG_PATH, "snapshots": SNAPSHOT_LOG_PATH}
