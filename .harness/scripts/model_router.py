#!/usr/bin/env python3
"""Resolve model preferences without assuming a provider supports per-agent routing."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
ROUTING = ROOT / ".harness" / "models" / "routing.json"


def load() -> dict:
    return json.loads(ROUTING.read_text(encoding="utf-8"))


def validate(data: dict) -> list[str]:
    errors: list[str] = []
    tiers = data.get("tiers", {})
    routes = data.get("task_routes", {})
    providers = data.get("providers", {})
    if data.get("unavailable_behavior") not in {"inherit", "gate", "fail"}:
        errors.append("unavailable_behavior deve ser inherit, gate ou fail")
    for task, route in routes.items():
        tier = route.get("tier")
        if tier not in tiers:
            errors.append(f"{task}: tier desconhecido {tier}")
    for tier, settings in tiers.items():
        fallback = settings.get("fallback_tier")
        if fallback is not None and fallback not in tiers:
            errors.append(f"{tier}: fallback desconhecido {fallback}")
        visited = {tier}
        while fallback is not None and fallback in tiers:
            if fallback in visited:
                errors.append(f"{tier}: ciclo de fallback detectado")
                break
            visited.add(fallback)
            fallback = tiers[fallback].get("fallback_tier")
    for provider, mapping in providers.items():
        unknown = set(mapping) - set(tiers)
        if unknown:
            errors.append(f"{provider}: tiers desconhecidos {sorted(unknown)}")
    if data.get("default_provider") not in providers:
        errors.append("default_provider nao existe em providers")
    return errors


def resolve(data: dict, task: str, provider: str | None) -> tuple[dict, int]:
    routes = data["task_routes"]
    if task not in routes:
        return {"status": "error", "message": f"task desconhecida: {task}"}, 2
    provider = provider or data["default_provider"]
    if provider not in data["providers"]:
        return {"status": "error", "message": f"provider desconhecido: {provider}"}, 2
    route = routes[task]
    requested_tier = route["tier"]
    preferred = route.get("preferred_model")
    resolved_tier = requested_tier
    configured = data["providers"][provider].get(resolved_tier)
    while not configured:
        fallback = data["tiers"][resolved_tier].get("fallback_tier")
        if fallback is None:
            break
        resolved_tier = fallback
        configured = data["providers"][provider].get(resolved_tier)
    model = preferred or configured
    if model:
        return {
            "status": "resolved",
            "task": task,
            "provider": provider,
            "requested_tier": requested_tier,
            "resolved_tier": requested_tier if preferred else resolved_tier,
            "model": model,
            "source": "task" if preferred else "provider-tier",
        }, 0
    behavior = data.get("unavailable_behavior", "inherit")
    payload = {
        "status": "inherit" if behavior == "inherit" else "unavailable",
        "task": task,
        "provider": provider,
        "requested_tier": requested_tier,
        "resolved_tier": None,
        "model": None,
        "source": "platform-default",
        "message": "nenhum modelo exato configurado para a rota",
    }
    return payload, 0 if behavior == "inherit" else 3


def main() -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("validate")
    resolve_parser = sub.add_parser("resolve")
    resolve_parser.add_argument("--task", required=True)
    resolve_parser.add_argument("--provider")
    sub.add_parser("list")
    args = parser.parse_args()
    data = load()
    errors = validate(data)
    if errors:
        for error in errors:
            print(error, file=sys.stderr)
        return 1
    if args.command == "validate":
        print("MODEL ROUTING OK")
        return 0
    if args.command == "list":
        print(json.dumps(data["task_routes"], ensure_ascii=False, indent=2))
        return 0
    payload, code = resolve(data, args.task, args.provider)
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
