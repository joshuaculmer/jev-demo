from dataclasses import dataclass

ABSOLUTE_ZERO_C = -273.15


@dataclass(frozen=True)
class Reading:
    sensor_id: str
    celsius: float


def celsius_to_fahrenheit(celsius: float) -> float:
    return celsius * 9 / 5 + 32


def validate(reading: Reading) -> None:
    if reading.celsius < ABSOLUTE_ZERO_C:
        raise ValueError(f"{reading.sensor_id}: {reading.celsius} is below absolute zero")


def average_celsius(readings: list[Reading]) -> float:
    if not readings:
        raise ValueError("no readings to average")

    for reading in readings:
        validate(reading)

    return sum(r.celsius for r in readings) / len(readings)
