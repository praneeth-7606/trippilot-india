"""Generate SYNTHETIC provider-shaped test inputs. No data here is a live capture.

The landmarks are illustrative; coordinates, hours, distances, weather and
stop names are test assumptions, not travel advice or verified listings.
"""
import json
from pathlib import Path

ROOT = Path(__file__).parent
fixtures = {}


def add(key, engine, response):
    fixtures[key] = {"_engine": engine, "_provenance": "synthetic test input", "response": response}


points = [("Coimbatore", 11.0168, 76.9558), ("Pollachi", 10.6588, 77.0072),
          ("Udumalpet", 10.5847, 77.2403), ("Marayoor", 10.2769, 77.1629),
          ("Munnar", 10.0889, 77.0595)]

for mode, duration in [("two_wheeler", 245), ("driving", 230)]:
    for origin, dest, waypoints in [("coimbatore", "munnar", points),
                                    ("munnar", "coimbatore", list(reversed(points)))]:
        routes = []
        for factor in [1, 1.15]:
            steps = [{"title": f"Continue toward {p[0]}", "distance": 35000,
                      "duration": round(duration * 60 * factor / 4),
                      "gps_coordinates": {"latitude": p[1], "longitude": p[2]}}
                     for p in waypoints]
            routes.append({"via": "Synthetic route A" if factor == 1 else "Synthetic route B",
                "distance": round(140000 * factor), "duration": round(duration * 60 * factor),
                "trips": [{"details": steps}]})
        add(f"dir:{origin}:{dest}:{mode}", "google_maps_directions", {
            "directions": routes, "places_info": [{"address": p[0], "gps_coordinates":
                {"latitude": p[1], "longitude": p[2]}} for p in [waypoints[0], waypoints[-1]]]})


def place(name, lat, lng, hours=None):
    data = {"title": name, "data_id": "synthetic-" + name.lower().replace(" ", "-"),
        "address": "Synthetic fixture location; confirm before travel", "rating": 4.2,
        "gps_coordinates": {"latitude": lat, "longitude": lng}}
    if hours:
        data["opening_hours"] = {"open": hours[0], "close": hours[1]}
    return data


add("places:munnar:attractions", "google_maps", {"local_results": [
    place("Tea Museum", 10.092, 77.052, ("09:00", "17:00")),
    place("Mattupetty Dam", 10.106, 77.125, ("09:00", "17:00")),
    place("Echo Point", 10.117, 77.155, ("09:00", "17:00")),
    place("Top Station", 10.125, 77.246),
    place("Blossom Park", 10.071, 77.065, ("09:00", "17:00"))]})

for kind, name in [("food", "Vegetarian meal stop"), ("fuel", "Fuel candidate"),
                   ("washroom", "Washroom candidate"), ("rest", "Rest candidate")]:
    add(f"places:route:{kind}", "google_maps", {"local_results": [
        place(f"{name} — Pollachi [synthetic]", 10.6588, 77.0072),
        place(f"{name} — Udumalpet [synthetic]", 10.5847, 77.2403),
        place(f"{name} — Marayoor [synthetic]", 10.2769, 77.1629)]})
add("places:munnar:food", "google_maps", {"local_results": [
    place("Vegetarian lunch — Munnar [synthetic]", 10.089, 77.060)]})
add("search:munnar:advisory", "google", {"organic_results": [{
    "title": "Kerala Tourism", "link": "https://www.keralatourism.org/",
    "snippet": "Synthetic advisory fixture: consult official attraction rules, closures and permits before departure."}]})

if __name__ == "__main__":
    (ROOT / "serpapi.json").write_text(json.dumps(fixtures, indent=2), encoding="utf-8")
    (ROOT / "openmeteo.json").write_text(json.dumps({"weather:munnar": [
        {"summary": "Synthetic: partly cloudy", "max_c": 24, "min_c": 15, "precip": 20},
        {"summary": "Synthetic: rain showers", "max_c": 22, "min_c": 14, "precip": 50}]
    }, indent=2), encoding="utf-8")
    print(f"Generated {len(fixtures)} synthetic SerpApi scenarios and 2 weather rows")
