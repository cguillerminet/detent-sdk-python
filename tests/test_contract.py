import dataclasses
import json
from pathlib import Path

from detent import models

SNAPSHOT = json.loads((Path(__file__).parent.parent / "openapi" / "detent.json").read_text())

# dataclass name -> OpenAPI component schema name
PAIRS = {
    "LimitResult": "LimitResponse",
    "AcquireResult": "AcquireResponse",
    "ReleaseResult": "ReleaseResponse",
    "StatsResult": "StatsResponse",
    "DayStat": "DayStat",
    "MonthSummary": "MonthSummary",
}


def test_dataclasses_cover_every_wire_field():
    schemas = SNAPSHOT["components"]["schemas"]
    for dc_name, schema_name in PAIRS.items():
        dc = getattr(models, dc_name)
        fields = {f.name for f in dataclasses.fields(dc)}
        props = set(schemas[schema_name]["properties"].keys())
        missing = props - fields
        assert not missing, f"{dc_name} is missing wire fields {missing} from {schema_name}"
