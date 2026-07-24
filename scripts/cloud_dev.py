#!/usr/bin/env python3
"""Drive step 9's Terraform (infra/terraform/) and step 7's `monolith`
Compose profile together, so "run the cloud order-service, then point a
local monolith at it" is one command instead of a manual multi-step dance.

Meant to be runnable by a human OR an agent -- every destructive/billed
action (apply, destroy) needs an explicit --yes, everything else is safe to
run blind. `status`/`plan` need no AWS write access at all.

Usage:
    python scripts/cloud_dev.py plan                # terraform init + plan (read-only)
    python scripts/cloud_dev.py apply --yes          # terraform init + apply -auto-approve
    python scripts/cloud_dev.py wire                 # write .env.cloud from terraform output
    python scripts/cloud_dev.py start                # docker compose --profile monolith up -d
    python scripts/cloud_dev.py all --yes             # apply + wire + start, in order
    python scripts/cloud_dev.py status                # terraform output (safe, read-only)
    python scripts/cloud_dev.py stop                  # docker compose --profile monolith down
    python scripts/cloud_dev.py destroy --yes          # terraform destroy

Requires: a real AWS Academy Learner Lab session exported to this shell
(AWS_ACCESS_KEY_ID / AWS_SECRET_ACCESS_KEY / AWS_SESSION_TOKEN) before
`apply`/`plan`/`destroy`/`status`. `wire`/`start`/`stop` don't touch AWS
directly but `wire` reads AWS creds from the environment to embed them into
.env.cloud (the local monolith's SQS client needs them -- it isn't running
under an EC2 instance profile).
"""
from __future__ import annotations

import argparse
import json
import os
import secrets
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
TF_DIR = REPO_ROOT / "infra" / "terraform"
TFVARS = TF_DIR / "terraform.tfvars"
TFVARS_EXAMPLE = TF_DIR / "terraform.tfvars.example"
ENV_CLOUD = REPO_ROOT / ".env.cloud"

AWS_ENV_VARS = ("AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY", "AWS_SESSION_TOKEN")


def run(cmd: list[str], cwd: Path, check: bool = True) -> subprocess.CompletedProcess:
    print(f"+ {' '.join(cmd)}  (cwd={cwd})")
    return subprocess.run(cmd, cwd=cwd, check=check)


def run_capture(cmd: list[str], cwd: Path) -> str:
    result = subprocess.run(cmd, cwd=cwd, check=True, capture_output=True, text=True)
    return result.stdout


def require_tfvars() -> None:
    if TFVARS.exists():
        return
    print(
        f"Missing {TFVARS}.\n"
        f"Copy {TFVARS_EXAMPLE.name} to {TFVARS.name} and fill in real values "
        "(my_ip, db_password, order_service_shared_secret, django_events_url) first.",
        file=sys.stderr,
    )
    sys.exit(1)


def require_aws_env() -> None:
    missing = [v for v in AWS_ENV_VARS if not os.environ.get(v)]
    if missing:
        print(
            "Missing AWS credentials in this shell: " + ", ".join(missing) + "\n"
            "Export your AWS Academy Learner Lab session's credentials first "
            "(AWS_SESSION_TOKEN included -- these are temporary STS creds).",
            file=sys.stderr,
        )
        sys.exit(1)


def cmd_plan(_args: argparse.Namespace) -> None:
    require_tfvars()
    require_aws_env()
    run(["terraform", "init"], cwd=TF_DIR)
    run(["terraform", "plan"], cwd=TF_DIR)


def cmd_apply(args: argparse.Namespace) -> None:
    require_tfvars()
    require_aws_env()
    run(["terraform", "init"], cwd=TF_DIR)
    if not args.yes:
        print(
            "This provisions real, billed AWS resources (RDS + SQS + EC2).\n"
            "Re-run with --yes to actually apply. Showing the plan instead:",
        )
        run(["terraform", "plan"], cwd=TF_DIR)
        return
    run(["terraform", "apply", "-auto-approve"], cwd=TF_DIR)


def cmd_status(_args: argparse.Namespace) -> None:
    require_aws_env()
    run(["terraform", "output"], cwd=TF_DIR)


def cmd_wire(_args: argparse.Namespace) -> None:
    """Write .env.cloud from terraform output + this shell's AWS creds."""
    require_aws_env()
    raw = run_capture(["terraform", "output", "-json"], cwd=TF_DIR)
    outputs = json.loads(raw)

    def val(name: str) -> str:
        try:
            return outputs[name]["value"]
        except KeyError:
            print(
                f"terraform output missing '{name}' -- has `apply` been run yet?",
                file=sys.stderr,
            )
            sys.exit(1)

    rds_endpoint = val("rds_endpoint")
    sqs_queue_url = val("sqs_queue_url")
    order_service_ip = val("order_service_public_ip")

    # Preserve an existing SECRET_KEY across re-runs instead of rotating it
    # every time `wire` is called.
    secret_key = None
    if ENV_CLOUD.exists():
        for line in ENV_CLOUD.read_text().splitlines():
            if line.startswith("SECRET_KEY="):
                existing = line.split("=", 1)[1]
                if existing:
                    secret_key = existing
    if not secret_key:
        secret_key = secrets.token_urlsafe(48)

    tfvars_lines = TFVARS.read_text().splitlines() if TFVARS.exists() else []
    tfvars = {}
    for line in tfvars_lines:
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        tfvars[k.strip()] = v.strip().strip('"')

    db_username = tfvars.get("db_username", "saleor")
    db_password = tfvars.get("db_password", "")
    shared_secret = tfvars.get("order_service_shared_secret", "")

    lines = [
        "# Generated by scripts/cloud_dev.py wire -- do not hand-edit, re-run instead.",
        f"SECRET_KEY={secret_key}",
        "DEBUG=False",
        "ALLOWED_HOSTS=localhost,127.0.0.1,host.docker.internal",
        "ALLOWED_CLIENT_HOSTS=localhost,127.0.0.1,host.docker.internal",
        # No real storefront domain for this lab run -- account-confirmation
        # emails would otherwise require ALLOWED_CLIENT_HOSTS to diverge from
        # the localhost default (see settings.py's ENABLE_ACCOUNT_CONFIRMATION_BY_EMAIL check).
        "ENABLE_ACCOUNT_CONFIRMATION_BY_EMAIL=False",
        "",
        f"DATABASE_URL=postgres://{db_username}:{db_password}@{rds_endpoint}/saleor",
        "CELERY_BROKER_URL=sqs://",
        f"AWS_ACCESS_KEY_ID={os.environ['AWS_ACCESS_KEY_ID']}",
        f"AWS_SECRET_ACCESS_KEY={os.environ['AWS_SECRET_ACCESS_KEY']}",
        f"AWS_SESSION_TOKEN={os.environ['AWS_SESSION_TOKEN']}",
        "AWS_DEFAULT_REGION=us-east-1",
        f"ORDER_SERVICE_URL=http://{order_service_ip}:8001",
        f"ORDER_SERVICE_SHARED_SECRET={shared_secret}",
        "",
        f"# SQS queue URL (reference, not consumed directly by Django): {sqs_queue_url}",
    ]
    ENV_CLOUD.write_text("\n".join(lines) + "\n")
    print(f"Wrote {ENV_CLOUD}")


def cmd_start(_args: argparse.Namespace) -> None:
    if not ENV_CLOUD.exists():
        print(f"Missing {ENV_CLOUD} -- run `wire` first.", file=sys.stderr)
        sys.exit(1)
    env = {**_env_passthrough(), "ENV_FILE": str(ENV_CLOUD)}
    print(f"+ docker compose --profile monolith up -d --build  (ENV_FILE={ENV_CLOUD})")
    subprocess.run(
        ["docker", "compose", "--profile", "monolith", "up", "-d", "--build"],
        cwd=REPO_ROOT,
        env=env,
        check=True,
    )


def cmd_stop(_args: argparse.Namespace) -> None:
    env = {**_env_passthrough(), "ENV_FILE": str(ENV_CLOUD)}
    subprocess.run(
        ["docker", "compose", "--profile", "monolith", "down"],
        cwd=REPO_ROOT,
        env=env,
        check=True,
    )


def cmd_destroy(args: argparse.Namespace) -> None:
    require_tfvars()
    require_aws_env()
    if not args.yes:
        print("Re-run with --yes to actually destroy. Showing the plan for destroy instead:")
        run(["terraform", "plan", "-destroy"], cwd=TF_DIR)
        return
    run(["terraform", "destroy", "-auto-approve"], cwd=TF_DIR)


def cmd_all(args: argparse.Namespace) -> None:
    cmd_apply(args)
    if not args.yes:
        return
    cmd_wire(args)
    cmd_start(args)


def _env_passthrough() -> dict:
    return dict(os.environ)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)

    for name, fn, needs_yes in [
        ("plan", cmd_plan, False),
        ("apply", cmd_apply, True),
        ("status", cmd_status, False),
        ("wire", cmd_wire, False),
        ("start", cmd_start, False),
        ("stop", cmd_stop, False),
        ("destroy", cmd_destroy, True),
        ("all", cmd_all, True),
    ]:
        p = sub.add_parser(name, help=fn.__doc__ or "")
        if needs_yes:
            p.add_argument(
                "--yes",
                action="store_true",
                help="actually run (skip the dry-run/plan-only default)",
            )
        p.set_defaults(func=fn, yes=False)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
