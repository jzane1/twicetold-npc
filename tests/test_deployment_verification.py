"""The restore check must reject missing data or a changed chain/vector/receipt."""

from copy import deepcopy

import pytest

from tests.verify_deployment import compare_snapshots


@pytest.mark.parametrize(
    "changed",
    [
        None,
        "memory_details",
        "memory_fact_versions",
        "observation_receipts",
        "embedding_space",
    ],
)
def test_restore_comparison(changed):
    source = {
        table: {"rows": 1, "sha256": "fixture"}
        for table in (
            "memories",
            "memory_details",
            "memory_fact_versions",
            "memory_gist_spans",
            "embedding_space",
            "schema_migrations",
            "observation_receipts",
        )
    }
    restored = deepcopy(source)
    if changed:
        restored[changed]["sha256"] = "different"
    assert compare_snapshots(source, restored)["passed"] == (changed is None)


def test_empty_restore_is_not_a_demonstration():
    assert not compare_snapshots({}, {})["passed"]
