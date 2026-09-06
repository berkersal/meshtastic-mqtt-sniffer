import os
import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated, Literal

import paho.mqtt.client as mqtt
import typer
from dotenv import load_dotenv
from google.protobuf.message import DecodeError
from loguru import logger
from paho.mqtt.properties import Properties

from meshtastic_mqtt_sniffer.database import Database
from meshtastic_mqtt_sniffer.logging import (
    SEPARATOR,
    configure_logging,
    format_payload,
    print_application_payload,
    print_field,
    report_error,
    report_error_with_raw,
)
from meshtastic_mqtt_sniffer.translations import resolve_language, tr
from protobufs.meshtastic import mqtt_pb2

app = typer.Typer(add_completion=False, no_args_is_help=False)


def handle_message(
    database: Database,
    language: str,
    topic: str,
    raw: bytes,
) -> None:
    """Decode, persist, validate, and optionally display an MQTT message.

    Args:
        database (Database): Database class instance.
        language (str): Resolved output language code.
        topic (str): MQTT topic carrying the message.
        raw (bytes): Serialized Meshtastic service envelope.

    Returns:
        None: Packet data is persisted and output is written as side effects.
    """
    envelope = mqtt_pb2.ServiceEnvelope()
    try:
        envelope.ParseFromString(raw)
    except DecodeError as error:
        report_error_with_raw(
            tr(language, "decode_envelope", error=error),
            raw,
            f"topic={topic!r}",
        )
        return

    if not envelope.HasField("packet"):
        report_error_with_raw(
            tr(language, "no_packet"),
            raw,
            f"topic={topic!r} channel_id={envelope.channel_id!r} gateway_id={envelope.gateway_id!r}",
        )
        return

    packet = envelope.packet
    try:
        database.save_packet(topic, envelope, packet)
    except sqlite3.Error as error:
        report_error_with_raw(
            tr(language, "save_packet", error=error),
            raw,
            f"topic={topic!r}",
        )

    payload_variant = packet.WhichOneof("payload_variant")

    logger.success(f"\n{SEPARATOR}\n{tr(language, 'mqtt_message')}\n{SEPARATOR}")
    print_field(language, "topic", topic)
    print_field(language, "decode", "ServiceEnvelope")
    print_field(language, "channel_id", envelope.channel_id)
    print_field(language, "gateway_id", envelope.gateway_id)
    logger.success(f"\n{tr(language, 'packet')}")
    print_field(language, "from", f"0x{getattr(packet, 'from'):08x}")
    print_field(language, "to", f"0x{packet.to:08x}")
    print_field(language, "id", packet.id)
    rx_time = (
        tr(language, "unknown")
        if packet.rx_time == 0
        else datetime.fromtimestamp(packet.rx_time, UTC).isoformat().replace("+00:00", "Z")
    )
    print_field(language, "rx_time", rx_time)
    print_field(language, "rx_snr", f"{packet.rx_snr:.2f} dB")
    print_field(language, "rssi", packet.rx_rssi)
    print_field(language, "via_mqtt", packet.via_mqtt)
    print_field(language, "hop_limit", packet.hop_limit)
    print_field(language, "hop_start", packet.hop_start)
    logger.success(f"\n{tr(language, 'payload')}")
    if payload_variant == "decoded":
        print_application_payload(language, raw, packet.decoded.portnum, packet.decoded.payload)
    elif payload_variant == "encrypted":
        print_field(language, "encoding", tr(language, "encrypted"))
        print_field(language, "length", f"{len(packet.encrypted)} bytes")
        print_field(language, "content", format_payload(packet.encrypted))
    else:
        print_field(language, "encoding", tr(language, "missing"))
    logger.success(SEPARATOR)


@app.callback(invoke_without_command=True)
# ruff: ignore[PLR0913, PLR0917]
def sniff(
    language: Annotated[
        Literal["auto", "en", "tr"],
        typer.Option(
            "--lang",
            help="Output language: auto, en, or tr / Uygulama dili: auto, en veya tr.",
        ),
    ] = "auto",
    host: Annotated[
        str | None,
        typer.Option(
            "--host",
            help="MQTT host / MQTT sunucusu.",
        ),
    ] = None,
    port: Annotated[
        int | None,
        typer.Option(
            "--port",
            min=1,
            max=65535,
            help="MQTT port / MQTT portu.",
        ),
    ] = None,
    topic: Annotated[
        str | None,
        typer.Option(
            "--topic",
            help="Subscription topic / Abonelik konusu.",
        ),
    ] = None,
    database_path: Annotated[
        Path | None,
        typer.Option(
            "--database",
            help="SQLite database path / SQLite veritabanı konumu.",  # noqa: RUF001
        ),
    ] = None,
    log_path: Annotated[
        Path | None,
        typer.Option(
            "--log-file",
            help="Log file path / Günlük dosyası konumu.",  # noqa: RUF001
        ),
    ] = None,
    log_level: Annotated[
        Literal["DEBUG", "INFO", "SUCCESS", "WARNING", "ERROR", "CRITICAL"],
        typer.Option(
            "--log-level",
            help="Log level / Günlük seviyesi.",
        ),
    ] = "WARNING",
) -> None:
    """Subscribe to MQTT and process Meshtastic packets.

    Args:
        language (Literal["auto", "en", "tr"]): Output language selection.
        host (str | None): MQTT host override; otherwise uses ``MQTT_HOST``.
        port (int | None): MQTT port override; otherwise uses ``MQTT_PORT``.
        topic (str | None): Subscription topic override; otherwise uses ``MQTT_TOPIC``.
        database_path (Path | None): SQLite path override; otherwise uses ``MQTT_DB_PATH``.
        log_path (Path | None): Error-log path override; otherwise uses ``MQTT_LOG_FILE``.
        log_level (Literal["DEBUG", "INFO", "SUCCESS", "WARNING", "ERROR", "CRITICAL"]):
            Log level override; otherwise uses ``WARNING``.

    Returns:
        None: The function runs the MQTT event loop until it exits or fails.
    """
    load_dotenv()
    selected_language = resolve_language(language)
    log_name = str(log_path or os.getenv("MQTT_LOG_FILE", "meshtastic-mqtt-sniffer.log"))
    try:
        configure_logging(log_name, log_level)
    except OSError as error:
        logger.error(tr(selected_language, "could_not_open_log", path=log_name, error=error))
        raise typer.Exit(1) from error

    db_name = str(database_path or os.getenv("MQTT_DB_PATH", "packets.db"))
    try:
        database = Database(db_name)
    except sqlite3.Error as error:
        report_error(tr(selected_language, "could_not_open_db", path=db_name, error=error))
        raise typer.Exit(1) from error

    mqtt_host = host or os.getenv("MQTT_HOST", "localhost")
    mqtt_port = port or int(os.getenv("MQTT_PORT", "1883"))
    mqtt_topic = topic or os.getenv("MQTT_TOPIC", "msh/#")
    client_id = os.getenv("MQTT_CLIENT_ID", "meshtastic-mqtt-sniffer")
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=client_id)
    if (username := os.getenv("MQTT_USERNAME")) and (password := os.getenv("MQTT_PASSWORD")):
        client.username_pw_set(username, password)

    def on_connect(
        client: mqtt.Client,
        _userdata: object,
        _flags: mqtt.ConnectFlags,
        reason_code: mqtt.ReasonCode,
        _properties: Properties | None = None,
    ) -> None:
        """Subscribe after the MQTT client completes its connection attempt.

        Args:
            client (mqtt.Client): Connected MQTT client instance.
            _userdata (object): User data associated with the client.
            _flags (mqtt.ConnectFlags): MQTT connection flags supplied by Paho.
            reason_code (mqtt.ReasonCode): MQTT connection result code.
            _properties (Properties | None): MQTT v5 connection properties, when provided.

        Returns:
            None: The client subscribes on success or logs the connection error.
        """
        if reason_code.is_failure:
            report_error(tr(selected_language, "connection_error", error=reason_code))
            return
        client.subscribe(mqtt_topic, qos=0)
        logger.success(tr(selected_language, "subscribed", topic=mqtt_topic))

    def on_message(_client: mqtt.Client, _userdata: object, message: mqtt.MQTTMessage) -> None:
        """Process an MQTT message delivered by Paho.

        Args:
            _client (mqtt.Client): MQTT client that delivered the message.
            _userdata (object): User data associated with the client.
            message (mqtt.MQTTMessage): MQTT message containing topic and payload.

        Returns:
            None: The message is handed to the Meshtastic packet handler.
        """
        handle_message(
            database,
            selected_language,
            message.topic,
            message.payload,
        )

    client.on_connect = on_connect
    client.on_message = on_message
    try:
        client.connect(mqtt_host, mqtt_port, keepalive=30)
        client.loop_forever()
    except OSError as error:
        report_error(tr(selected_language, "connection_error", error=error))
        raise typer.Exit(1) from error
    finally:
        database.close()


if __name__ == "__main__":
    app()
