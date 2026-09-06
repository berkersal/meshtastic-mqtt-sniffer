import contextlib
import sqlite3
from datetime import UTC, datetime

from protobufs.meshtastic import (
    mesh_pb2,
    mqtt_pb2,
    portnums_pb2,
)


class Database:
    """Manages the SQLite database connection and packet storage for the Meshtastic MQTT sniffer."""

    def __init__(self, path: str) -> None:
        """Initialize the database with the given path."""
        self._path = path
        self._db = self.open_database()

    def open_database(self) -> sqlite3.Connection:
        """Open the SQLite database and create its packet table and indexes.

        Returns:
            sqlite3.Connection: Initialized connection with WAL and busy timeout enabled.
        """
        database = sqlite3.connect(self._path)
        database.execute("PRAGMA journal_mode = WAL")
        database.execute("PRAGMA busy_timeout = 5000")
        database.executescript("""
            CREATE TABLE IF NOT EXISTS packets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                received_at TEXT NOT NULL,
                mqtt_topic TEXT NOT NULL, channel_id TEXT NOT NULL, gateway_id TEXT NOT NULL,
                sender TEXT NOT NULL, receiver TEXT NOT NULL, packet_id INTEGER NOT NULL,
                port_number INTEGER, port_name TEXT, payload_encoding TEXT NOT NULL,
                payload_text TEXT, payload_hex TEXT, rx_time TEXT, rx_snr REAL NOT NULL,
                rx_rssi INTEGER NOT NULL, hop_limit INTEGER NOT NULL, hop_start INTEGER NOT NULL,
                via_mqtt INTEGER NOT NULL
            );
            CREATE INDEX IF NOT EXISTS packets_received_at_idx ON packets(received_at);
            CREATE INDEX IF NOT EXISTS packets_sender_idx ON packets(sender);
            CREATE INDEX IF NOT EXISTS packets_receiver_idx ON packets(receiver);
            CREATE INDEX IF NOT EXISTS packets_port_idx ON packets(port_number);
            CREATE INDEX IF NOT EXISTS packets_channel_idx ON packets(channel_id);
            CREATE INDEX IF NOT EXISTS packets_topic_idx ON packets(mqtt_topic);
        """)
        return database

    def close(self) -> None:
        """Close the SQLite database connection."""
        self._db.close()

    def save_packet(
        self,
        topic: str,
        envelope: mqtt_pb2.ServiceEnvelope,
        packet: mesh_pb2.MeshPacket,
    ) -> None:
        """Persist MQTT and Meshtastic packet metadata in SQLite.

        Args:
            topic (str): MQTT topic carrying the packet.
            envelope (mqtt_pb2.ServiceEnvelope): Decoded Meshtastic service envelope.
            packet (mesh_pb2.MeshPacket): Mesh packet extracted from the envelope.

        Returns:
            None: The packet is inserted and the transaction is committed.
        """
        payload_variant = packet.WhichOneof("payload_variant")
        port_number = port_name = payload_text = payload_hex = None
        if payload_variant == "decoded":
            decoded = packet.decoded
            port_number = decoded.portnum
            with contextlib.suppress(ZeroDivisionError):
                port_name = portnums_pb2.PortNum.Name(port_number)

            payload_hex = decoded.payload.hex()
            with contextlib.suppress(UnicodeDecodeError):
                payload_text = decoded.payload.decode("utf-8")
            encoding = "decoded"
        elif payload_variant == "encrypted":
            encoding = "encrypted"
            payload_hex = packet.encrypted.hex()
        else:
            encoding = "missing"

        rx_time = (
            datetime.fromtimestamp(packet.rx_time, UTC).isoformat().replace("+00:00", "Z") if packet.rx_time else None
        )
        self._db.execute(
            """INSERT INTO packets (
                received_at, mqtt_topic, channel_id, gateway_id, sender, receiver, packet_id,
                port_number, port_name, payload_encoding, payload_text, payload_hex, rx_time,
                rx_snr, rx_rssi, hop_limit, hop_start, via_mqtt
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                datetime.now(UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z"),
                topic,
                envelope.channel_id,
                envelope.gateway_id,
                f"0x{getattr(packet, 'from'):08x}",
                f"0x{packet.to:08x}",
                packet.id,
                port_number,
                port_name,
                encoding,
                payload_text,
                payload_hex,
                rx_time,
                packet.rx_snr,
                packet.rx_rssi,
                packet.hop_limit,
                packet.hop_start,
                packet.via_mqtt,
            ),
        )
        self._db.commit()
