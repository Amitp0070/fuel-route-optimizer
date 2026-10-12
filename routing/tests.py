
from unittest.mock import patch

from django.test import SimpleTestCase

from routing.services import optimize_fuel_stops

from types import SimpleNamespace
from unittest.mock import patch
from django.test import SimpleTestCase
import json
from unittest.mock import patch

from django.test import TestCase
from django.urls import reverse


class FuelOptimizerTests(SimpleTestCase):



    @patch("routing.services.route_station_candidates")
    def test_total_cost_matches_dp_and_selected_stops(self, mock_candidates):
        def candidate(position, price, name):
            return {
                "station": SimpleNamespace(
                    pk=int(position),
                    name=name,
                    city="Test City",
                    state="TX",
                    retail_price=price,
                    latitude=32.0,
                    longitude=-96.0,
                ),
                "route_position_miles": position,
                "distance_from_route_miles": 0.5,
            }

        mock_candidates.return_value = [
            candidate(200.0, 3.00, "Station A"),
            candidate(400.0, 4.00, "Station B"),
        ]

        route = {
            "distance_miles": 650.0,
            "geometry": {"type": "LineString", "coordinates": []},
        }

        result = optimize_fuel_stops(route)

        self.assertEqual(result["status"], "success")

        reported_cost = sum(
            stop["estimated_purchase_cost_usd"]
            for stop in result["selected_stops"]
        )

        self.assertAlmostEqual(
            result["estimated_refueling_cost_usd"],
            reported_cost,
            places=2,
        )

        previous_position = 0.0
        for stop in result["selected_stops"]:
            position = stop["route_position_miles"]
            self.assertLessEqual(position - previous_position, 500.0)
            self.assertGreaterEqual(stop["estimated_gallons_purchased"], 0)
            previous_position = position

        self.assertLessEqual(650.0 - previous_position, 500.0)


    @patch("routing.services.route_station_candidates")
    def test_long_route_selects_reachable_stops(self, mock_candidates):
        def candidate(position, price, name):
            return {
                "station": SimpleNamespace(
                    pk=int(position),
                    name=name,
                    city="Test City",
                    state="TX",
                    retail_price=price,
                    latitude=32.0,
                    longitude=-96.0,
                ),
                "route_position_miles": position,
                "distance_from_route_miles": 0.5,
            }

        mock_candidates.return_value = [
            candidate(200.0, 3.50, "Station A"),
            candidate(400.0, 3.00, "Station B"),
            candidate(600.0, 3.25, "Station C"),
        ]

        route = {
            "distance_miles": 750.0,
            "geometry": {"type": "LineString", "coordinates": []},
        }

        result = optimize_fuel_stops(route)

        self.assertEqual(result["status"], "success")
        self.assertGreater(result["fuel_stops_required"], 0)

        positions = [
            stop["route_position_miles"]
            for stop in result["selected_stops"]
        ]
        self.assertEqual(positions, sorted(positions))

        previous_position = 0.0
        for position in positions:
            self.assertLessEqual(position - previous_position, 500.0)
            previous_position = position

        self.assertLessEqual(750.0 - previous_position, 500.0)

    @patch("routing.services.route_station_candidates")
    def test_refueling_cost_matches_selected_purchases(self, mock_candidates):
        def candidate(position, price, name):
            return {
                "station": SimpleNamespace(
                    pk=int(position),
                    name=name,
                    city="Test City",
                    state="TX",
                    retail_price=price,
                    latitude=32.0,
                    longitude=-96.0,
                ),
                "route_position_miles": position,
                "distance_from_route_miles": 0.5,
            }

        mock_candidates.return_value = [
            candidate(200.0, 3.00, "Station A"),
            candidate(400.0, 4.00, "Station B"),
        ]

        route = {
            "distance_miles": 650.0,
            "geometry": {"type": "LineString", "coordinates": []},
        }

        result = optimize_fuel_stops(route)

        self.assertEqual(result["status"], "success")

        expected_cost = sum(
            stop["estimated_purchase_cost_usd"]
            for stop in result["selected_stops"]
        )
        self.assertAlmostEqual(
            result["estimated_refueling_cost_usd"],
            expected_cost,
            places=2,
        )



    @patch("routing.services.route_station_candidates")
    def test_optimizer_chooses_cheapest_feasible_sequence(
        self, mock_candidates
    ):
        def candidate(position, price, name):
            return {
                "station": SimpleNamespace(
                    pk=int(position),
                    name=name,
                    city="Test City",
                    state="TX",
                    retail_price=price,
                    latitude=32.0,
                    longitude=-96.0,
                ),
                "route_position_miles": position,
                "distance_from_route_miles": 0.5,
            }

        mock_candidates.return_value = [
            candidate(200.0, 4.00, "Expensive Station"),
            candidate(300.0, 2.00, "Cheap Station"),
            candidate(600.0, 3.00, "Later Station"),
        ]

        route = {
            "distance_miles": 750.0,
            "geometry": {"type": "LineString", "coordinates": []},
        }

        result = optimize_fuel_stops(route)

        self.assertEqual(result["status"], "success")

        selected_names = [
            stop["name"] for stop in result["selected_stops"]
        ]

        self.assertIn("Cheap Station", selected_names)

        positions = [
            stop["route_position_miles"]
            for stop in result["selected_stops"]
        ]
        self.assertEqual(positions, sorted(positions))


    @patch("routing.services.route_station_candidates")
    def test_short_route_needs_no_stops(self, mock_candidates):
        route = {
            "distance_miles": 238.41,
            "geometry": {"type": "LineString", "coordinates": []},
        }

        result = optimize_fuel_stops(route)

        self.assertEqual(result["status"], "success")
        self.assertEqual(result["fuel_stops_required"], 0)
        self.assertAlmostEqual(
            result["estimated_fuel_required_gallons"], 23.84, places=2
        )
        mock_candidates.assert_not_called()

    @patch("routing.services.route_station_candidates")
    def test_long_route_without_stations_is_unavailable(
        self, mock_candidates
    ):
        mock_candidates.return_value = []

        route = {
            "distance_miles": 782.91,
            "geometry": {"type": "LineString", "coordinates": []},
        }

        result = optimize_fuel_stops(route)

        self.assertEqual(result["status"], "insufficient_station_data")
        self.assertIsNone(result["fuel_stops_required"])
        self.assertIsNone(result["estimated_refueling_cost_usd"])

    def test_invalid_mpg_returns_error(self):
        route = {
            "distance_miles": 782.91,
            "geometry": {"type": "LineString", "coordinates": []},
        }

        with patch("routing.services.FUEL_EFFICIENCY_MPG", 0):
            result = optimize_fuel_stops(route)

        self.assertEqual(
            result["status"],
            "invalid_route_or_vehicle_configuration",
        )

    def test_negative_route_distance_returns_error(self):
        route = {
            "distance_miles": -10,
            "geometry": {"type": "LineString", "coordinates": []},
        }

        result = optimize_fuel_stops(route)

        self.assertEqual(
            result["status"],
            "invalid_route_or_vehicle_configuration",
        )



class RouteAPITests(TestCase):

    def test_missing_start_returns_400(self):
        response = self.client.post(
            "/api/route/",
            data=json.dumps({"finish": "Houston, Texas"}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["status"], "error")
        self.assertEqual(response.json()["message"], "'start' is required")

    def test_missing_finish_returns_400(self):
        response = self.client.post(
            "/api/route/",
            data=json.dumps({"start": "Dallas, Texas"}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            response.json()["message"],
            "'finish' is required",
        )

    def test_invalid_json_returns_400(self):
        response = self.client.post(
            "/api/route/",
            data="{invalid-json",
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["message"], "Invalid JSON body")

    @patch("routing.views.optimize_fuel_stops")
    @patch("routing.views.get_route_fuel_stations")
    @patch("routing.views.get_driving_route")
    @patch("routing.views.geocode_location")
    def test_valid_route_returns_success(
        self,
        mock_geocode,
        mock_route,
        mock_stations,
        mock_optimizer,
    ):
        mock_geocode.side_effect = [
            {
                "latitude": 32.77,
                "longitude": -96.79,
                "display_name": "Dallas, Texas",
            },
            {
                "latitude": 29.75,
                "longitude": -95.36,
                "display_name": "Houston, Texas",
            },
        ]

        mock_route.return_value = {
            "distance_miles": 238.41,
            "duration_minutes": 253.47,
            "geometry": {
                "type": "LineString",
                "coordinates": [[-96.79, 32.77], [-95.36, 29.75]],
            },
        }

        mock_stations.return_value = [
            {
                "name": "Test Fuel Station",
                "retail_price": 3.25,
            }
        ]

        mock_optimizer.return_value = {
            "status": "success",
            "fuel_stops_required": 0,
        }

        response = self.client.post(
            "/api/route/",
            data=json.dumps({
                "start": "Dallas, Texas",
                "finish": "Houston, Texas",
            }),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)

        data = response.json()
        self.assertEqual(data["status"], "success")
        self.assertEqual(data["route"]["distance_miles"], 238.41)
        self.assertEqual(data["nearby_stations_count"], 1)
        self.assertEqual(data["station_lookup"]["status"], "success")
        self.assertEqual(data["fuel_optimization"]["fuel_stops_required"], 0)

    @patch("routing.views.optimize_fuel_stops")
    @patch("routing.views.get_route_fuel_stations")
    @patch("routing.views.get_driving_route")
    @patch("routing.views.geocode_location")
    def test_station_lookup_failure_does_not_fail_route(
        self,
        mock_geocode,
        mock_route,
        mock_stations,
        mock_optimizer,
    ):
        import requests

        mock_geocode.side_effect = [
            {"latitude": 32.77, "longitude": -96.79},
            {"latitude": 29.75, "longitude": -95.36},
        ]

        mock_route.return_value = {
            "distance_miles": 238.41,
            "duration_minutes": 253.47,
            "geometry": {
                "type": "LineString",
                "coordinates": [[-96.79, 32.77], [-95.36, 29.75]],
            },
        }

        mock_stations.side_effect = requests.Timeout("Overpass timeout")
        mock_optimizer.return_value = {
            "status": "success",
            "fuel_stops_required": 0,
        }

        response = self.client.post(
            "/api/route/",
            data=json.dumps({
                "start": "Dallas, Texas",
                "finish": "Houston, Texas",
            }),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)

        data = response.json()
        self.assertEqual(data["status"], "success")
        self.assertEqual(data["station_lookup"]["status"], "unavailable")
        self.assertEqual(data["nearby_stations_count"], 0)
