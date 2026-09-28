from typing import Any, Dict, Optional, Tuple
import requests
from pydantic import BaseModel, Field

from app.i18n import t
from app.tools.location import Place, geocode

# Geographic coordinates for key farming districts (Punjab, Haryana, UP, MP, Rajasthan)
DISTRICT_COORDINATES: Dict[str, Tuple[float, float]] = {
    "ludhiana": (30.9010, 75.8573),
    "amritsar": (31.6340, 74.8723),
    "bathinda": (30.2110, 74.9455),
    "patiala": (30.3398, 76.3869),
    "karnal": (29.6857, 76.9905),
    "hisar": (29.1492, 75.7217),
    "sirsa": (29.5349, 75.0298),
    "varanasi": (25.3176, 82.9739),
    "lucknow": (26.8467, 80.9462),
    "kanpur": (26.4499, 80.3319),
    "indore": (22.7196, 75.8577),
    "bhopal": (23.2599, 77.4126),
    "jaipur": (26.9124, 75.7873),
    "kota": (25.2138, 75.8648),
    "patna": (25.5941, 85.1376),
}


class AgWeatherReport(BaseModel):
    district: str
    temperature_c: float
    relative_humidity: float
    wind_speed_kmh: float
    rain_probability_pct: float
    spray_recommendation: str
    irrigation_advisory: str
    is_live: bool
    source_notice: str


class AgWeatherTool:
    """Agricultural weather advisory tool using Open-Meteo with offline fallback."""

    def __init__(self, timeout_sec: float = 4.0):
        self.timeout_sec = timeout_sec
        self.endpoint = "https://api.open-meteo.com/v1/forecast"

    def resolve_place(self, name: str) -> Optional[Place]:
        """Coordinates for a place name: built-in districts first, then Open-Meteo geocoding."""
        coords = DISTRICT_COORDINATES.get(name.lower().strip())
        if coords:
            return Place(name=name.strip().title(), latitude=coords[0], longitude=coords[1])
        return geocode(name.strip(), self.timeout_sec)

    def get_weather_for_district(
        self, district_name: str = "Ludhiana", language: str = "hi", place: Optional[Place] = None
    ) -> AgWeatherReport:
        """Fetch weather parameters and generate agronomic spraying & irrigation advice in `language`.

        Pass `place` (from resolve_place) for locations outside the built-in district list.
        """
        if place is not None:
            lat, lon = place.latitude, place.longitude
            district_name = place.name
        else:
            clean_dist = district_name.lower().strip()
            lat, lon = DISTRICT_COORDINATES.get(clean_dist, DISTRICT_COORDINATES["ludhiana"])

        try:
            params = {
                "latitude": lat,
                "longitude": lon,
                "current": "temperature_2m,relative_humidity_2m,precipitation,wind_speed_10m",
                "hourly": "precipitation_probability",
                "forecast_days": 1,
            }

            resp = requests.get(self.endpoint, params=params, timeout=self.timeout_sec)
            if resp.status_code == 200:
                data = resp.json()
                current = data.get("current", {})
                hourly = data.get("hourly", {})

                temp = float(current.get("temperature_2m", 24.0))
                humidity = float(current.get("relative_humidity_2m", 60.0))
                wind_speed = float(current.get("wind_speed_10m", 8.0))

                rain_probs = hourly.get("precipitation_probability", [10])
                rain_prob = float(max(rain_probs[:12])) if rain_probs else 10.0

                spray_rec, irr_rec = self._evaluate_agronomic_advisory(wind_speed, rain_prob, temp, language)

                return AgWeatherReport(
                    district=district_name.title(),
                    temperature_c=temp,
                    relative_humidity=humidity,
                    wind_speed_kmh=wind_speed,
                    rain_probability_pct=rain_prob,
                    spray_recommendation=spray_rec,
                    irrigation_advisory=irr_rec,
                    is_live=True,
                    source_notice="Live Open-Meteo Ag-Weather Feed",
                )
        except Exception as e:
            # Fallback gracefully to seasonal cache
            pass

        return self._get_fallback_advisory(district_name, language)

    def _evaluate_agronomic_advisory(
        self, wind_speed: float, rain_prob: float, temp: float, language: str = "hi"
    ) -> Tuple[str, str]:
        """Produce concrete farmer spraying and irrigation advice."""
        # Spray Advisory
        if rain_prob > 40:
            spray = t("spray_rain", language)
        elif wind_speed > 15:
            spray = t("spray_wind", language, wind=wind_speed)
        else:
            spray = t("spray_ok", language)

        # Irrigation Advisory
        if rain_prob > 50:
            irr = t("irrigation_stop", language)
        elif temp > 35:
            irr = t("irrigation_light", language)
        else:
            irr = t("irrigation_normal", language)

        return spray, irr

    def _get_fallback_advisory(self, district_name: str, language: str = "hi") -> AgWeatherReport:
        """Safe seasonal fallback ensuring continuous operation during offline/network failure."""
        return AgWeatherReport(
            district=district_name.title(),
            temperature_c=24.5,
            relative_humidity=58.0,
            wind_speed_kmh=9.2,
            rain_probability_pct=15.0,
            spray_recommendation=t("fallback_spray", language),
            irrigation_advisory=t("fallback_irrigation", language),
            is_live=False,
            source_notice="Offline District Seasonal Climate Cache (Open-Meteo fallback)",
        )
