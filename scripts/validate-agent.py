#!/usr/bin/env python3
"""Local schema validation for Dialogflow CX agent JSON package files.

Runs without GCP credentials. Checks:
  - agent.json exists and has required fields
  - Flow/page/intent/webhook directory structure matches spec
  - Fulfillment objects have correct types
  - Enum values use correct casing
  - No empty required strings

Exit code 0 = pass, 1 = failures found.
"""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ERRORS: list[str] = []

VALID_AUTH_ENUMS = {"ID_TOKEN", "ACCESS_TOKEN", "NONE", "SERVICE_AGENT_AUTH_UNSPECIFIED", ""}


def err(ctx: str, msg: str):
    ERRORS.append(f"  {ctx}: {msg}")


def load_json(path: Path) -> dict | None:
    rel = str(path.relative_to(ROOT))
    try:
        with open(path) as f:
            return json.load(f)
    except json.JSONDecodeError as e:
        err(rel, f"JSON parse error: {e}")
        return None


def require_fields(rel: str, data: dict, fields: list[str]):
    for f in fields:
        if f not in data:
            err(rel, f"missing required field: {f}")


def validate_fulfillment(ctx: str, ful: dict | None):
    if not ful:
        return
    wh = ful.get("webhook")
    if wh and not isinstance(wh, str):
        err(ctx, f"webhook must be a string display name, got {type(wh).__name__}")
    if wh and not ful.get("tag"):
        err(ctx, "webhook specified but tag is missing")
    for i, msg in enumerate(ful.get("messages", [])):
        oat = msg.get("outputAudioText")
        if oat is not None:
            if not isinstance(oat, dict):
                err(ctx, f"messages[{i}].outputAudioText must be object")
            elif "text" in oat and not isinstance(oat["text"], str):
                err(ctx, f"messages[{i}].outputAudioText.text must be string")
        ei = msg.get("endInteraction")
        if ei is not None and not isinstance(ei, dict):
            err(ctx, f"messages[{i}].endInteraction must be object")


def validate_agent_json():
    p = ROOT / "agent.json"
    if not p.exists():
        err("agent.json", "file missing — required at root of JSON package")
        return
    data = load_json(p)
    if not data:
        return
    require_fields("agent.json", data, ["displayName", "defaultLanguageCode", "timeZone"])
    sf = data.get("startFlow")
    if not sf:
        err("agent.json", "missing startFlow")
    elif not (ROOT / "flows" / sf).is_dir():
        err("agent.json", f"startFlow '{sf}' — no matching directory at flows/{sf}/")


def validate_webhooks():
    d = ROOT / "webhooks"
    if not d.is_dir():
        err("webhooks/", "directory missing")
        return
    for f in d.glob("*.json"):
        rel = str(f.relative_to(ROOT))
        data = load_json(f)
        if not data:
            continue
        require_fields(rel, data, ["displayName"])
        gws = data.get("genericWebService")
        if not gws:
            err(rel, "missing genericWebService object")
            continue
        if "uri" not in gws:
            err(rel, "genericWebService.uri missing")
        elif not gws["uri"].startswith("https://"):
            err(rel, f"uri must use https: {gws['uri']}")
        auth = gws.get("serviceAgentAuth", "")
        if auth not in VALID_AUTH_ENUMS:
            err(rel, f"invalid serviceAgentAuth: '{auth}' — expected one of {VALID_AUTH_ENUMS - {''}}")


def validate_intents():
    d = ROOT / "intents"
    if not d.is_dir():
        err("intents/", "directory missing")
        return
    for intent_dir in sorted(d.iterdir()):
        if not intent_dir.is_dir():
            continue
        name = intent_dir.name
        jf = intent_dir / f"{name}.json"
        rel = str(jf.relative_to(ROOT))
        if not jf.exists():
            err(str(intent_dir.relative_to(ROOT)), f"missing {name}.json")
            continue
        data = load_json(jf)
        if not data:
            continue
        require_fields(rel, data, ["displayName"])
        tp_dir = intent_dir / "trainingPhrases"
        if tp_dir.is_dir():
            for tp in tp_dir.glob("*.json"):
                tp_rel = str(tp.relative_to(ROOT))
                tp_data = load_json(tp)
                if tp_data and "trainingPhrases" not in tp_data:
                    err(tp_rel, "missing trainingPhrases key")


def validate_flows():
    d = ROOT / "flows"
    if not d.is_dir():
        err("flows/", "directory missing")
        return
    for flow_dir in sorted(d.iterdir()):
        if not flow_dir.is_dir():
            continue
        fname = flow_dir.name
        fj = flow_dir / f"{fname}.json"
        frel = str(fj.relative_to(ROOT))
        if not fj.exists():
            err(str(flow_dir.relative_to(ROOT)), f"missing {fname}.json")
            continue
        fdata = load_json(fj)
        if fdata and "displayName" not in fdata:
            err(frel, "missing displayName")

        pages_dir = flow_dir / "pages"
        if not pages_dir.is_dir():
            continue
        for pf in sorted(pages_dir.glob("*.json")):
            prel = str(pf.relative_to(ROOT))
            pdata = load_json(pf)
            if not pdata:
                continue
            require_fields(prel, pdata, ["displayName"])
            validate_fulfillment(f"{prel}.entryFulfillment", pdata.get("entryFulfillment"))
            for i, route in enumerate(pdata.get("transitionRoutes", [])):
                rctx = f"{prel}.transitionRoutes[{i}]"
                if "intent" not in route and "condition" not in route:
                    err(rctx, "needs 'intent' or 'condition'")
            for i, handler in enumerate(pdata.get("eventHandlers", [])):
                hctx = f"{prel}.eventHandlers[{i}]"
                if "event" not in handler:
                    err(hctx, "missing 'event'")
                validate_fulfillment(f"{hctx}.triggerFulfillment", handler.get("triggerFulfillment"))


def main():
    validate_agent_json()
    validate_webhooks()
    validate_intents()
    validate_flows()

    if ERRORS:
        print(f"❌ {len(ERRORS)} schema error(s):\n")
        for e in ERRORS:
            print(e)
        sys.exit(1)

    print("✅ Local schema validation passed")


if __name__ == "__main__":
    main()
