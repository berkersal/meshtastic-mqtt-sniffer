import sys
from typing import cast

from google.protobuf.message import DecodeError, Message
from loguru import logger

from meshtastic_mqtt_sniffer.translations import tr
from protobufs.meshtastic import (
    mesh_pb2,
    portnums_pb2,
    telemetry_pb2,
)

SEPARATOR = "=" * 80


def configure_logging(log_path: str, log_level: str) -> None:
    """Configure Loguru sinks for standard output, standard error, and error logs.

    Args:
        log_path (str): Filesystem path for the error-only log file.
        log_level (str): Log level for the sinks.

    Returns:
        None: Loguru's global logger is configured as a side effect.
    """
    logger.remove()
    logger.add(
        sys.stdout,
        level=log_level,
        filter=lambda record: record["level"].name not in ("ERROR", "CRITICAL"),
        format="{message}",
    )
    logger.add(sys.stderr, level="ERROR", format="{message}")
    logger.add(log_path, level=log_level, encoding="utf-8", format="[{time:YYYY-MM-DD HH:mm:ss.SSS}] {message}")


def report_error(message: str) -> None:
    """Write an error using the configured Loguru sinks.

    Args:
        message (str): Error message to record and display.

    Returns:
        None: The error is emitted as a side effect.
    """
    logger.error(message)


def format_payload(payload: bytes) -> str:
    """Format MQTT payload data as hexadecimal and decoded UTF-8 text.

    Args:
        payload (bytes): Raw MQTT payload data to format.

    Returns:
        str: A hexadecimal and UTF-8 representation of the payload. Invalid byte sequences are replaced.
    """
    utf8_payload = payload.decode("utf-8", errors="replace")
    return f"0x{payload.hex()} utf8={utf8_payload!r}"


def report_error_with_raw(message: str, raw: bytes, context: str) -> None:
    """Report an error with parsed context and the raw MQTT message.

    Args:
        message (str): Error message to record and display.
        raw (bytes): Original raw MQTT message bytes.
        context (str): Parsed context relevant to the error.

    Returns:
        None: The error is emitted through the configured Loguru sinks.
    """
    report_error(f"{message}; {context}; raw_message={format_payload(raw)}")


def print_field(language: str, key: str, value: object) -> None:
    """Print one localized label and value in packet output.

    Args:
        language (str): Resolved output language code.
        key (str): Translation key for the field label.
        value (object): Value to render after the localized label.

    Returns:
        None: This function writes the field to standard output.
    """
    logger.success(f"  {tr(language, key):<11}: {value}")


# ruff: ignore[PLR0912, PLR0915, C901]
def print_application_payload(language: str, raw: bytes, portnum: int, payload: bytes) -> None:
    """Decode and display a Meshtastic application payload.

    Args:
        language (str): Resolved output language code.
        raw (bytes): Original raw MQTT message bytes.
        portnum (int): Meshtastic application port number.
        payload (bytes): Decoded application payload to display.

    Returns:
        None: Payload details are written to standard output.
    """
    try:
        port_name = portnums_pb2.PortNum.Name(portnum)
    except ValueError:
        report_error_with_raw(
            tr(language, "unknown_port", portnum=portnum),
            raw,
            f"portnum={portnum} application_payload={format_payload(payload)}",
        )
        print_field(language, "content", f"{tr(language, 'unknown')} port {portnum}")
        print_field(language, "raw", format_payload(payload))
        return

    if port_name == "TEXT_MESSAGE_APP":
        try:
            print_field(language, "type", "text")
            print_field(language, "content", repr(payload.decode("utf-8")))
        except UnicodeDecodeError as error:
            report_error_with_raw(
                tr(language, "invalid_text", error=error),
                raw,
                f"port=TEXT_MESSAGE_APP application_payload=0x{payload.hex()}",
            )
            print_field(language, "decode", tr(language, "invalid_utf8", error=error))
            print_field(language, "raw", format_payload(payload))
        return

    message_types: dict[str, tuple[type[Message], str]] = {
        "POSITION_APP": (mesh_pb2.Position, "Position"),
        "NODEINFO_APP": (mesh_pb2.User, "User"),
        "WAYPOINT_APP": (mesh_pb2.Waypoint, "Waypoint"),
        "TELEMETRY_APP": (telemetry_pb2.Telemetry, "Telemetry"),
    }
    if port_name not in message_types:
        print_field(language, "encoding", tr(language, "protobuf_binary"))
        print_field(language, "raw", format_payload(payload))
        return

    message_type, name = message_types[port_name]
    try:
        decoded = message_type()
        decoded.ParseFromString(payload)
    except DecodeError as error:
        report_error_with_raw(
            tr(language, "decode_payload", message_type=name, error=error),
            raw,
            f"application_payload=0x{payload.hex()}",
        )
        print_field(language, "type", name)
        print_field(language, "decode", f"{tr(language, 'failed').lower()} - {error}")
        print_field(language, "raw", format_payload(payload))
        return

    print_field(language, "type", name)
    if port_name == "POSITION_APP":
        decoded = cast("mesh_pb2.Position", decoded)
        if (latitude := decoded.latitude_i if decoded.HasField("latitude_i") else None) is not None:
            print_field(language, "latitude", f"{latitude / 10_000_000:.7f}")
        if (longitude := decoded.longitude_i if decoded.HasField("longitude_i") else None) is not None:
            print_field(language, "longitude", f"{longitude / 10_000_000:.7f}")
        if (altitude := decoded.altitude if decoded.HasField("altitude") else None) is not None:
            print_field(language, "altitude", f"{altitude} m")
        print_field(language, "timestamp", decoded.timestamp)
    elif port_name == "NODEINFO_APP":
        decoded = cast("mesh_pb2.User", decoded)
        print_field(language, "id", decoded.id)
        print_field(language, "long_name", decoded.long_name)
        print_field(language, "short_name", decoded.short_name)
    elif port_name == "WAYPOINT_APP":
        decoded = cast("mesh_pb2.Waypoint", decoded)
        print_field(language, "id", decoded.id)
        if (latitude := decoded.latitude_i if decoded.HasField("latitude_i") else None) is not None:
            print_field(language, "latitude", f"{latitude / 10_000_000:.7f}")
        if (longitude := decoded.longitude_i if decoded.HasField("longitude_i") else None) is not None:
            print_field(language, "longitude", f"{longitude / 10_000_000:.7f}")
        print_field(language, "content", decoded.name)
    elif port_name == "TELEMETRY_APP":
        decoded = cast("telemetry_pb2.Telemetry", decoded)
        print_field(language, "timestamp", decoded.time)
        variant = decoded.WhichOneof("variant")
        print_field(language, "variant", variant or tr(language, "missing"))
        if variant == "device_metrics":
            metrics = decoded.device_metrics
            print_field(language, "battery", metrics.battery_level if metrics.HasField("battery_level") else None)
            print_field(language, "voltage", metrics.voltage if metrics.HasField("voltage") else None)
            print_field(language, "uptime", metrics.uptime_seconds if metrics.HasField("uptime_seconds") else None)
        elif variant == "environment_metrics":
            metrics = decoded.environment_metrics
            print_field(language, "temperature", metrics.temperature if metrics.HasField("temperature") else None)
            print_field(
                language,
                "humidity",
                metrics.relative_humidity if metrics.HasField("relative_humidity") else None,
            )
            print_field(
                language,
                "pressure",
                metrics.barometric_pressure if metrics.HasField("barometric_pressure") else None,
            )
