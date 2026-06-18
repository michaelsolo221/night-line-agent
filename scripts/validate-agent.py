#!/usr/bin/env python3
"""Local schema validation for Dialogflow CX agent JSON package files.

Checks structure matches the real CX export format:
  - agent.json exists with required fields
  - webhook timeout is {"seconds": N} not a string
  - messages use {"text": {"text": [...]}} not {"outputAudioText": ...}
  - pages have "form": {} field
  - intents have "name" (UUID) field
  - training phrases have "repeatCount" and "languageCode"

Exit 0 = pass, 1 = failures.
"""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ERRORS: list[str] = []


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


def validate_agent_json():
    p = ROOT / "agent.json"
    if not p.exists():
        err("agent.json", "file missing")
        return
    data = load_json(p)
    if not data:
        return
    for field in ("displayName", "defaultLanguageCode", "timeZone", "startFlow"):
        if field not in data:
            err("agent.json", f"missing required field: {field}")
    # Check advancedSettings.dtmfSettings exists for phone agents
    dtmf = data.get("advancedSettings", {}).get("dtmfSettings", {})
    if not dtmf.get("enabled"):
        err("agent.json", "dtmfSettings.enabled should be true for phone agents")


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
        if "displayName" not in data:
            err(rel, "missing displayName")
        gws = data.get("genericWebService")
        if not gws:
            err(rel, "missing genericWebService")
            continue
        if "uri" not in gws:
            err(rel, "genericWebService.uri missing")
        elif not gws["uri"].startswith("https://"):
            err(rel, f"uri must use https: {gws['uri']}")
        # timeout must be {"seconds": N} object, not a string
        timeout = data.get("timeout")
        if timeout is not None:
            if isinstance(timeout, str):
                err(rel, f'timeout must be {{"seconds": N}} object, got string "{timeout}"')
            elif not isinstance(timeout, dict) or "seconds" not in timeout:
                err(rel, "timeout must have 'seconds' field")


def validate_messages(ctx: str, messages: list):
    """Validate message format matches CX export: {"text": {"text": [...]}}."""
    for i, msg in enumerate(messages):
        mctx = f"{ctx}.messages[{i}]"
        # Should have "text" key with nested "text" array, or "endInteraction"
        if "text" in msg:
            inner = msg["text"]
            if not isinstance(inner, dict) or "text" not in inner:
                err(mctx, 'text message must be {"text": {"text": ["..."]}}')
            elif not isinstance(inner["text"], list):
                err(mctx, "inner text must be an array")
        if "languageCode" not in msg and "endInteraction" not in msg:
            err(mctx, "missing languageCode")


def validate_fulfillment(ctx: str, ful: dict | None):
    if not ful:
        return
    wh = ful.get("webhook")
    if wh and not isinstance(wh, str):
        err(ctx, f"webhook must be string, got {type(wh).__name__}")
    if wh and not ful.get("tag"):
        err(ctx, "webhook specified but tag is missing")
    validate_messages(ctx, ful.get("messages", []))


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
        if "displayName" not in data:
            err(rel, "missing displayName")
        if "name" not in data:
            err(rel, "missing 'name' (UUID)")
        # Training phrases
        tp_dir = intent_dir / "trainingPhrases"
        if tp_dir.is_dir():
            for tp in tp_dir.glob("*.json"):
                tp_rel = str(tp.relative_to(ROOT))
                tp_data = load_json(tp)
                if not tp_data:
                    continue
                phrases = tp_data.get("trainingPhrases", [])
                for pi, phrase in enumerate(phrases):
                    if "repeatCount" not in phrase:
                        err(tp_rel, f"trainingPhrases[{pi}] missing repeatCount")
                    if "languageCode" not in phrase:
                        err(tp_rel, f"trainingPhrases[{pi}] missing languageCode")


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
        if not fdata:
            continue
        if "displayName" not in fdata:
            err(frel, "missing displayName")
        # Validate flow-level transition routes
        for i, route in enumerate(fdata.get("transitionRoutes", [])):
            rctx = f"{frel}.transitionRoutes[{i}]"
            if "intent" not in route:
                err(rctx, "missing 'intent'")
            # triggerFulfillment can be empty {}
            tf = route.get("triggerFulfillment")
            if tf and tf.get("messages"):
                validate_messages(rctx, tf["messages"])

        pages_dir = flow_dir / "pages"
        if not pages_dir.is_dir():
            continue
        for pf in sorted(pages_dir.glob("*.json")):
            prel = str(pf.relative_to(ROOT))
            pdata = load_json(pf)
            if not pdata:
                continue
            if "displayName" not in pdata:
                err(prel, "missing displayName")
            if "form" not in pdata:
                err(prel, "missing 'form' (should be empty {})")
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
