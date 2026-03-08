#!/usr/bin/env python3
"""
Post-deploy script for meta-agentcore-chat.

Usage:
    cd meta-agentcore-chat
    python update_ios_config.py -c team_id="YDH73YQ2RH" -c bundle_id="com.example.MetaChatAgent"

What it does:
    1. Stores API keys securely in SSM Parameter Store (SecureString)
    2. Runs `cdk deploy --outputs-file outputs.json` in the backend folder
    3. Reads the CDK outputs (ApiUrl, UserPoolId, AppClientId)
    4. Updates ios/MetaChatAgent/Services/AppConfig.swift

SSM keys stored:
    /metachat/tavily_api_key  — pass with -c tavily_api_key=xxx
    /metachat/github_pat      — pass with -c github_pat=xxx
"""

import json
import subprocess
import sys
import os
from pathlib import Path

# Ensure the script runs inside the backend venv
_venv = Path(__file__).parent / "backend" / ".venv"
if not sys.prefix.startswith(str(_venv)):
    print(f"ERROR: Activate the venv first:\n  source backend/.venv/bin/activate\n  python {Path(__file__).name}")
    sys.exit(1)

import boto3

BACKEND_DIR = Path(__file__).parent / "backend"
OUTPUTS_FILE = BACKEND_DIR / "outputs.json"
APP_CONFIG = Path(__file__).parent / "ios/MetaChatAgent/Services/AppConfig.swift"
STACK_NAME = "MetaChatAgentCoreStack"
REGION = "us-east-1"

# Map from CDK context key → SSM parameter path
SSM_PARAMS = {
    "tavily_api_key":    "/metachat/tavily_api_key",
    "github_pat":        "/metachat/github_pat",
    "anthropic_api_key": "/metachat/anthropic_api_key",
    "openai_api_key":    "/metachat/openai_api_key",   # optional, Anthropic takes priority
}


def run(cmd, cwd=None, check=True):
    print(f"  $ {' '.join(cmd)}")
    result = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
    if check and result.returncode != 0:
        print(f"  ERROR: {result.stderr.strip()}")
        sys.exit(1)
    return result.stdout.strip()


def store_ssm_secrets(extra_args):
    """Extract secret values from -c args and store them in SSM."""
    context = {}
    i = 0
    while i < len(extra_args):
        if extra_args[i] == "-c" and i + 1 < len(extra_args):
            key, _, value = extra_args[i + 1].partition("=")
            context[key] = value
            i += 2
        else:
            i += 1

    ssm = boto3.client("ssm", region_name=REGION)
    stored = []
    for key, path in SSM_PARAMS.items():
        if key in context and context[key]:
            ssm.put_parameter(
                Name=path,
                Value=context[key],
                Type="SecureString",
                Overwrite=True,
            )
            stored.append(f"  ✅ {path}")

    if stored:
        print("\n[0/4] Storing secrets in SSM Parameter Store (SecureString)...")
        for s in stored:
            print(s)

    # Return args without the secret values (they're now in SSM)
    clean_args = []
    i = 0
    while i < len(extra_args):
        if extra_args[i] == "-c" and i + 1 < len(extra_args):
            key, _, value = extra_args[i + 1].partition("=")
            if key not in SSM_PARAMS:
                clean_args += ["-c", extra_args[i + 1]]
            i += 2
        else:
            clean_args.append(extra_args[i])
            i += 1
    return clean_args


def deploy(extra_args):
    print("\n[1/4] Deploying CDK stack...")
    venv_bin = BACKEND_DIR / ".venv" / "bin"
    # CDK is a global npm tool; activate venv so `python app.py` uses the right packages
    activate = f"source {venv_bin}/activate"
    cdk_cmd = " ".join([
        "cdk", "deploy",
        f"--outputs-file {OUTPUTS_FILE}",
        "--require-approval never",
    ] + extra_args)
    result = subprocess.run(
        f"{activate} && {cdk_cmd}",
        shell=True,
        cwd=BACKEND_DIR,
        executable="/bin/zsh",
    )
    if result.returncode != 0:
        print("  ERROR: CDK deploy failed.")
        sys.exit(1)


def read_outputs():
    print("\n[2/4] Reading CDK outputs...")
    if not OUTPUTS_FILE.exists():
        print("  ERROR: outputs.json not found. Deploy failed?")
        sys.exit(1)

    with open(OUTPUTS_FILE) as f:
        data = json.load(f)

    stack_outputs = data.get(STACK_NAME, {})
    if not stack_outputs:
        print(f"  ERROR: No outputs found for stack '{STACK_NAME}'")
        print(f"  Available stacks: {list(data.keys())}")
        sys.exit(1)

    api_url = stack_outputs.get("ApiUrl", "").rstrip("/")
    user_pool_id = stack_outputs.get("UserPoolId", "")
    app_client_id = stack_outputs.get("AppClientId", "")

    print(f"  ApiUrl:      {api_url}")
    print(f"  UserPoolId:  {user_pool_id}")
    print(f"  AppClientId: {app_client_id}")

    return api_url, user_pool_id, app_client_id


def update_app_config(api_url, user_pool_id, app_client_id):
    print("\n[3/4] Updating AppConfig.swift...")

    content = f"""import Foundation

enum AppConfig {{
    static let apiBaseURL = "{api_url}"
    static let userPoolId = "{user_pool_id}"
    static let appClientId = "{app_client_id}"
    static let awsRegion = "{REGION}"

    static var chatURL: URL {{ URL(string: "\\(apiBaseURL)/chat")! }}
}}
"""
    APP_CONFIG.write_text(content)
    print(f"  Updated: {APP_CONFIG}")


def print_summary(api_url, user_pool_id, app_client_id):
    print("\n" + "="*60)
    print("  Deploy complete!")
    print("="*60)
    print(f"  API URL:      {api_url}")
    print(f"  UserPoolId:   {user_pool_id}")
    print(f"  AppClientId:  {app_client_id}")
    print()
    print("  Secrets stored in SSM (encrypted):")
    for path in SSM_PARAMS.values():
        print(f"    {path}")
    print("="*60 + "\n")


def main():
    extra_args = sys.argv[1:]

    skip_deploy = "--skip-deploy" in extra_args
    extra_args = [a for a in extra_args if a != "--skip-deploy"]

    # Always sync secrets to SSM (even on --skip-deploy)
    clean_args = store_ssm_secrets(extra_args)

    if not skip_deploy:
        deploy(clean_args)

    api_url, user_pool_id, app_client_id = read_outputs()
    update_app_config(api_url, user_pool_id, app_client_id)
    print_summary(api_url, user_pool_id, app_client_id)


if __name__ == "__main__":
    main()
