
import json
import requests

from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from .services import (
    geocode_location,
    get_driving_route,
    get_route_fuel_stations,
    optimize_fuel_stops,
)

import logging

logger = logging.getLogger(__name__)

def health_check(request):
    return JsonResponse({
        "status": "success",
        "message": "Fuel Route Optimizer API is running",
        "version": "1.0.0",
    })


@csrf_exempt
@require_POST
def route_api(request):
    try:
        body = json.loads(request.body or "{}")
    except (json.JSONDecodeError, UnicodeDecodeError):
        return JsonResponse({
            "status": "error",
            "message": "Invalid JSON body",
        }, status=400)

    start_location = body.get("start")
    finish_location = body.get("finish")

    if not isinstance(start_location, str) or not start_location.strip():
        return JsonResponse({
            "status": "error",
            "message": "'start' is required",
        }, status=400)

    if not isinstance(finish_location, str) or not finish_location.strip():
        return JsonResponse({
            "status": "error",
            "message": "'finish' is required",
        }, status=400)

    try:
        start = geocode_location(start_location.strip())
        finish = geocode_location(finish_location.strip())

        route = get_driving_route(start, finish)


        try:
            stations = get_route_fuel_stations(route["geometry"])
            station_lookup = {
                "status": "success",
                "count": len(stations),
            }
        except requests.RequestException:
            logger.exception("Fuel station lookup failed")
            stations = []
            station_lookup = {
                "status": "unavailable",
                "message": (
                    "Fuel station data is temporarily unavailable."
                ),
            }

        fuel_optimization = optimize_fuel_stops(route)

        return JsonResponse({
            "status": "success",
            "start": start,
            "finish": finish,
            "route": route,
            "nearby_stations_count": len(stations),
            "nearby_stations": stations,
            "fuel_optimization": fuel_optimization,
            "station_lookup": station_lookup,
        })

    except ValueError as exc:
        return JsonResponse({
            "status": "error",
            "message": str(exc),
        }, status=400)

    except requests.RequestException:
        logger.exception("External service request failed")
        return JsonResponse({
            "status": "error",
            "message": (
                "A geocoding, routing, or station lookup service failed."
            ),
        }, status=502)
