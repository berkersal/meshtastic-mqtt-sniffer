"""Generate typed Python bindings from the bundled Meshtastic protobuf schemas."""

from __future__ import annotations

import importlib.resources
import shutil
from pathlib import Path

from grpc_tools import protoc


def generate_protobufs(root: Path | None = None) -> None:
    """Generate Python protobuf modules and type stubs.

    Args:
        root: Project root. Defaults to the directory containing this file.

    Raises:
        RuntimeError: If the protobuf compiler exits unsuccessfully.
    """
    if root is None:
        root = Path(__file__).resolve().parent.parent.parent

    proto_root = root / "protobufs"
    source_root = root / "src"
    protobufs_dir = source_root / "protobufs"
    gitignore = protobufs_dir / ".gitignore"

    with gitignore.open() as f:
        for line in f.readlines():
            for ignored_file in protobufs_dir.rglob(line.strip()):
                ignored_file.unlink(missing_ok=True)

    proto_files = sorted(path.relative_to(proto_root).as_posix() for path in proto_root.rglob("*.proto"))

    if not proto_files:
        err_msg = f"No protobuf files found in {proto_root}"
        raise RuntimeError(err_msg)

    # grpcio-tools bundles the standard Google protobuf .proto files,
    # including google/protobuf/descriptor.proto, under grpc_tools/_proto.
    grpc_proto_include = str(importlib.resources.files("grpc_tools").joinpath("_proto"))

    result = protoc.main(
        [
            "protoc",
            f"--proto_path={proto_root}",
            f"--proto_path={grpc_proto_include}",
            f"--python_out={protobufs_dir}",
            f"--pyi_out={protobufs_dir}",
            *proto_files,
        ],
    )

    if result != 0:
        err_msg = "Failed to generate Python protobuf modules."
        raise RuntimeError(err_msg)

    _rewrite_imports(protobufs_dir)


def _move_root_modules(source_root: Path, output_package: Path) -> None:
    """Move generated top-level protobuf modules into the public package."""
    for pattern in ("*_pb2.py", "*_pb2.pyi"):
        for module in source_root.glob(pattern):
            shutil.move(str(module), output_package / module.name)


def _rewrite_imports(output_package: Path) -> None:
    """Rewrite generated imports to use the public protobuf package."""
    for pattern in ("*_pb2.py", "*_pb2.pyi"):
        for module in output_package.rglob(pattern):
            source = module.read_text(encoding="utf-8")
            source = source.replace(
                "from meshtastic import ",
                "from protobufs.meshtastic import ",
            )
            source = source.replace(
                "import nanopb_pb2 as ",
                "from protobufs.meshtastic import nanopb_pb2 as ",
            )
            module.write_text(source, encoding="utf-8")


def main() -> None:
    """Generate Python protobuf modules and type stubs."""
    generate_protobufs()


if __name__ == "__main__":
    main()
