# Saihang BMS (Anenji) Documentation

## Overview

The Saihang BMS (often branded as Anenji) uses a custom Bluetooth Low Energy protocol that is heavily based on Modbus RTU, but wrapped in a proprietary frame starting with `A5 A5`. The BMS streams a large, contiguous block of registers containing real-time telemetry, battery parameters, and protection settings.

During the development and reverse-engineering of the `aiobmsble` driver, the complete Modbus memory map was extracted from the official Android application (internally referred to as the "BlueCat" protocol).

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

The polling command structure is:
`A5 A5 01 03 00 00 00 53 [CRC16]`

- `A5 A5`: Start of Frame (SOF)
- `01`: Device ID
- `03`: Modbus Function (Read Holding Registers)
- `00 00`: Starting Register (Address 0)
- `00 53`: Number of Registers to read (83 registers = 166 bytes of data). *Note: Earlier implementations only requested `0x48` (72 registers / 144 bytes), which cut off the Voltage Protection Settings. Requesting `0x53` ensures the entire settings block is retrieved.*
- `CRC16`: Standard Modbus CRC-16-CCITT

### Response Fragmentation
The BLE MTU size is typically smaller than the 166-byte payload. The BMS will split the response across multiple BLE notification frames. The `aiobmsble` driver accumulates these frames until the total length matches the expected length defined in the 5th byte of the response header (`data[4]`).

## Memory Map Discoveries

Detailed testing and comparison against the official application revealed several critical breakthroughs for the driver:

### 1. Temperature Calculation
The raw NTC temperature values are transmitted as an integer. Based on detailed testing and comparison with the values reported by the official app, the correct conversion was found to be `(val - 2730) / 10.0`. Earlier testing with the standard Kelvin-to-Celsius style `- 273.1` offset produced a consistent `-0.1°C` discrepancy, so the driver now uses the tested conversion formula to match the official app.

### 2. MOSFET and Ambient Temperatures
The telemetry block contains up to 4 standard cell NTC sensors starting at byte offset 87. However, the payload contains two additional dedicated sensors:
- **MOSFET Temperature**: Located at byte offset 107.
- **Ambient Temperature**: Located at byte offset 109.
These are now appended dynamically to the `temp_values` array so that Home Assistant can track the internal transistor and ambient case temperatures independently.

### 3. Hardware Switch States
The 16-bit word at offset 37 represents the `Fault & Switch Status Bitmask`. 
- **Bit 9 (`0x0200`)**: Charge MOSFET state
- **Bit 10 (`0x0400`)**: Discharge MOSFET state
- **Bit 13 (`0x2000`)**: AC IN state

### 4. The "Padding" Mystery
Bytes 111 to 124 contain `FFFFFFFF...` padding. This is because the BMS's internal memory map is contiguous. Telemetry data ends at byte 110, and the static Voltage Protection Settings start at byte 125. The gap between these two regions simply contains unused/reserved Modbus registers. By requesting a single large block of `0x53` registers, the driver naturally bridges this gap and retrieves both telemetry and settings simultaneously.

### 5. Extended Capabilities
The driver successfully maps the following extended fields not found on basic BMS units:
- `balancer`: Live bitmask of which specific cells are currently being actively balanced.
- `total_charge`: Total Ah throughput over the entire lifecycle of the battery.
- `pack_ov_alarm` ... `cell_uv_delay`: 16 individual Voltage Protection settings dynamically extracted if the payload length permits.
