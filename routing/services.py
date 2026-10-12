
import requests
import math


from fuel.models import FuelStation


VEHICLE_RANGE_MILES = 500.0
FUEL_EFFICIENCY_MPG = 10.0
MAX_STATION_DISTANCE_MILES = 5.0

GEOCODING_URL = "https://nominatim.openstreetmap.org/search"


def geocode_location(location: str) -> dict:
    response = requests.get(
        GEOCODING_URL,
        params={
            "q": f"{location}, USA",
            "format": "jsonv2",
            "limit": 1,
            "countrycodes": "us",
        },
        headers={
            "User-Agent": "FuelRouteOptimizer/1.0 (assessment project)"
        },
        timeout=10,
    )
    response.raise_for_status()
    results = response.json()

    if not results:
        raise ValueError(f"Location not found in USA: {location}")

    return {
        "latitude": float(results[0]["lat"]),
        "longitude": float(results[0]["lon"]),
        "display_name": results[0]["display_name"],
    }



def get_driving_route(start: dict, finish: dict) -> dict:
    url = (
        "https://router.project-osrm.org/route/v1/driving/"
        f"{start['longitude']},{start['latitude']};"
        f"{finish['longitude']},{finish['latitude']}"
    )

    response = requests.get(
        url,
        params={
            "overview": "simplified",
            "geometries": "geojson",
            "steps": "false",
        },
        timeout=20,
    )
    response.raise_for_status()
    data = response.json()

    if data.get("code") != "Ok" or not data.get("routes"):
        raise ValueError("No driving route found.")

    route = data["routes"][0]

    return {
        "distance_miles": round(route["distance"] / 1609.344, 2),
        "duration_minutes": round(route["duration"] / 60, 2),
        "geometry": route["geometry"],
    }



OVERPASS_URL = "https://overpass-api.de/api/interpreter"


def sample_route_points(geometry: dict, interval_miles: float = 10):
    """Sample route geometry approximately every 10 miles."""
    coordinates = geometry["coordinates"]

    if len(coordinates) < 2:
        return coordinates

    points = [coordinates[0]]
    distance_since_sample = 0.0

    for first, second in zip(coordinates, coordinates[1:]):
        lon1, lat1 = first
        lon2, lat2 = second

        # Approximate segment distance using haversine.
        radius_miles = 3958.8
        phi1, phi2 = math.radians(lat1), math.radians(lat2)
        dphi = math.radians(lat2 - lat1)
        dlambda = math.radians(lon2 - lon1)

        a = (
            math.sin(dphi / 2) ** 2
            + math.cos(phi1)
            * math.cos(phi2)
            * math.sin(dlambda / 2) ** 2
        )
        segment_distance = 2 * radius_miles * math.asin(
            min(1.0, math.sqrt(a))
        )

        distance_since_sample += segment_distance

        if distance_since_sample >= interval_miles:
            points.append(second)
            distance_since_sample = 0.0

    if points[-1] != coordinates[-1]:
        points.append(coordinates[-1])

    return points



def get_route_fuel_stations(
    geometry: dict,
    radius_meters: int = 5000,
) -> list:
    """
    Retrieve fuel stations from the local database.
    Avoid external Overpass requests and their timeouts.
    """
    max_distance_miles = radius_meters / 1609.344

    candidates = route_station_candidates(
        geometry,
        max_distance=max_distance_miles,
    )

    stations = []

    for item in candidates:
        station = item["station"]

        stations.append({
            "source": "local_csv",
            "station_id": station.pk,
            "name": station.name,
            "brand": station.name,
            "latitude": station.latitude,
            "longitude": station.longitude,
            "city": station.city,
            "state": station.state,
            "retail_price": float(station.retail_price),
            "distance_from_route_miles": item[
                "distance_from_route_miles"
            ],
            "route_position_miles": item["route_position_miles"],
        })

    stations.sort(
        key=lambda item: item["route_position_miles"]
    )

    return stations


def haversine_miles(lon1, lat1, lon2, lat2):
    """Calculate straight-line distance between two coordinates."""
    radius = 3958.8

    lat1, lat2 = math.radians(lat1), math.radians(lat2)
    delta_lat = math.radians(lat2 - lat1)
    delta_lon = math.radians(lon2 - lon1)

    a = (
        math.sin(delta_lat / 2) ** 2
        + math.cos(lat1)
        * math.cos(lat2)
        * math.sin(delta_lon / 2) ** 2
    )

    return 2 * radius * math.asin(min(1, math.sqrt(a)))


def project_station_onto_route(station, geometry):
    """
    Find a station's approximate nearest position on the route.
    Returns cross-track distance and distance along the route.
    """
    coordinates = geometry.get("coordinates", [])

    if len(coordinates) < 2:
        return float("inf"), None

    station_lat = station.latitude
    station_lon = station.longitude
    cumulative_miles = 0.0
    best_distance = float("inf")
    best_route_position = None

    for first, second in zip(coordinates, coordinates[1:]):
        lon1, lat1 = first
        lon2, lat2 = second

        segment_miles = haversine_miles(
            lon1, lat1, lon2, lat2
        )

        if segment_miles == 0:
            continue

        # Local coordinate approximation for projecting onto a segment.
        reference_lat = math.radians(
            (lat1 + lat2 + station_lat) / 3
        )
        x_scale = math.cos(reference_lat)

        ax, ay = lon1 * x_scale, lat1
        bx, by = lon2 * x_scale, lat2
        px, py = station_lon * x_scale, station_lat

        dx, dy = bx - ax, by - ay
        denominator = dx * dx + dy * dy

        t = 0.0 if denominator == 0 else (
            ((px - ax) * dx + (py - ay) * dy)
            / denominator
        )
        t = max(0.0, min(1.0, t))

        projected_lon = lon1 + t * (lon2 - lon1)
        projected_lat = lat1 + t * (lat2 - lat1)

        distance = haversine_miles(
            station_lon,
            station_lat,
            projected_lon,
            projected_lat,
        )

        if distance < best_distance:
            best_distance = distance
            best_route_position = (
                cumulative_miles + segment_miles * t
            )

        cumulative_miles += segment_miles

    return best_distance, best_route_position


def distance_to_route_miles(station, geometry):
    distance, _ = project_station_onto_route(
        station, geometry
    )
    return distance


def route_station_candidates(
    geometry,
    max_distance=MAX_STATION_DISTANCE_MILES,
):
    coordinates = geometry.get("coordinates", [])
    if len(coordinates) < 2:
        return []

    min_lon = min(p[0] for p in coordinates)
    max_lon = max(p[0] for p in coordinates)
    min_lat = min(p[1] for p in coordinates)
    max_lat = max(p[1] for p in coordinates)

    lat_margin = max_distance / 69.0
    mid_lat = (min_lat + max_lat) / 2
    lon_margin = max_distance / max(
        1.0, 69.0 * math.cos(math.radians(mid_lat))
    )

    stations = FuelStation.objects.filter(
        latitude__isnull=False,
        longitude__isnull=False,
        latitude__gte=min_lat - lat_margin,
        latitude__lte=max_lat + lat_margin,
        longitude__gte=min_lon - lon_margin,
        longitude__lte=max_lon + lon_margin,
    )

    results = []

    for station in stations:
        distance, route_position = project_station_onto_route(
            station, geometry
        )

        if distance <= max_distance and route_position is not None:
            results.append({
                "station": station,
                "distance_from_route_miles": round(distance, 2),
                "route_position_miles": round(route_position, 2),
            })

    return results



def optimize_fuel_stops(route):
    """
    Select a minimum-cost feasible sequence of fuel stops.

    Assumptions:
    - Vehicle starts with a full 500-mile range.
    - Fuel efficiency is 10 MPG.
    - Candidate stations are within 5 miles of the route.
    - The vehicle refills enough to restore its full range at each stop.
    - Initial fuel cost is excluded because its purchase price is unknown.
    """
    distance = float(route["distance_miles"])
    mpg = float(FUEL_EFFICIENCY_MPG)
    max_range = float(VEHICLE_RANGE_MILES)

    if distance < 0 or mpg <= 0 or max_range <= 0:
        return {
            "status": "invalid_route_or_vehicle_configuration",
            "message": "Distance must be non-negative and MPG/range must be positive.",
        }

    required_gallons = distance / mpg

    assumptions = {
        "starting_range_miles": max_range,
        "fuel_efficiency_mpg": mpg,
        "starts_with_full_range": True,
        "max_station_distance_from_route_miles": 5.0,
        "initial_fuel_cost_included": False,
    }

    if distance <= max_range:
        return {
            "status": "success",
            "assumptions": assumptions,
            "route_distance_miles": round(distance, 2),
            "estimated_fuel_required_gallons": round(required_gallons, 2),
            "fuel_stops_required": 0,
            "selected_stops": [],
            "estimated_refueling_cost_usd": 0.0,
            "estimated_fuel_cost_usd": None,
            "cost_note": (
                "No intermediate refueling is required. "
                "Total trip fuel cost is unknown because the initial "
                "fuel purchase price is not provided."
            ),
        }

    candidates = route_station_candidates(
        route["geometry"],
        max_distance=5.0,
    )

    # Keep only stations positioned along the route.
    stations = []

    for item in candidates:
        station = item["station"]
        position = item.get("route_position_miles")

        if position is None:
            continue

        position = float(position)
        price = float(station.retail_price)

        if (
            0 < position < distance
            and price > 0
            and station.latitude is not None
            and station.longitude is not None
        ):
            stations.append({
                "station": station,
                "position": position,
                "price": price,
                "distance_from_route_miles": float(
                    item["distance_from_route_miles"]
                ),
            })

    stations.sort(key=lambda item: item["position"])

    if not stations:
        return {
            "status": "insufficient_station_data",
            "assumptions": assumptions,
            "route_distance_miles": round(distance, 2),
            "estimated_fuel_required_gallons": round(required_gallons, 2),
            "fuel_stops_required": None,
            "selected_stops": [],
            "estimated_refueling_cost_usd": None,
            "estimated_fuel_cost_usd": None,
            "message": "No usable fuel stations were found along the route.",
        }

    # Dynamic programming:
    # dp[i] = minimum estimated refueling cost to reach station i.
    # The starting tank is full, so reaching the first station costs
    # fuel purchase for the distance from the origin to that station.
    count = len(stations)
    dp = [float("inf")] * count
    previous = [None] * count

    for i, current in enumerate(stations):
        position = current["position"]

        # Reach this station directly from the starting full tank.
        if position <= max_range:
            dp[i] = (position / mpg) * current["price"]

        # Or reach it after refueling at an earlier station.
        for j in range(i):
            earlier_position = stations[j]["position"]
            gap = position - earlier_position

            if gap <= 0 or gap > max_range:
                continue

            if dp[j] == float("inf"):
                continue

            cost = dp[j] + (gap / mpg) * current["price"]

            if cost < dp[i]:
                dp[i] = cost
                previous[i] = j

    # The destination must be reachable from the final selected station.
    feasible_last_stations = [
        i
        for i, item in enumerate(stations)
        if distance - item["position"] <= max_range
        and dp[i] < float("inf")
    ]

    if not feasible_last_stations:
        return {
            "status": "insufficient_station_data",
            "assumptions": assumptions,
            "route_distance_miles": round(distance, 2),
            "estimated_fuel_required_gallons": round(required_gallons, 2),
            "fuel_stops_required": None,
            "selected_stops": [],
            "estimated_refueling_cost_usd": None,
            "estimated_fuel_cost_usd": None,
            "candidate_station_count": count,
            "message": (
                "The available station candidates do not establish "
                "a feasible route within the vehicle's range. "
                "More station coverage is needed."
            ),
        }

    # Choose the lowest-cost feasible sequence.
    last_index = min(
        feasible_last_stations,
        key=lambda i: dp[i],
    )

    selected_indices = []
    index = last_index

    while index is not None:
        selected_indices.append(index)
        index = previous[index]

    selected_indices.reverse()

    selected_stops = []
    previous_position = 0.0
    total_refueling_gallons = 0.0

    for index in selected_indices:
        item = stations[index]
        station = item["station"]

        # Amount needed to refill fuel consumed since the previous stop.
        leg_distance = item["position"] - previous_position
        gallons_purchased = leg_distance / mpg
        purchase_cost = gallons_purchased * item["price"]

        total_refueling_gallons += gallons_purchased

        selected_stops.append({
            "station_id": station.pk,
            "name": station.name,
            "city": station.city,
            "state": station.state,
            "route_position_miles": round(item["position"], 2),
            "distance_from_route_miles": round(
                item["distance_from_route_miles"], 2
            ),
            "retail_price_usd_per_gallon": round(item["price"], 3),
            "estimated_gallons_purchased": round(gallons_purchased, 2),
            "estimated_purchase_cost_usd": round(purchase_cost, 2),
            "leg_distance_since_previous_stop_miles": round(
                leg_distance, 2
            ),
        })

        previous_position = item["position"]

    return {
        "status": "success",
        "assumptions": assumptions,
        "route_distance_miles": round(distance, 2),
        "estimated_fuel_required_gallons": round(required_gallons, 2),
        "fuel_stops_required": len(selected_stops),
        "selected_stops": selected_stops,
        "estimated_refueling_gallons": round(
            total_refueling_gallons, 2
        ),
        "estimated_refueling_cost_usd": round(dp[last_index], 2),
        "estimated_fuel_cost_usd": None,
        "cost_note": (
            "Estimated cost of fuel purchased at selected intermediate "
            "stops. Initial fuel cost is excluded; total trip fuel cost "
            "cannot be calculated without its purchase price."
        ),
        "candidate_station_count": count,
    }
