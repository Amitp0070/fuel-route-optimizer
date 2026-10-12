from django.db import models


class FuelStation(models.Model):
    opis_truckstop_id = models.CharField(max_length=50, db_index=True)
    name = models.CharField(max_length=255)
    address = models.CharField(max_length=500)
    city = models.CharField(max_length=100, db_index=True)
    state = models.CharField(max_length=2, db_index=True)
    rack_id = models.CharField(max_length=50, blank=True)
    retail_price = models.DecimalField(max_digits=10, decimal_places=6)
    latitude = models.FloatField(null=True, blank=True)
    longitude = models.FloatField(null=True, blank=True)
    class Meta:
        indexes = [
            models.Index(
                fields=["state", "city"],
                name="fuel_state_city_idx",
            ),
            models.Index(
                fields=["retail_price"],
                name="fuel_price_idx",
            ),
        ]

    def __str__(self):
        return f"{self.name}, {self.city}, {self.state}"
