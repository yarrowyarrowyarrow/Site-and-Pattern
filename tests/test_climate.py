"""Basic tests for climate zone lookup."""
from src.climate import get_hardiness_zone, centroid


def test_edmonton():
    zone = get_hardiness_zone(53.5461, -113.4938)
    assert zone == 3, f"Edmonton should be zone 3, got {zone}"


def test_calgary():
    zone = get_hardiness_zone(51.0447, -114.0719)
    assert zone == 4, f"Calgary should be zone 4, got {zone}"


def test_far_north():
    zone = get_hardiness_zone(60.0, -120.0)
    assert zone <= 1, f"Far north should be zone 0-1, got {zone}"


def test_centroid():
    coords = [[-113.5, 53.5], [-113.4, 53.5], [-113.4, 53.6], [-113.5, 53.6]]
    lat, lng = centroid(coords)
    assert abs(lat - 53.55) < 0.01
    assert abs(lng - (-113.45)) < 0.01


if __name__ == "__main__":
    test_edmonton()
    test_calgary()
    test_far_north()
    test_centroid()
    print("All tests passed!")
