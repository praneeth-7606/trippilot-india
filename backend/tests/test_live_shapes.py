from datetime import date, datetime, timezone
from app.models.itinerary import PlaceCategory
from app.services.maps import parse_places
from app.services.serpapi import ProviderResponse


def test_maps_weekly_hours_are_used_for_the_actual_trip_day():
    response = ProviderResponse("google_maps", {"local_results": [{
        "title": "Museum", "gps_coordinates": {"latitude": 10.08, "longitude": 77.06},
        "operating_hours": {"monday": "Closed", "saturday": "9 AM–5 PM"},
        "price": "₹200–400", "open_state": "Closes soon · 5 PM"
    }]}, datetime.now(timezone.utc), False)
    place = parse_places(response, PlaceCategory.attraction)[0]
    assert place.opening_hours.for_day(date(2026, 10, 5))[2] is True
    opening, closing, closed = place.opening_hours.for_day(date(2026, 10, 10))
    assert (opening.hour, closing.hour, closed) == (9, 17, False)
    assert "google.com/maps" in place.sources[-1].url


def test_current_open_state_is_not_a_future_opening_schedule():
    response = ProviderResponse("google_maps", {"local_results": [{
        "title": "Cafe", "open_state": "Open · Closes 5 PM"
    }]}, datetime.now(timezone.utc), False)
    hours = parse_places(response, PlaceCategory.restaurant)[0].opening_hours
    assert hours is None or hours.for_day(date(2026, 10, 10))[:2] == (None, None)
