import json
from dataclasses import dataclass
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]

DEFAULT_CAPABILITIES_PATH = (
    PROJECT_ROOT / "data" / "knowledge" / "system_capabilities.json"
)


@dataclass(frozen=True)
class SystemCapability:
    capability: str
    available: bool
    content: str


@dataclass
class SystemCapabilitiesContext:
    context: str
    capability_count: int
    capabilities: list[str]


class SystemCapabilitiesProvider:
    def __init__(
        self,
        capabilities_path: Path = (DEFAULT_CAPABILITIES_PATH),
    ):

        self.capabilities_path = capabilities_path

        self._capabilities = self._load_capabilities()

    def _load_capabilities(
        self,
    ) -> list[SystemCapability]:

        if not self.capabilities_path.exists():
            raise FileNotFoundError(
                f"System capabilities file not found: {self.capabilities_path}"
            )

        with self.capabilities_path.open(
            "r",
            encoding="utf-8",
        ) as file:
            data = json.load(file)

        if not isinstance(
            data,
            list,
        ):
            raise ValueError("System capabilities must contain a JSON list.")  # noqa: TRY004

        if not data:
            raise ValueError("System capabilities cannot be empty.")

        capabilities = []

        seen = set()

        for index, item in enumerate(data):
            if not isinstance(
                item,
                dict,
            ):
                raise ValueError(f"Capability {index} must be an object.")  # noqa: TRY004

            capability = item.get("capability")

            available = item.get("available")

            content = item.get("content")

            if (
                not isinstance(
                    capability,
                    str,
                )
                or not capability.strip()
            ):
                raise ValueError(f"Capability {index} has an invalid name.")

            capability = capability.strip()

            if capability in seen:
                raise ValueError(f"Duplicate system capability: {capability}")

            seen.add(capability)

            if not isinstance(
                available,
                bool,
            ):
                raise ValueError(f"Capability {index} available must be a boolean.")  # noqa: TRY004

            if (
                not isinstance(
                    content,
                    str,
                )
                or not content.strip()
            ):
                raise ValueError(f"Capability {index} has invalid content.")

            capabilities.append(
                SystemCapability(
                    capability=capability,
                    available=available,
                    content=content.strip(),
                )
            )

        return capabilities

    def build(
        self,
    ) -> SystemCapabilitiesContext:

        sections = []

        for index, capability in enumerate(
            self._capabilities,
            start=1,
        ):
            status = "available" if capability.available else "unavailable"

            sections.append(
                f"System capability {index}\n"
                f"Capability: "
                f"{capability.capability}\n"
                f"Status: {status}\n"
                f"Content: "
                f"{capability.content}"
            )

        return SystemCapabilitiesContext(
            context="\n\n".join(sections),
            capability_count=len(self._capabilities),
            capabilities=[capability.capability for capability in self._capabilities],
        )
