
import csv
from decimal import Decimal, InvalidOperation
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from fuel.models import FuelStation


US_STATES = {
    "AL", "AK", "AZ", "AR", "CA", "CO", "CT", "DE", "FL", "GA",
    "HI", "ID", "IL", "IN", "IA", "KS", "KY", "LA", "ME", "MD",
    "MA", "MI", "MN", "MS", "MO", "MT", "NE", "NV", "NH", "NJ",
    "NM", "NY", "NC", "ND", "OH", "OK", "OR", "PA", "RI", "SC",
    "SD", "TN", "TX", "UT", "VT", "VA", "WA", "WV", "WI", "WY",
    "DC",
}


class Command(BaseCommand):
    help = "Import US fuel stations from the assessment CSV"

    def add_arguments(self, parser):
        parser.add_argument(
            "--replace",
            action="store_true",
            help="Delete existing station records before importing",
        )

    def handle(self, *args, **options):
        csv_path = (
            Path(settings.BASE_DIR)
            / "data"
            / "fuel-prices-for-be-assessment.csv"
        )

        if not csv_path.is_file():
            raise CommandError(f"CSV file not found: {csv_path}")

        if options["replace"]:
            FuelStation.objects.all().delete()

        seen = set()
        batch = []
        imported = 0
        skipped = 0

        try:
            with csv_path.open(
                "r", encoding="utf-8-sig", newline=""
            ) as file:
                reader = csv.DictReader(file)

                required = {
                    "OPIS Truckstop ID",
                    "Truckstop Name",
                    "Address",
                    "City",
                    "State",
                    "Rack ID",
                    "Retail Price",
                }

                if not reader.fieldnames or not required.issubset(
                    set(reader.fieldnames)
                ):
                    raise CommandError(
                        f"Unexpected CSV headers: {reader.fieldnames}"
                    )

                for row in reader:
                    state = (row.get("State") or "").strip().upper()

                    if state not in US_STATES:
                        skipped += 1
                        continue

                    try:
                        price = Decimal(
                            row["Retail Price"].strip()
                        )
                        if not price.is_finite() or price <= 0:
                            raise InvalidOperation
                    except (InvalidOperation, AttributeError):
                        skipped += 1
                        continue

                    values = (
                        row["OPIS Truckstop ID"].strip(),
                        row["Truckstop Name"].strip(),
                        row["Address"].strip(),
                        row["City"].strip(),
                        state,
                        row["Rack ID"].strip(),
                        price,
                    )

                    if values in seen:
                        skipped += 1
                        continue

                    seen.add(values)

                    batch.append(
                        FuelStation(
                            opis_truckstop_id=values[0],
                            name=values[1],
                            address=values[2],
                            city=values[3],
                            state=values[4],
                            rack_id=values[5],
                            retail_price=values[6],
                        )
                    )

                    if len(batch) >= 1000:
                        FuelStation.objects.bulk_create(batch)
                        imported += len(batch)
                        batch.clear()

        except (OSError, KeyError, InvalidOperation) as exc:
            raise CommandError(f"CSV import failed: {exc}") from exc

        if batch:
            FuelStation.objects.bulk_create(batch)
            imported += len(batch)

        self.stdout.write(
            self.style.SUCCESS(
                f"Imported: {imported}, skipped: {skipped}"
            )
        )
