"""Hatchling hook that generates bundled Meshtastic protobuf bindings."""

from __future__ import annotations

import importlib.util
from pathlib import Path

from hatchling.builders.hooks.plugin.interface import BuildHookInterface  # ty: ignore[unresolved-import]


class CustomBuildHook(BuildHookInterface):
    """Generate typed Python protobuf bindings before building the package."""

    PLUGIN_NAME = "custom"

    def initialize(
        self,
        _version: str,
        _build_data: dict[str, object],
    ) -> None:
        """Generate protobuf modules before Hatchling packages the project."""
        generator_path = Path(self.root) / "src" / "protobufs" / "generate_protobufs.py"

        spec = importlib.util.spec_from_file_location(
            "generate_protobufs",
            generator_path,
        )
        if spec is None or spec.loader is None:
            err_msg = f"Unable to load protobuf generator: {generator_path}"
            raise RuntimeError(err_msg)

        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        module.generate_protobufs(Path(self.root))
