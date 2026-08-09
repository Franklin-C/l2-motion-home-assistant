"""Constants for L2 Motion Bed."""

DOMAIN = "l2_motion"
DEVICE_NAME = "HHC0051745CDEF"
SERVICE_UUID = "0000ffe0-0000-1000-8000-00805f9b34fb"
WRITE_UUID = "0000ffe1-0000-1000-8000-00805f9b34fb"

CONF_CONNECTION_TYPE = "connection_type"
CONNECTION_BLUETOOTH = "bluetooth"
CONNECTION_WINDOWS_BRIDGE = "windows_bridge"
DEFAULT_BRIDGE_PORT = 8765

COMMANDS = {
    "light": "A",
    "foot_massage": "B",
    "head_massage": "C",
    "stop_massage": "D",
    "head_up": "K",
    "head_down": "L",
    "feet_up": "M",
    "feet_down": "N",
    "home": "O",
    "extra_up": "P",
    "extra_down": "Q",
    "memory_1": "U",
    "memory_2": "V",
}

PLATFORMS = ["button"]
