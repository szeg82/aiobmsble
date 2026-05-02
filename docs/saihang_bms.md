# Saihang BMS (Anenji) Documentation

## Overview

The Saihang BMS (often branded as Anenji) uses a custom Bluetooth Low Energy protocol that is heavily based on Modbus RTU, but wrapped in a proprietary frame starting with `A5 A5`. 
The BMS returns a large, contiguous block of registers containing real-time telemetry and battery parameters. Additional protection settings exist later in the register map, but are currently documented only for future extension.

## Device Identification

- **Local Name**: `SH*` (e.g., SH-BMS)
- **Service UUID**: `0000fffa-0000-1000-8000-00805f9b34fb` (Short: `fffa`)
- **Notification Characteristic**: `0000fffc-0000-1000-8000-00805f9b34fb` (read/notify)
- **Write Characteristic**: `0000fffb-0000-1000-8000-00805f9b34fb` (write)

### Device Discovery

The Saihang BMS is detected using:
- A local name matching the prefix `SH`
- Service UUID `fffa`
- The device must be connectable.

## Protocol Mechanics

### The Polling Command

Unlike some BMS devices that push data automatically, the Saihang BMS requires an active polling command to stream telemetry. The driver periodically writes a Modbus `Read Holding Registers` (0x03) command to the `fffb` characteristic.

The polling command structure currently used by the driver is:
`A5 A5 01 03 00 00 00 48 [CRC16]`

- `A5 A5`: Start of Frame (SOF)
- `01`: Device ID
- `03`: Modbus Function (Read Holding Registers)
- `00 00`: Starting Register (Address 0)
- `00 48`: Number of registers to read (72 registers = 144 bytes of data)
- `CRC16`: Standard Modbus CRC-16

The `0x48` request covers all currently supported telemetry fields, including cell voltages, temperatures, MOSFET state, balancer state, MOSFET temperature, and ambient temperature.

Additional voltage protection settings exist later in the register map. Requesting `0x53` registers would include more of that block, but those values are currently not exposed by the driver and are documented only for future extension.

### Response Fragmentation

The BLE MTU size is typically smaller than the requested payload. The BMS may split the response across multiple BLE notification frames. The `aiobmsble` driver accumulates these frames until the total length matches the expected length defined in the 5th byte of the response header (`data[4]`).

### Temperatures
The telemetry block contains up to 4 standard cell NTC sensors starting at byte offset 87. However, the payload contains two additional dedicated sensors:
- **MOSFET Temperature**: Located at byte offset 107.
- **Ambient Temperature**: Located at byte offset 109.
These are now appended dynamically to the `temp_values` array so that Home Assistant can track the internal transistor and ambient case temperatures independently.

### 3. Hardware Switch States
The 16-bit word at offset 37 represents the `Fault & Switch Status Bitmask`. 
- **Bit 9 (`0x0200`)**: Charge MOSFET state
- **Bit 10 (`0x0400`)**: Discharge MOSFET state
- **Bit 13 (`0x2000`)**: AC IN state

### Supported Telemetry Memory Map

The following table documents the currently supported part of the Saihang BMS response payload. Offsets are byte offsets in the complete response frame, including the `A5 A5` frame header.

The current driver request (`0x48` registers) returns a 144-byte data block, which is sufficient for all supported runtime telemetry fields.

| Byte Offset | Length | Raw Example | Decoded Example | Description |
|---:|---:|---|---|---|
| 0 | 2 | `a5a5` | - | Frame header (SOF) |
| 2 | 1 | `01` | 1 | Device ID |
| 3 | 1 | `03` | 3 | Modbus function code |
| 4 | 1 | `90` | 144 | Payload data length in bytes |
| 5 | 4 | `fffffe54` | -4.28 A | Current |
| 9 | 4 | `000014d6` | 53.34 V | Total voltage |
| 13 | 2 | `0063` | 99 % | Battery level / SOC |
| 15 | 2 | `0064` | 100 % | Battery health / SOH |
| 17 | 4 | `00007b55` | 315.73 Ah | Cycle charge / remaining capacity |
| 21 | 4 | `00007c11` | 317.61 Ah | Total charge |
| 25 | 4 | `00007530` | 300.00 Ah | Design capacity |
| 29 | 2 | `003e` | 62 | Cycle count |
| 31 | 2 | `ffff` | 0 | Problem code, inverted bitmask |
| 33 | 2 | `0000` | 0 | Alarm status bitmask, currently not exposed |
| 35 | 2 | `0000` | 0 | Protection status bitmask, currently not exposed |
| 37 | 2 | `0e00` | - | Fault and switch status bitmask |
| 39 | 2 | `0000` | - | Padding / upper balancer bits |
| 41 | 2 | `0000` | 0 | Balancer state bitmask |
| 43 | 2 | `0010` | 16 | Cell count |
| 45 | 2 | `0d08` | 3.336 V | Cell 1 voltage |
| 47 | 2 | `0d02` | 3.330 V | Cell 2 voltage |
| 49 | 2 | `0d06` | 3.334 V | Cell 3 voltage |
| 51 | 2 | `0cfe` | 3.326 V | Cell 4 voltage |
| 53 | 2 | `0d06` | 3.334 V | Cell 5 voltage |
| 55 | 2 | `0d07` | 3.335 V | Cell 6 voltage |
| 57 | 2 | `0d04` | 3.332 V | Cell 7 voltage |
| 59 | 2 | `0d0e` | 3.342 V | Cell 8 voltage |
| 61 | 2 | `0d08` | 3.336 V | Cell 9 voltage |
| 63 | 2 | `0cfb` | 3.323 V | Cell 10 voltage |
| 65 | 2 | `0d05` | 3.333 V | Cell 11 voltage |
| 67 | 2 | `0d03` | 3.331 V | Cell 12 voltage |
| 69 | 2 | `0d0e` | 3.342 V | Cell 13 voltage |
| 71 | 2 | `0d0b` | 3.339 V | Cell 14 voltage |
| 73 | 2 | `0d08` | 3.336 V | Cell 15 voltage |
| 75 | 2 | `0d04` | 3.332 V | Cell 16 voltage |
| 77 | 8 | `ffffffffffffffff` | - | Reserved for cells 17-20 |
| 85 | 2 | `0004` | 4 | Temperature sensor count |
| 87 | 2 | `0b80` | 21.3 °C | Temperature sensor 1 |
| 89 | 2 | `0b7e` | 21.1 °C | Temperature sensor 2 |
| 91 | 2 | `0b74` | 20.1 °C | Temperature sensor 3 |
| 93 | 2 | `0b7a` | 20.7 °C | Temperature sensor 4 |
| 95 | 12 | `ffffffffffffffffffffffff` | - | Reserved for temperature sensors 5-10 |
| 107 | 2 | `0b64` | 18.5 °C | MOSFET temperature |
| 109 | 2 | `0b8a` | 22.3 °C | Ambient temperature |
| 111 | 14 | `ffffffffffffffffffffffffffff` | - | Padding / unused area |

## Known Unsupported Voltage Protection Settings

The Saihang BMS memory map continues after the supported telemetry block with voltage protection settings. These values are currently documented for future extension, but are not exposed by the driver.

With the current `0x48` request, only the beginning of this settings area may be present. A larger request, such as `0x53`, would be needed to retrieve the complete block.

| Byte Offset | Length | Raw Example | Decoded Example | Description |
|---:|---:|---|---|---|
| 125 | 4 | `0000dde0` | 56.80 V | Pack OV alarm |
| 129 | 4 | `0000e100` | 57.60 V | Pack OV protection |
| 133 | 4 | `0000d340` | 54.08 V | Pack OV release protection |
| 137 | 2 | `000a` | 1.0 s | Pack OV protection delay time |
| 139 | 2 | `0e10` | 3.60 V | Cell OV alarm |
| 141 | 2 | `0e42` | 3.65 V | Cell OV protection |
| 143 | 2 | `0d34` | 3.38 V | Cell OV release protection |
| 145 | 2 | `000a` | 1.0 s | Cell OV protection delay time |
| 147 | 4 | `0000....` | ... V | Pack UV alarm, incomplete in 144-byte payload |
| 151 | 4 | `........` | ... V | Pack UV protection, theoretical with larger request |
| 155 | 4 | `........` | ... V | Pack UV release protection, theoretical with larger request |
| 159 | 2 | `....` | ... s | Pack UV protection delay time, theoretical with larger request |
| 161 | 2 | `....` | ... V | Cell UV alarm, theoretical with larger request |
| 163 | 2 | `....` | ... V | Cell UV protection, theoretical with larger request |
| 165 | 2 | `....` | ... V | Cell UV release protection, theoretical with larger request |
| 167 | 2 | `....` | ... s | Cell UV protection delay time, theoretical with larger request |
