from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

Node = tuple[int, int]


@dataclass
class Hospital:
    hospital_id: str
    name: str
    node: Node
    beds_total: int
    specialties: set[str]
    beds_available: int | None = None
    current_load: int = 0
    release_times: list[float] = field(default_factory=list)

    def __post_init__(self) -> None:
        if self.beds_available is None:
            self.beds_available = self.beds_total

    @property
    def load_ratio(self) -> float:
        return min(1.0, self.current_load / max(1, self.beds_total))

    @property
    def can_accept(self) -> bool:
        return (self.beds_available or 0) > 0

    def reserve_bed(self) -> bool:
        if not self.can_accept:
            return False
        self.beds_available = int(self.beds_available or 0) - 1
        self.current_load += 1
        return True

    def release_bed(self) -> None:
        if self.current_load > 0:
            self.current_load -= 1
        self.beds_available = min(self.beds_total, int(self.beds_available or 0) + 1)


@dataclass
class Emergency:
    emergency_id: int
    node: Node
    event_type: str
    severity: int
    specialty_needed: str
    created_at: float
    status: str = "waiting"  # waiting, dispatched, picked_up, completed, delayed
    ambulance_id: Optional[str] = None
    hospital_id: Optional[str] = None
    hospital_name: Optional[str] = None
    eta_to_patient_min: Optional[float] = None
    eta_to_hospital_min: Optional[float] = None
    normal_route_min: Optional[float] = None
    optimized_route_min: Optional[float] = None
    completed_at: Optional[float] = None
    delayed_flag: bool = False

    @property
    def total_eta_min(self) -> Optional[float]:
        if self.eta_to_patient_min is None:
            return None
        if self.eta_to_hospital_min is None:
            return self.eta_to_patient_min
        return self.eta_to_patient_min + self.eta_to_hospital_min


@dataclass
class Ambulance:
    ambulance_id: str
    home_node: Node
    current_node: Node
    speed_kmph: float
    x: float
    y: float
    status: str = "idle"  # idle, to_emergency, to_hospital, returning
    route: list[Node] = field(default_factory=list)
    route_index: int = 0
    assigned_emergency_id: Optional[int] = None
    assigned_hospital_id: Optional[str] = None
    path_note: str = ""

    @property
    def is_idle(self) -> bool:
        return self.status == "idle"

    def assign_route(
        self,
        route: list[Node],
        status: str,
        emergency_id: Optional[int] = None,
        hospital_id: Optional[str] = None,
        note: str = "",
    ) -> None:
        self.route = route[:]
        self.route_index = 0
        self.status = status
        self.assigned_emergency_id = emergency_id
        self.assigned_hospital_id = hospital_id
        self.path_note = note
        if route:
            self.current_node = route[0]

    def clear_assignment(self) -> None:
        self.status = "idle"
        self.route = []
        self.route_index = 0
        self.assigned_emergency_id = None
        self.assigned_hospital_id = None
        self.path_note = ""
