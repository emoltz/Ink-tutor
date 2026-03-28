"""Tests for pen_host.parse_dot()."""
import struct

import pen_host


def _make_packet(x: int, y: int, pressure: int) -> bytearray:
    """Build a minimal 12-byte Neo dot packet."""
    data = bytearray(12)
    struct.pack_into(">I", data, 0, x)       # bytes 0-3
    struct.pack_into(">I", data, 4, y)       # bytes 4-7
    struct.pack_into(">H", data, 8, pressure) # bytes 8-9
    # bytes 10-11 unused (not read by parse_dot)
    return data


class TestParseDot:
    def test_valid_packet_returns_dict(self):
        result = pen_host.parse_dot(_make_packet(500, 300, 1024))
        assert result is not None
        assert isinstance(result, dict)

    def test_x_y_pressure_decoded_correctly(self):
        result = pen_host.parse_dot(_make_packet(1234, 5678, 999))
        assert result["x"] == 1234
        assert result["y"] == 5678
        assert result["pressure"] == 999

    def test_type_is_always_dot(self):
        result = pen_host.parse_dot(_make_packet(0, 0, 0))
        assert result["type"] == "dot"

    def test_ts_is_a_float(self):
        result = pen_host.parse_dot(_make_packet(10, 20, 30))
        assert isinstance(result["ts"], float)

    def test_short_packet_returns_none(self):
        assert pen_host.parse_dot(bytearray(11)) is None

    def test_empty_packet_returns_none(self):
        assert pen_host.parse_dot(bytearray()) is None

    def test_exactly_12_bytes_is_valid(self):
        assert pen_host.parse_dot(bytearray(12)) is not None

    def test_longer_packet_is_valid(self):
        assert pen_host.parse_dot(bytearray(20)) is not None

    def test_zero_values(self):
        result = pen_host.parse_dot(_make_packet(0, 0, 0))
        assert result["x"] == 0
        assert result["y"] == 0
        assert result["pressure"] == 0

    def test_max_values(self):
        result = pen_host.parse_dot(_make_packet(0xFFFFFFFF, 0xFFFFFFFF, 0xFFFF))
        assert result["x"] == 0xFFFFFFFF
        assert result["y"] == 0xFFFFFFFF
        assert result["pressure"] == 0xFFFF
