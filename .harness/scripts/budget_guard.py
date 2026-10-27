#!/usr/bin/env python3
"""Track execution usage and enforce provider or local budget thresholds."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
HARNESS = ROOT / ".harness"
POLICY_PATH = HARNESS / "budgets" / "policy.json"
USAGE_PATH = HARNESS / "state" / "usage.json"


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def write_atomic(path: Path, data: dict) -> None:
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temp.replace(path)


def reservation_totals(usage: dict) -> dict:
    totals = {"input_tokens": 0, "output_tokens": 0, "estimated_cost_usd": 0.0}
    for item in usage.get("reservations", []):
        totals["input_tokens"] += int(item.get("input_tokens", 0))
        totals["output_tokens"] += int(item.get("output_tokens", 0))
        totals["estimated_cost_usd"] += float(item.get("estimated_cost_usd", 0.0))
    return totals


def execution_percent(policy: dict, usage: dict) -> tuple[float, dict]:
    limits = policy.get("execution_limits", {})
    reserved = reservation_totals(usage)
    values = {
        "input_tokens": int(usage.get("input_tokens", 0)) + reserved["input_tokens"],
        "output_tokens": int(usage.get("output_tokens", 0)) + reserved["output_tokens"],
        "estimated_cost_usd": float(usage.get("estimated_cost_usd", 0.0)) + reserved["estimated_cost_usd"],
    }
    ratios: dict[str, float] = {}
    for key, value in values.items():
        limit = limits.get(key)
        if limit is not None and float(limit) > 0:
            ratios[key] = 100.0 * float(value) / float(limit)
    return max(ratios.values(), default=0.0), {
        "including_reservations": values,
        "limits": limits,
        "percent_by_dimension": ratios,
    }


def authorization_applies(usage: dict, scope: str, percent: float) -> bool:
    authorization = usage.get("authorization")
    if not authorization:
        return False
    allowed_scope = authorization.get("scope")
    if allowed_scope not in {"run", scope}:
        return False
    return percent <= float(authorization.get("until_percent", 0.0))


def evaluate(policy: dict, usage: dict, scope: str, checkpoint: str | None) -> tuple[dict, int]:
    execution, details = execution_percent(policy, usage)
    provider = usage.get("provider_usage_percent")
    known = {"execution": execution}
    if provider is not None:
        known["provider"] = float(provider)
    effective = max(known.values(), default=0.0)
    source = max(known, key=known.get) if known else "unavailable"
    thresholds = policy["provider_thresholds"]
    warning = float(thresholds["warning_percent"])
    gate = float(thresholds["human_gate_percent"])
    hard_stop = float(thresholds["hard_stop_percent"])
    provider_unavailable = provider is None
    unavailable_behavior = policy.get("provider_usage_unavailable", "use-execution-budget")

    status = "continue"
    code = 0
    message = "orcamento dentro dos limites"
    if not policy.get("enabled", True):
        status = "disabled"
        message = "budget guard desativado"
    elif provider_unavailable and unavailable_behavior == "gate":
        status = "measurement-unavailable"
        message = "percentual do provedor indisponivel"
        code = 4
    elif effective >= hard_stop:
        status = "hard-stop"
        message = "hard stop de orcamento atingido"
        code = 3
    elif effective >= gate and not authorization_applies(usage, scope, effective):
        status = "human-gate"
        message = "decisao humana obrigatoria para continuar"
        code = 2
    elif effective >= gate:
        status = "authorized"
        message = "continuidade autorizada para este escopo"
    elif effective >= warning:
        status = "warning"
        message = "limite de aviso atingido; reduza paralelismo e reavalie o proximo checkpoint"

    payload = {
        "status": status,
        "message": message,
        "scope": scope,
        "checkpoint": checkpoint,
        "effective_percent": round(effective, 4),
        "effective_source": source,
        "provider_usage_percent": provider,
        "provider_usage_source": usage.get("provider_usage_source", "unavailable"),
        "execution_percent": round(execution, 4),
        "execution": details,
        "thresholds": thresholds,
        "authorization": usage.get("authorization"),
    }
    return payload, code


def print_payload(payload: dict) -> None:
    print(json.dumps(payload, ensure_ascii=False, indent=2))


def command_record(args: argparse.Namespace, usage: dict) -> int:
    if args.input_tokens < 0 or args.output_tokens < 0 or args.estimated_cost_usd < 0:
        raise ValueError("deltas de uso nao podem ser negativos")
    usage["input_tokens"] = int(usage.get("input_tokens", 0)) + args.input_tokens
    usage["output_tokens"] = int(usage.get("output_tokens", 0)) + args.output_tokens
    usage["estimated_cost_usd"] = round(
        float(usage.get("estimated_cost_usd", 0.0)) + args.estimated_cost_usd, 8
    )
    if args.provider_usage_unavailable:
        usage["provider_usage_percent"] = None
        usage["provider_usage_source"] = "unavailable"
        usage["provider_usage_checked_at"] = now()
    elif args.provider_usage_percent is not None:
        if not 0 <= args.provider_usage_percent <= 100:
            raise ValueError("provider usage percent deve estar entre 0 e 100")
        usage["provider_usage_percent"] = args.provider_usage_percent
        usage["provider_usage_source"] = args.source
        usage["provider_usage_checked_at"] = now()
    usage["updated_at"] = now()
    write_atomic(USAGE_PATH, usage)
    print("USAGE RECORDED")
    return 0


def command_reserve(args: argparse.Namespace, usage: dict) -> int:
    if args.input_tokens < 0 or args.output_tokens < 0 or args.estimated_cost_usd < 0:
        raise ValueError("reservas nao podem ser negativas")
    reservations = usage.setdefault("reservations", [])
    if any(item.get("id") == args.id for item in reservations):
        print(f"RESERVATION EXISTS: {args.id}")
        return 1
    reservations.append({
        "id": args.id,
        "scope": args.scope,
        "input_tokens": args.input_tokens,
        "output_tokens": args.output_tokens,
        "estimated_cost_usd": args.estimated_cost_usd,
        "created_at": now(),
    })
    usage["updated_at"] = now()
    write_atomic(USAGE_PATH, usage)
    print(f"RESERVED: {args.id}")
    return 0


def command_release(args: argparse.Namespace, usage: dict) -> int:
    before = len(usage.get("reservations", []))
    usage["reservations"] = [item for item in usage.get("reservations", []) if item.get("id") != args.id]
    if len(usage["reservations"]) == before:
        print(f"RESERVATION NOT FOUND: {args.id}")
        return 1
    usage["updated_at"] = now()
    write_atomic(USAGE_PATH, usage)
    print(f"RELEASED: {args.id}")
    return 0


def command_authorize(args: argparse.Namespace, policy: dict, usage: dict) -> int:
    hard_stop = float(policy["provider_thresholds"]["hard_stop_percent"])
    gate = float(policy["provider_thresholds"]["human_gate_percent"])
    if args.until_percent < gate:
        print(f"AUTHORIZATION REJECTED: until-percent deve ser pelo menos {gate}")
        return 1
    if args.until_percent >= hard_stop:
        print(f"AUTHORIZATION REJECTED: until-percent deve ser menor que {hard_stop}")
        return 1
    usage["authorization"] = {
        "scope": args.scope,
        "until_percent": args.until_percent,
        "reason": args.reason,
        "created_at": now(),
    }
    usage["updated_at"] = now()
    write_atomic(USAGE_PATH, usage)
    print("BUDGET AUTHORIZED")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    check = sub.add_parser("check")
    check.add_argument("--checkpoint")
    check.add_argument("--scope", choices=["feature", "wave", "run"], default="run")
    sub.add_parser("status")
    record = sub.add_parser("record")
    record.add_argument("--input-tokens", type=int, default=0)
    record.add_argument("--output-tokens", type=int, default=0)
    record.add_argument("--estimated-cost-usd", type=float, default=0.0)
    record.add_argument("--provider-usage-percent", type=float)
    record.add_argument("--provider-usage-unavailable", action="store_true")
    record.add_argument("--source", default="local-estimate")
    reserve = sub.add_parser("reserve")
    reserve.add_argument("--id", required=True)
    reserve.add_argument("--scope", choices=["feature", "wave", "run"], default="feature")
    reserve.add_argument("--input-tokens", type=int, default=0)
    reserve.add_argument("--output-tokens", type=int, default=0)
    reserve.add_argument("--estimated-cost-usd", type=float, default=0.0)
    release = sub.add_parser("release")
    release.add_argument("--id", required=True)
    authorize = sub.add_parser("authorize")
    authorize.add_argument("--scope", choices=["feature", "wave", "run"], required=True)
    authorize.add_argument("--until-percent", type=float, required=True)
    authorize.add_argument("--reason", required=True)
    sub.add_parser("clear-authorization")
    args = parser.parse_args()

    policy = load(POLICY_PATH)
    usage = load(USAGE_PATH)
    if args.command == "record":
        return command_record(args, usage)
    if args.command == "reserve":
        return command_reserve(args, usage)
    if args.command == "release":
        return command_release(args, usage)
    if args.command == "authorize":
        return command_authorize(args, policy, usage)
    if args.command == "clear-authorization":
        usage["authorization"] = None
        usage["updated_at"] = now()
        write_atomic(USAGE_PATH, usage)
        print("BUDGET AUTHORIZATION CLEARED")
        return 0
    payload, code = evaluate(
        policy,
        usage,
        getattr(args, "scope", "run"),
        getattr(args, "checkpoint", None),
    )
    print_payload(payload)
    return 0 if args.command == "status" else code


if __name__ == "__main__":
    raise SystemExit(main())
