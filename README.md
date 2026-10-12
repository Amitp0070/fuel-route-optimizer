# Fuel Route Optimizer

A Django REST API that calculates driving routes between US locations, finds nearby fuel stations from a local fuel-price dataset, and estimates fuel requirements and intermediate refueling costs.

## Features

- Geocodes US start and destination locations using OpenStreetMap Nominatim.
- Calculates driving routes using OSRM.
- Returns route distance, duration, and GeoJSON geometry.
- Finds nearby fuel stations from locally stored CSV-derived records.
- Estimates fuel consumption using configurable vehicle assumptions.
- Selects candidate refueling stops subject to the vehicle's range.
- Handles temporary external station-service failures gracefully.
- Includes automated Django tests.

## Technology Stack

- Python
- Django
- Django REST API
- SQLite
- OpenStreetMap Nominatim
- OSRM
- CSV fuel-price dataset

## Prerequisites

- Python 3.12 or a compatible Python version
- pip
- Internet access for geocoding and routing services

## Installation

Clone the repository and enter the project directory:

```bash
git clone YOUR_GITHUB_REPOSITORY_URL
cd fuel-route-optimizer
```

Create and activate a virtual environment.

Windows PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

Install project dependencies:

```powershell
pip install -r requirements.txt
```

Apply database migrations:

```powershell
python manage.py migrate
```

If the project requires importing the fuel-price CSV, follow the data-import instructions provided with the repository.

## Run the Application

```powershell
python manage.py runserver
```

The development server runs at `http://127.0.0.1:8000/`.

## API Endpoints

### Health Check

`GET /api/health/`

Checks whether the API is running.

### Calculate a Route

`POST /api/route/`

Request headers:

`Content-Type: application/json`

Example request:

```json
{
  "start": "Dallas, Texas",
  "finish": "Atlanta, Georgia"
}
```

The response includes:

- Start and destination coordinates
- Driving distance and duration
- Route geometry
- Nearby fuel-station candidates
- Fuel consumption estimate
- Selected intermediate stops, when a feasible solution can be established
- Estimated refueling cost and optimization status

## Vehicle Assumptions

The current optimizer uses these assumptions:

- Starting fuel range: 500 miles
- Fuel efficiency: 10 miles per gallon
- Starting tank is full
- Fuel stations are considered within approximately 5 miles of the route

These values and the station-search radius should be documented and configured consistently with the implementation.

## Fuel Cost Interpretation

`estimated_fuel_required_gallons` represents estimated fuel consumed over the complete trip.

`estimated_refueling_cost_usd` represents the estimated cost of fuel purchased at selected intermediate stops. It does not include the cost of fuel already in the starting tank.

Total trip fuel cost cannot be calculated accurately without an assumption or value for the starting fuel's purchase price.

## Run Tests

```powershell
python manage.py test routing
```

Run Django's system check:

```powershell
python manage.py check
```

## Known Limitations

- Fuel-station coverage depends on the availability of geocoded dataset records.
- Nearby station coordinates do not establish exact driving detours to station entrances.
- External geocoding and routing services may be temporarily unavailable.
- Fuel prices reflect the supplied dataset and may not represent current prices.
- Optimization correctness depends on station coverage, route-position estimates, range assumptions, and the implemented cost model.

## Project Status

The API routing flow and basic automated tests have been validated. Further verification of the minimum-cost optimization model, station coverage, and submission documentation is required before claiming a globally optimal solution.
