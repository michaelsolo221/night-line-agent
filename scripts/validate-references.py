#!/usr/bin/env python3
"""Cross-reference validation for Dialogflow CX agent JSON package files.

Checks that every display-name reference resolves to an existing resource:
  - agent.json startFlow → flows/<name>/
  - transitionRoutes[].intent → intents/<name>/<name>.json
  - transitionRoutes[].targetPage → pages/<name>.json (in same flow)
  - fulfillment.webhook → webhooks/<name>.json
  - eventHandlers[].targetPage → pages/<name>.json

Exit code 0 = pass, 1 = failures found.
"""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ERRORS: list[str] = []

# Collected display names
known_intents: set[str] = set()
known_pages: dict[str, str] = {}   # displayName → flow dir name
known_flows: set[str] = set()
known_webhooks: set[str] = set()

END_SESSION = "END_SESSION"


def err(ctx: str, msg: str):
    ERRORS.append(f"  {ctx}: {msg}")


def load_json(path: Path) -> dict | None:
    try:
        with open(path) as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return None


def collect_names():
    """Scan all JSON files and collect display names."""
    # Intents
    intents_dir = ROOT / "intents"
    if intents_dir.is_dir():
        for d in intents_dir.iterdir():
            if not d.is_dir():
                continue
            jf = d / f"{d.name}.json"
            data = load_json(jf)
            if data and "displayName" in data:
                known_intents.add(data["displayName"])

    # Flows and pages
    flows_dir = ROOT / "flows"
    if flows_dir.is_dir():
        for fd in flows_dir.iterdir():
            if not fd.is_dir():
                continue
            fj = fd / f"{fd.name}.json"
            data = load_json(fj)
            if data and "displayName" in data:
                known_flows.add(data["displayName"])
            pages_dir = fd / "pages"
            if pages_dir.is_dir():
                for pf in pages_dir.glob("*.json"):
                    pdata = load_json(pf)
                    if pdata and "displayName" in pdata:
                        known_pages[pdata["displayName"]] = fd.name

    # Webhooks
    wh_dir = ROOT / "webhooks"
    if wh_dir.is_dir():
        for f in wh_dir.glob("*.json"):
            data = load_json(f)
            if data and "displayName" in data:
                known_webhooks.add(data["displayName"])


def check_fulfillment(ctx: str, ful: dict | None):
    if not ful:
        return
    wh = ful.get("webhook")
    if wh and wh not in known_webhooks:
        err(ctx, f'webhook "{wh}" not found in webhooks/')


def validate_agent():
    p = ROOT / "agent.json"
    data = load_json(p)
    if not data:
        return
    sf = data.get("startFlow", "")
    if sf and sf not in known_flows:
        err("agent.json", f'startFlow "{sf}" — no flow with that displayName')


def validate_pages():
    flows_dir = ROOT / "flows"
    if not flows_dir.is_dir():
        return
    for flow_name in sorted(
        d.name for d in flows_dir.iterdir() if d.is_dir()
    ):
        pages_dir = flows_dir / flow_name / "pages"
        if not pages_dir.is_dir():
            continue
        for pf in sorted(pages_dir.glob("*.json")):
            rel = f"flows/{flow_name}/pages/{pf.name}"
            data = load_json(pf)
            if not data:
                continue

            # transitionRoutes
            for i, route in enumerate(data.get("transitionRoutes", [])):
                rctx = f"{rel} transitionRoutes[{i}]"
                intent = route.get("intent")
                if intent and intent not in known_intents:
                    err(rctx, f'intent "{intent}" not found in intents/')
                tp = route.get("targetPage")
                if tp and tp != END_SESSION and tp not in known_pages:
                    err(rctx, f'targetPage "{tp}" not found in any flow pages/')

            # entryFulfillment
            check_fulfillment(f"{rel}.entryFulfillment", data.get("entryFulfillment"))

            # eventHandlers
            for i, handler in enumerate(data.get("eventHandlers", [])):
                hctx = f"{rel} eventHandlers[{i}]"
                tp = handler.get("targetPage")
                if tp and tp != END_SESSION and tp not in known_pages:
                    err(hctx, f'targetPage "{tp}" not found')
                check_fulfillment(f"{hctx}.triggerFulfillment", handler.get("triggerFulfillment"))


def main():
    collect_names()
    validate_agent()
    validate_pages()

    if ERRORS:
        print(f"❌ {len(ERRORS)} cross-reference error(s):\n")
        for e in ERRORS:
            print(e)
        sys.exit(1)

    print("✅ All cross-references resolve correctly")


if __name__ == "__main__":
    main()
