# Fuel Route Optimizer

A Django REST API that calculates driving routes between US locations, identifies nearby fuel stations from a local fuel-price dataset, and estimates fuel consumption and intermediate refueling costs.

## Features

- Geocodes start and destination locations using OpenStreetMap Nominatim.
- Calculates driving routes using OSRM.
- Returns route distance, duration, and route geometry.
- Imports fuel-station records from the supplied CSV dataset into a local database.
- Finds fuel-station candidates near the route.
- Estimates fuel requirements using configurable vehicle assumptions.
- Selects feasible intermediate refueling stops based on vehicle range and station prices.
- Handles temporary station-service failures gracefully.
- Includes automated tests for fuel optimization and API behavior.

## Technology Stack

- Python
- Django
- Django REST Framework
- SQLite
- OpenStreetMap Nominatim
- OSRM
- CSV fuel-price dataset
- Requests

## Prerequisites

- Python 3.12 or a compatible version
- pip
- Internet access for geocoding and routing

## Installation and Setup

### 1. Clone the repository

```bash
git clone https://github.com/Amitp0070/fuel-route-optimizer.git
cd fuel-route-optimizer
```

### 2. Create and activate a virtual environment

Windows PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

### 3. Install dependencies

```powershell
python -m pip install -r requirements.txt
```

### 4. Apply database migrations

```powershell
python manage.py migrate
```

### 5. Import fuel-station data

Import the supplied CSV dataset into the local database:

```powershell
python manage.py import_fuel_stations
```

To replace existing station records before importing:

```powershell
python manage.py import_fuel_stations --replace
```

Use `--replace` only when you intend to delete the existing station records and reimport the dataset.

### 6. Start the development server

```powershell
python manage.py runserver
```

The local API will be available at `http://127.0.0.1:8000/`.

## API Endpoints

### Health Check

`GET /api/health/`

Checks whether the API is running.

Example:

```powershell
Invoke-RestMethod -Uri "http://127.0.0.1:8000/api/health/" -Method Get
```

### Calculate a Route

`POST /api/route/`

Request header:

`Content-Type: application/json`

Example request body:

```json
{
  "start": "Dallas, Texas",
  "finish": "Atlanta, Georgia"
}
```

PowerShell example:

```powershell
$body = @{
    start = "Dallas, Texas"
    finish = "Atlanta, Georgia"
} | ConvertTo-Json

Invoke-RestMethod `
    -Uri "http://127.0.0.1:8000/api/route/" `
    -Method Post `
    -ContentType "application/json" `
    -Body $body
```

The response provides route information, nearby fuel-station candidates, estimated fuel consumption, selected refueling stops when a feasible solution is found, and optimization status.

## Fuel Optimization Assumptions

The current implementation uses these assumptions:

| Parameter | Value |
|---|---:|
| Vehicle range with a full tank | 500 miles |
| Fuel efficiency | 10 miles per gallon |
| Fuel-station search radius | Approximately 5 miles from the route |

The optimizer assumes the vehicle starts with a full tank and refills to full range at selected intermediate stops. It evaluates feasible station sequences using estimated fuel costs.

The result depends on available station records, station prices, estimated positions along the route, and the assumptions above. Nearby coordinates do not guarantee that a station entrance can be reached with a particular driving detour.

## Fuel Cost Interpretation

- `estimated_fuel_required_gallons` estimates fuel consumed over the full trip.
- `estimated_refueling_cost_usd` estimates fuel purchases at selected intermediate stops.
- The estimated refueling cost excludes fuel already in the starting tank because its purchase price is unknown.
- The intermediate refueling cost is not the same as the total cost of all fuel consumed during the trip.

## Running Tests

Run the routing and fuel application tests:

```powershell
python manage.py test routing fuel
```

Run Django's system check:

```powershell
python manage.py check
```

## Known Limitations

- Fuel-station coverage depends on the supplied dataset and the number of records with usable coordinates.
- Station positions along the route are estimates and do not calculate exact driving detours to station entrances.
- Fuel prices in the supplied dataset may not reflect current prices.
- Geocoding and routing depend on external services and can fail temporarily.
- The optimizer's result depends on the full-tank refueling assumption and the available candidate stations.
- The initial tank's fuel cost is excluded from the intermediate refueling cost estimate.

## Project Structure

```text
config/       Django project configuration
fuel/         Fuel-station models, import command, and tests
routing/      Route API, routing services, and optimization tests
data/         Supplied fuel-price CSV dataset
manage.py     Django management entry point
requirements.txt
README.md
```

## License and Dataset

This project was created as a coding assessment. The supplied fuel-price dataset is included for the assessment workflow. Refer to the dataset's original terms and the assessment instructions for applicable usage restrictions.
