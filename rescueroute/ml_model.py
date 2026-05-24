from __future__ import annotations

import math
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from .config import MODEL_PATH

FEATURE_COLUMNS = [
    "distance_km",
    "traffic_level",
    "road_block",
    "ambulance_speed_kmph",
    "emergency_severity",
]


def generate_training_data(rows: int = 5000, seed: int = 42) -> pd.DataFrame:
    """Create simulation-style data for the arrival-time regressor."""
    rng = np.random.default_rng(seed)
    distance = rng.uniform(0.2, 9.0, rows)
    traffic_level = rng.choice([1, 2, 3], rows, p=[0.50, 0.33, 0.17])
    road_block = rng.choice([0, 1], rows, p=[0.93, 0.07])
    speed = rng.normal(48, 7, rows).clip(28, 68)
    severity = rng.choice([1, 2, 3, 4, 5], rows, p=[0.10, 0.18, 0.25, 0.25, 0.22])

    traffic_multiplier = np.select(
        [traffic_level == 1, traffic_level == 2, traffic_level == 3],
        [1.0, 1.55, 2.45],
        default=1.0,
    )
    detour_penalty = road_block * rng.uniform(3.0, 9.0, rows)
    severity_buffer = (6 - severity) * 0.18  # less severe calls may get slightly less priority
    noise = rng.normal(0.0, 0.75, rows)

    arrival_time = (distance / speed) * 60.0 * traffic_multiplier + detour_penalty + severity_buffer + noise
    arrival_time = np.maximum(0.8, arrival_time)

    return pd.DataFrame(
        {
            "distance_km": distance.round(3),
            "traffic_level": traffic_level,
            "road_block": road_block,
            "ambulance_speed_kmph": speed.round(2),
            "emergency_severity": severity,
            "arrival_time_min": arrival_time.round(3),
        }
    )


class ArrivalTimePredictor:
    """Tiny wrapper around a RandomForestRegressor with a safe formula fallback."""

    def __init__(self, model_path: Path = MODEL_PATH, auto_train: bool = True) -> None:
        self.model_path = Path(model_path)
        self.model: Any | None = None
        self.metrics: dict[str, float] = {}
        if auto_train:
            self.load_or_train()

    def load_or_train(self) -> None:
        try:
            import joblib

            if self.model_path.exists():
                bundle = joblib.load(self.model_path)
                self.model = bundle.get("model")
                self.metrics = bundle.get("metrics", {})
                return
        except Exception:
            self.model = None

        try:
            self.train_and_save()
        except Exception:
            # The simulation can still run without sklearn/joblib.
            self.model = None
            self.metrics = {"fallback_formula": 1.0}

    def train_and_save(self, rows: int = 5000, seed: int = 42) -> dict[str, float]:
        from sklearn.ensemble import RandomForestRegressor
        from sklearn.metrics import mean_absolute_error, r2_score
        from sklearn.model_selection import train_test_split
        import joblib

        data = generate_training_data(rows=rows, seed=seed)
        X = data[FEATURE_COLUMNS]
        y = data["arrival_time_min"]
        X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.22, random_state=seed)

        model = RandomForestRegressor(
            n_estimators=140,
            max_depth=12,
            min_samples_leaf=3,
            random_state=seed,
            n_jobs=-1,
        )
        model.fit(X_train, y_train)
        predictions = model.predict(X_test)
        metrics = {
            "mae_minutes": float(mean_absolute_error(y_test, predictions)),
            "r2": float(r2_score(y_test, predictions)),
            "training_rows": float(rows),
        }

        self.model_path.parent.mkdir(parents=True, exist_ok=True)
        joblib.dump({"model": model, "metrics": metrics, "features": FEATURE_COLUMNS}, self.model_path)
        self.model = model
        self.metrics = metrics
        return metrics

    def predict(
        self,
        distance_km: float,
        avg_traffic_level: float,
        road_block_count: int,
        ambulance_speed_kmph: float,
        emergency_severity: int,
    ) -> float:
        features = pd.DataFrame(
            [
                {
                    "distance_km": max(0.0, float(distance_km)),
                    "traffic_level": float(avg_traffic_level),
                    "road_block": 1 if road_block_count > 0 else 0,
                    "ambulance_speed_kmph": max(1.0, float(ambulance_speed_kmph)),
                    "emergency_severity": int(emergency_severity),
                }
            ],
            columns=FEATURE_COLUMNS,
        )
        if self.model is not None:
            try:
                return max(0.5, float(self.model.predict(features)[0]))
            except Exception:
                pass
        return self._fallback_predict(
            distance_km=distance_km,
            avg_traffic_level=avg_traffic_level,
            road_block_count=road_block_count,
            ambulance_speed_kmph=ambulance_speed_kmph,
            emergency_severity=emergency_severity,
        )

    @staticmethod
    def _fallback_predict(
        distance_km: float,
        avg_traffic_level: float,
        road_block_count: int,
        ambulance_speed_kmph: float,
        emergency_severity: int,
    ) -> float:
        multiplier = {1: 1.0, 2: 1.55, 3: 2.45, 4: 9999.0}.get(int(round(avg_traffic_level)), 1.4)
        if not math.isfinite(multiplier) or multiplier > 100:
            multiplier = 4.0
        severity_buffer = max(0, 6 - int(emergency_severity)) * 0.18
        return max(0.5, (float(distance_km) / max(1.0, float(ambulance_speed_kmph))) * 60.0 * multiplier + road_block_count * 5.0 + severity_buffer)
