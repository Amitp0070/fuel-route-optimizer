
import csv
import io

import requests
from django.core.management.base import BaseCommand, CommandError

from fuel.models import FuelStation


CENSUS_BATCH_URL = (
    "https://geocoding.geo.census.gov/geocoder/"
    "locations/addressbatch"
)


class Command(BaseCommand):
    help = "Batch-geocode fuel station addresses using US Census"

    def handle(self, *args, **options):
        stations = list(
            FuelStation.objects.filter(
                latitude__isnull=True,
                longitude__isnull=True,
            ).order_by("id")
        )

        if not stations:
            self.stdout.write("No stations need geocoding.")
            return

        input_buffer = io.StringIO()
        writer = csv.writer(input_buffer, lineterminator="\n")

        for station in stations:
            # Census batch format:
            # ID, street address, city, state, ZIP
            writer.writerow([
                station.pk,
                station.address,
                station.city,
                station.state,
                "",
            ])

        try:
            response = requests.post(
                CENSUS_BATCH_URL,
                data={"benchmark": "Public_AR_Current"},
                files={
                    "addressFile": (
                        "fuel_stations.csv",
                        input_buffer.getvalue().encode("utf-8"),
                        "text/csv",
                    )
                },
                timeout=180,
            )
            response.raise_for_status()
            print("HTTP status:", response.status_code)
            print("Response length:", len(response.text))
            print("First 10 response lines:")
            print("\n".join(response.text.splitlines()[:10]))
        except requests.RequestException as exc:
            raise CommandError(
                f"Census geocoding request failed: {exc}"
            ) from exc

        updates = []
        matched = 0
        unmatched = 0

        reader = csv.reader(io.StringIO(response.text))

        for row in reader:
            if len(row) < 3:
                continue

            if row[2].strip() != "Match":
                unmatched += 1
                continue

            if len(row) < 6:
                unmatched += 1
                continue

            try:
                station_id = int(row[0])
            except ValueError:
                continue

            # Census result format includes match status and coordinates.
            if row[2].strip() != "Match":
                unmatched += 1
                continue

            coordinates = row[5].strip() if len(row) > 5 else ""

            if not coordinates:
                unmatched += 1
                continue

            try:
                longitude, latitude = map(
                    float, coordinates.split(",")
                )
            except (ValueError, TypeError):
                unmatched += 1
                continue

            station = next(
                (item for item in stations if item.pk == station_id),
                None,
            )

            if station is None:
                continue

            station.latitude = latitude
            station.longitude = longitude
            updates.append(station)
            matched += 1

        if updates:
            FuelStation.objects.bulk_update(
                updates,
                ["latitude", "longitude"],
                batch_size=500,
            )

        self.stdout.write(
            self.style.SUCCESS(
                f"Matched: {matched}; unmatched: {unmatched}; "
                f"remaining without coordinates: "
                f"{FuelStation.objects.filter(latitude__isnull=True).count()}"
            )
        )
