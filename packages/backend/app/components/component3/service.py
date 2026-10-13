from __future__ import annotations

import hashlib
import json
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any

SERVICE_CATEGORIES = (
    "Masons",
    "Carpenters",
    "Tile Workers",
    "Plumbers",
    "Electricians",
    "Technicians",
    "Painters",
    "A/C Services",
    "Cleaners",
    "Vehicle Repairs",
    "CCTV Installation",
    "Well Services",
    "Cushion Works",
    "Ceiling Works",
)

BASE_DEMAND = {
    "Electricians": 35,
    "Plumbers": 30,
    "Technicians": 28,
    "Cleaners": 32,
    "Vehicle Repairs": 24,
    "A/C Services": 22,
    "Painters": 18,
    "Carpenters": 16,
    "Tile Workers": 14,
    "Masons": 13,
    "CCTV Installation": 12,
    "Ceiling Works": 11,
    "Well Services": 8,
    "Cushion Works": 7,
}

ARTIFACT_FILES = ("best_model.pkl", "label_encoders.pkl", "feature_columns.pkl")
DAYS = ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday")


class Component3ArtifactError(RuntimeError):
    """Raised when the demand model bundle is missing or incompatible."""


def demand_level(avg_daily: float) -> str:
    if avg_daily <= 10:
        return "LOW"
    if avg_daily <= 25:
        return "MEDIUM"
    return "HIGH"


def next_week_dates(compile_date: date) -> list[date]:
    next_monday = compile_date + timedelta(days=7 - compile_date.weekday())
    return [next_monday + timedelta(days=offset) for offset in range(7)]


class Component3DemandService:
    """Generate the Component 3 weekly forecast from a versioned artifact bundle."""

    def __init__(
        self,
        artifact_dir: Path,
        *,
        model: Any | None = None,
        target_encoder: Any | None = None,
        feature_columns: list[str] | None = None,
    ) -> None:
        self.artifact_dir = Path(artifact_dir)
        self.model = model
        self.target_encoder = target_encoder
        self.feature_columns = feature_columns
        self.artifact_version = "demand-v1"

    @staticmethod
    def _sha256(path: Path) -> str:
        digest = hashlib.sha256()
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()

    def _load_artifacts(self) -> None:
        manifest_path = self.artifact_dir / "manifest.json"
        if not manifest_path.is_file():
            raise Component3ArtifactError(f"Missing Component 3 manifest: {manifest_path}")
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            raise Component3ArtifactError("Component 3 manifest is invalid") from error

        checksums = manifest.get("checksums")
        if not isinstance(checksums, dict):
            raise Component3ArtifactError("Component 3 manifest has no checksums")
        for name in ARTIFACT_FILES:
            path = self.artifact_dir / name
            if not path.is_file():
                raise Component3ArtifactError(f"Missing Component 3 artifact: {name}")
            expected = str(checksums.get(name, "")).lower()
            if not expected or self._sha256(path) != expected:
                raise Component3ArtifactError(f"Checksum mismatch for Component 3 artifact: {name}")

        try:
            import joblib

            self.model = joblib.load(self.artifact_dir / "best_model.pkl")
            encoders = joblib.load(self.artifact_dir / "label_encoders.pkl")
            self.feature_columns = list(joblib.load(self.artifact_dir / "feature_columns.pkl"))
            self.target_encoder = encoders["target_encoder"]
            # Older category-encoders artifacts predate this empty transform mapping.
            encoder_chain = [
                self.target_encoder,
                getattr(self.target_encoder, "ordinal_encoder", None),
            ]
            for encoder in encoder_chain:
                if encoder is not None and not hasattr(encoder, "min_group_lumping_"):
                    encoder.min_group_lumping_ = {}
        except (ImportError, KeyError, TypeError, ValueError) as error:
            raise Component3ArtifactError("Could not load Component 3 artifacts") from error
        self.artifact_version = str(manifest.get("artifact_version") or "demand-v1")

    @staticmethod
    def _feature_rows(dates: list[date]) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for forecast_date in dates:
            weekday = forecast_date.strftime("%A")
            weekend = int(weekday in {"Saturday", "Sunday"})
            week = int(forecast_date.isocalendar().week)
            for category in SERVICE_CATEGORIES:
                base = BASE_DEMAND.get(category, 20)
                previous_orders = base
                last_seven = base
                if weekend and category in {"Vehicle Repairs", "Cleaners", "A/C Services"}:
                    previous_orders += 3
                    last_seven += 2
                rows.append(
                    {
                        "day_of_week": weekday,
                        "month": forecast_date.month,
                        "week_of_year": week,
                        "service_category": category,
                        "district": "Colombo",
                        "city": "Colombo",
                        "rainfall_mm": 10.0,
                        "temperature_c": 30.0,
                        "humidity": 75,
                        "weekend": weekend,
                        "holiday": 0,
                        "available_providers": 20,
                        "previous_day_orders": previous_orders,
                        "last_7_day_avg": last_seven,
                        "last_30_day_avg": base,
                        "search_requests": base * 3,
                        "completed_orders": max(0, base - 2),
                        "cancelled_orders": 1,
                        "avg_provider_rating": 4.5,
                        "avg_distance_km": 5.0,
                        "year": forecast_date.year,
                        "day": forecast_date.day,
                        "week": week,
                        "weekday": forecast_date.weekday(),
                        "day_of_year": forecast_date.timetuple().tm_yday,
                    }
                )
        return rows

    def generate(self, compile_date: date | None = None) -> dict[str, Any]:
        if self.model is None or self.target_encoder is None or self.feature_columns is None:
            self._load_artifacts()
        assert self.model is not None
        assert self.target_encoder is not None
        assert self.feature_columns is not None

        try:
            import numpy as np
            import pandas as pd
        except ImportError as error:
            raise Component3ArtifactError(
                "Component 3 runtime dependencies are not installed"
            ) from error

        compiled_on = compile_date or datetime.now(UTC).date()
        forecast_dates = next_week_dates(compiled_on)
        input_frame = pd.DataFrame(self._feature_rows(forecast_dates))
        encoded = self.target_encoder.transform(input_frame)
        encoded.columns = [str(column) for column in encoded.columns]
        missing = [column for column in self.feature_columns if column not in encoded.columns]
        if missing:
            raise Component3ArtifactError(
                f"Component 3 encoder output is missing features: {', '.join(missing)}"
            )

        predictions = self.model.predict(encoded[self.feature_columns])
        if len(predictions) != len(input_frame):
            raise Component3ArtifactError("Component 3 model returned an unexpected row count")
        input_frame["predicted_order_count"] = np.maximum(1, np.round(predictions)).astype(int)

        by_category: dict[str, dict[str, Any]] = {}
        summary: list[dict[str, Any]] = []
        for category in SERVICE_CATEGORIES:
            category_rows = input_frame[input_frame["service_category"] == category]
            day_predictions = {
                day: int(
                    category_rows.loc[
                        category_rows["day_of_week"] == day,
                        "predicted_order_count",
                    ].iloc[0]
                )
                for day in DAYS
            }
            total = sum(day_predictions.values())
            average = round(total / 7.0, 1)
            level = demand_level(average)
            summary.append(
                {
                    "Service Category": category,
                    **day_predictions,
                    "Total Weekly Orders": total,
                    "Avg Daily Orders": average,
                    "Weekly Demand Level": level,
                }
            )
            safe_key = category.translate(str.maketrans({"/": "_", ".": "_", "#": "_", "$": "_"}))
            by_category[safe_key] = {
                "service_category": category,
                **day_predictions,
                "total_weekly": total,
                "avg_daily": average,
                "demand_level": level,
            }

        summary.sort(key=lambda item: item["Total Weekly Orders"], reverse=True)
        start_date, end_date = forecast_dates[0], forecast_dates[-1]
        return {
            "component_version": "component3-v1",
            "model_version": self.artifact_version,
            "compile_date": compiled_on.isoformat(),
            "target_week": f"{start_date} (Monday) to {end_date} (Sunday)",
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
            "last_updated": datetime.now(UTC).isoformat(),
            "by_category": by_category,
            "summary": summary,
        }
