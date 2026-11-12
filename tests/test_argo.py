from pathlib import Path

import yaml


def test_workflow_is_a_four_step_dag():
    document = yaml.safe_load(Path("argo/workflow.yaml").read_text())
    tasks = document["spec"]["templates"][0]["dag"]["tasks"]
    names = [task["name"] for task in tasks]
    assert names == ["audit", "transform", "nowcast", "publish"]
    assert tasks[1]["depends"] == "audit"
    assert tasks[2]["depends"] == "transform"
    assert tasks[3]["depends"] == "nowcast"
    assert document["spec"]["templates"][1]["container"]["image"] == "living-cost-squeeze:local"
