import math
import random


def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    Calculate the great-circle distance between two points on Earth (in meters).
    Uses the Haversine formula.
    """
    R = 6_371_000  # Earth radius in meters
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)

    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    return R * c


def simulate_gps(hospital_lat: float, hospital_lng: float) -> tuple[float, float]:
    """
    Simulate GPS coordinate collection with realistic distribution:
    - 60%: within 100m of hospital (indoor/on-premise)
    - 30%: 100m-500m from hospital (nearby)
    - 10%: >500m from hospital (anomalous)

    Returns (latitude, longitude) tuple.
    """
    roll = random.random()

    if roll < 0.60:
        radius = random.uniform(0, 100)
    elif roll < 0.90:
        radius = random.uniform(100, 500)
    else:
        radius = random.uniform(500, 3000)

    # Convert radius (meters) to degrees offset, then apply random bearing
    bearing = random.uniform(0, 2 * math.pi)
    # 1 degree lat ≈ 111,111 m; 1 degree lng ≈ 111,111 * cos(lat) m
    delta_lat = (radius * math.cos(bearing)) / 111_111
    delta_lng = (radius * math.sin(bearing)) / (111_111 * math.cos(math.radians(hospital_lat)))

    return (
        round(hospital_lat + delta_lat, 7),
        round(hospital_lng + delta_lng, 7),
    )
