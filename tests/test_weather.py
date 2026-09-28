import pytest
from app.tools.weather_tool import AgWeatherReport, AgWeatherTool


def test_weather_tool_fetch():
    tool = AgWeatherTool(timeout_sec=4.0)
    report = tool.get_weather_for_district("Ludhiana")

    assert isinstance(report, AgWeatherReport)
    assert report.district == "Ludhiana"
    assert report.temperature_c > -20.0
    assert report.relative_humidity >= 0.0
    assert len(report.spray_recommendation) > 0
    assert len(report.irrigation_advisory) > 0


def test_weather_advisory_logic_high_wind():
    tool = AgWeatherTool()
    spray, irr = tool._evaluate_agronomic_advisory(wind_speed=22.0, rain_prob=10.0, temp=25.0)
    assert "तेज हवा" in spray or "drift" in spray.lower()


def test_weather_advisory_logic_high_rain():
    tool = AgWeatherTool()
    spray, irr = tool._evaluate_agronomic_advisory(wind_speed=8.0, rain_prob=75.0, temp=22.0)
    assert "स्थगित" in spray or "वर्षा" in spray


def test_weather_fallback():
    tool = AgWeatherTool()
    fallback = tool._get_fallback_advisory("Karnal")
    assert fallback.district == "Karnal"
    assert fallback.is_live is False
    assert "fallback" in fallback.source_notice.lower()
