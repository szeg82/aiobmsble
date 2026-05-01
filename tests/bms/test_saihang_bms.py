"""Test the Saihang BMS implementation."""

from collections.abc import Buffer
from typing import Final
from uuid import UUID

from bleak.backends.characteristic import BleakGATTCharacteristic
import pytest

from aiobmsble import BMSSample
from aiobmsble.bms.saihang_bms import BMS
from tests.bluetooth import generate_ble_device
from tests.conftest import MockBleakClient
from tests.test_basebms import BMSBasicTests


class TestBasicBMS(BMSBasicTests):
    """Test the basic BMS functionality."""

    bms_class = BMS


class MockSaihangBleakClient(MockBleakClient):
    """Emulate a Saihang BMS BleakClient."""

    _RESP: Final[bytes] = (
        b"\xa5\xa5\x00\x03\xa6\x00\x00\x00\x00\x00\x00\x0a\xa8\x00\x60\x00\x64\x00\x00\x25\xa6\x00"
        b"\x00\x27\x10\x00\x00\x27\x10\x00\x02\xff\xff\x00\x01\x00\x00\x06\x00\x00\x00\x00\x00\x00"
        b"\x08\x0d\xa9\x0d\x6a\x0d\x28\x0d\x3d\x0d\x2c\x0d\x6b\x0d\x4d\x0d\x38\xff\xff\xff\xff\xff"
        b"\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\x00\x02\x0b"
        b"\x43\x0b\x46\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\x0b\x56\x0b"
        b"\xa4\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\x00\x00\xdd\xe0\x00\x00\xe1"
        b"\x00\x00\x00\xd3\x40\x00\x0a\x0e\x10\x0e\x42\x0d\x34\x00\x0a\x00\x00\xb3\xb0\x00\x00\xaf"
        b"\xc8\x00\x00\xbb\x80\x00\x0a\x0b\x54\x0a\xf0\x0b\xb8\x00\x0a\xff\xff\xe8\xe5"
    )

    async def write_gatt_char(
        self,
        char_specifier: BleakGATTCharacteristic | int | str | UUID,
        data: Buffer,
        response: bool | None = None,
    ) -> None:
        """Issue write command to GATT."""

        await super().write_gatt_char(char_specifier, data, response)

        assert (
            self._notify_callback
        ), "write to characteristics but notification not enabled"

        if bytes(data) != b"\xa5\xa5\x00\x03\x00\x00\x00\x53\x04\x26":
            return

        self._notify_callback("MockRoyPowBleakClient", self._RESP)


async def test_update(patch_bleak_client, keep_alive_fixture: bool) -> None:
    """Test Saihang BMS data update."""

    patch_bleak_client(MockSaihangBleakClient)

    bms = BMS(generate_ble_device(), keep_alive_fixture)

    assert await bms.async_update() == {
        "voltage": 27.28,
        "temperature": 18.275,
        "battery_charging": False,
        "battery_health": 100,
        "battery_level": 96,
        "cell_count": 8,
        "current": 0.0,
        "cycles": 2,
        "temp_sensors": 4,
        "temp_values": [15.3, 15.6, 17.2, 25.0],
        "cell_voltages": [
            3.497,
            3.434,
            3.368,
            3.389,
            3.372,
            3.435,
            3.405,
            3.384,
        ],
        "cycle_capacity": 2629.246,
        "cycle_charge": 96.38,
        "total_charge": 100.0,
        "delta_voltage": 0.129,
        "design_capacity": 100.0,
        "balancer": 0,
        "chrg_mosfet": True,
        "dischrg_mosfet": True,
        "pack_ov_alarm": 56.8,
        "pack_ov_protection": 57.6,
        "pack_ov_release": 54.08,
        "pack_ov_delay": 1.0,
        "cell_ov_alarm": 3.6,
        "cell_ov_protection": 3.65,
        "cell_ov_release": 3.38,
        "cell_ov_delay": 1.0,
        "pack_uv_alarm": 46.0,
        "pack_uv_protection": 45.0,
        "pack_uv_release": 48.0,
        "pack_uv_delay": 1.0,
        "cell_uv_alarm": 2.9,
        "cell_uv_protection": 2.8,
        "cell_uv_release": 3.0,
        "cell_uv_delay": 1.0,
        "problem": False,
        "problem_code": 0,
        "power": 0.0,
    }

    # query again to check already connected state
    await bms.async_update()
    assert bms.is_connected is keep_alive_fixture

    await bms.disconnect()


def test_uuid_tx_not_used() -> None:
    """Test that TX UUID is intentionally not used."""
    assert BMS.uuid_tx() == "fffb"


@pytest.mark.parametrize(
    ("wrong_response"),
    [
        b"",
        b"\xa5\xa5\x00\x03\xa6\x71\x5c",
        b"\xa5\xa6" + MockSaihangBleakClient._RESP[2:],
        MockSaihangBleakClient._RESP[:-2] + b"\x00\x00",
        b"\xa5\xa5\x00\x03\x89" + MockSaihangBleakClient._RESP[5:-2] + b"\xfc\x79",
    ],
    ids=[
        "empty",
        "minimal",
        "wrong_SOF",
        "wrong_CRC",
        "wrong_length",
    ],
)
async def test_invalid_response(
    monkeypatch: pytest.MonkeyPatch,
    patch_bleak_client,
    patch_bms_timeout,
    wrong_response: bytes,
) -> None:
    """Test data up date with BMS returning invalid data."""

    patch_bms_timeout()
    monkeypatch.setattr(MockSaihangBleakClient, "_RESP", bytearray(wrong_response))
    patch_bleak_client(MockSaihangBleakClient)

    bms = BMS(generate_ble_device())

    result: BMSSample = {}
    with pytest.raises(TimeoutError):
        result = await bms.async_update()

    assert not result
    await bms.disconnect()
