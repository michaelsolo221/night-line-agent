#!/usr/bin/env python3
"""Dialogflow CX Validation API check.

Zips the agent JSON package, restores it to a target agent,
then calls getValidationResult to check for semantic errors.

Requires:
  - GOOGLE_APPLICATION_CREDENTIALS or ADC configured
  - CX_API_PROJECT, CX_API_LOCATION, CX_API_AGENT_ID env vars
  - dialogflowcx pip package

Usage:
  pip install google-cloud-dialogflow-cx
  CX_API_PROJECT=superb-tendril-409615 \
  CX_API_LOCATION=us-central1 \
  CX_API_AGENT_ID=5c1fa4bf-24b8-4dc6-8de4-91da9aa7e165 \
    python3 scripts/validate-cx-api.py
"""

import json
import os
import sys
import tempfile
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def zip_agent(dest: Path) -> Path:
    """Create a zip of the agent JSON package at dest."""
    zip_path = dest / "agent.zip"
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        # agent.json at root
        agent = ROOT / "agent.json"
        if agent.exists():
            zf.write(agent, "agent.json")
        # All subdirectories
        for subdir in ("entityTypes", "flows", "intents", "testCases", "webhooks", "agentTransitionRouteGroups"):
            d = ROOT / subdir
            if d.is_dir():
                for f in d.rglob("*.json"):
                    zf.write(f, f.relative_to(ROOT))
    return zip_path


def main():
    project = os.environ.get("CX_API_PROJECT")
    location = os.environ.get("CX_API_LOCATION", "us-central1")
    agent_id = os.environ.get("CX_API_AGENT_ID")

    if not project or not agent_id:
        print("⏭  Skipping CX Validation API (CX_API_PROJECT / CX_API_AGENT_ID not set)")
        sys.exit(0)

    try:
        from google.cloud import dialogflowcx_v3 as dfcx
    except ImportError:
        print("⏭  Skipping CX Validation API (pip install google-cloud-dialogflow-cx)")
        sys.exit(0)

    agent_path = f"projects/{project}/locations/{location}/agents/{agent_id}"

    # Step 1: Zip and restore
    with tempfile.TemporaryDirectory() as tmp:
        zip_path = zip_agent(Path(tmp))
        print(f"📦 Zipped agent: {zip_path.stat().st_size} bytes")

        client = dfcx.AgentsClient()

        with open(zip_path, "rb") as f:
            agent_content = f.read()

        print("🔄 Restoring agent to validate...")
        restore_request = dfcx.RestoreAgentRequest(
            name=agent_path,
            agent_content=agent_content,
        )
        operation = client.restore_agent(request=restore_request)
        operation.result()  # blocks until done
        print("✅ Restore complete")

    # Step 2: Get validation result
    print("🔍 Fetching validation result...")
    result = client.get_agent_validation_result(
        name=f"{agent_path}/validationResult"
    )

    has_errors = False

    # Check agent-level errors
    for err in result.agent_validation_errors:
        print(f"  ❌ Agent error: {err.detail}")
        has_errors = True

    # Check flow-level errors
    for flow_result in result.flow_validation_results:
        flow_name = flow_result.flow.split("/")[-1]
        for err in flow_result.validation_messages:
            level = "❌" if err.severity == dfcx.ValidationMessage.Severity.ERROR else "⚠️"
            print(f"  {level} Flow [{flow_name}]: {err.detail}")
            if err.resource_type and err.resource:
                print(f"      resource: {err.resource_type} / {err.resource}")
            if err.resource_fields:
                for field_name, field_value in err.resource_fields.items():
                    print(f"      {field_name}: {field_value}")
            if err.severity == dfcx.ValidationMessage.Severity.ERROR:
                has_errors = True

    if has_errors:
        print("\n❌ Dialogflow CX validation found errors")
        sys.exit(1)

    print("✅ Dialogflow CX validation passed — no errors")


if __name__ == "__main__":
    main()
