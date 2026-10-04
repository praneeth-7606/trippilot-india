from datetime import datetime, timezone
from app.models.itinerary import PlaceCandidate, RouteLeg, RouteOption, RouteStep, GeoPoint
from app.models.trip import FoodPreferences, RoadPreferences
from app.planner.stops import plan_stops


def test_many_nearby_cafes_do_not_become_many_identical_breaks():
    leg = RouteLeg(id="r", from_name="A", to_name="B", distance_km=150, duration_min=240,
        travel_mode="two_wheeler", steps=[RouteStep(title=str(i), gps_coordinates=GeoPoint(lat=10+i*.1,lng=77)) for i in range(5)])
    route = RouteOption(id="r", label="Route", legs=[leg], total_distance_km=150, total_duration_min=240)
    cafes = [PlaceCandidate(id=str(i), name=f"Cafe {i}", category="rest", location=GeoPoint(lat=10.001,lng=77)) for i in range(20)]
    stops = plan_stops(route, datetime(2026,10,10,6,tzinfo=timezone.utc), FoodPreferences(), RoadPreferences(), [], [], [], [], cafes)
    assert len(stops) <= 2
    assert len({s.progress_minutes for s in stops}) == len(stops)
