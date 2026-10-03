from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any


class SyntheticDataError(ValueError):
    pass


def load_json(path: Path) -> Any:
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def load_synthetic_data(data_dir: Path) -> dict[str, Any]:
    names = (
        "manifest",
        "customers",
        "orders",
        "shipments",
        "refunds",
        "policies",
        "intent_catalog",
    )
    data = {name: load_json(data_dir / f"{name}.json") for name in names}
    manifest = data["manifest"]
    if manifest.get("is_synthetic") is not True:
        raise SyntheticDataError("Synthetic-data manifest must set is_synthetic to true")
    for collection_name in ("customers", "orders", "shipments", "refunds", "policies"):
        for record in data[collection_name]:
            if record.get("is_synthetic") is not True:
                raise SyntheticDataError(f"{collection_name} contains a non-synthetic record")
    return deepcopy(data)
