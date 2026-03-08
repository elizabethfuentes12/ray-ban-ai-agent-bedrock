import json
import boto3
import os
import uuid
import urllib.parse
from agentcore_service import AgentCoreService

TABLE_NAME = os.environ.get("TABLE_NAME")
AGENT_ARN = os.environ.get("AGENT_ARN")
TEAM_ID = os.environ.get("TEAM_ID", "")
BUNDLE_ID = os.environ.get("BUNDLE_ID", "")

dynamodb = boto3.resource("dynamodb")
table = dynamodb.Table(TABLE_NAME)


def lambda_handler(event, context):
    method = event.get("httpMethod", "")
    path = event.get("path", "")

    # Apple App Site Association — required for Universal Links
    if "apple-app-site-association" in path:
        return _response(200, {
            "applinks": {
                "apps": [],
                "details": [{"appID": f"{TEAM_ID}.{BUNDLE_ID}", "paths": ["/*"]}]
            }
        })

    # GET / — Meta AI redirects here after registration, redirect to app via URL scheme
    if method == "GET":
        query = event.get("queryStringParameters") or {}
        params = urllib.parse.urlencode(query)
        redirect_url = f"metachatagent://callback?{params}"
        return {
            "statusCode": 302,
            "headers": {"Location": redirect_url},
            "body": "",
        }

    # POST /chat
    if method != "POST":
        return _response(405, {"error": "Method not allowed"})

    # Get authenticated user from Cognito
    request_context = event.get("requestContext", {})
    authorizer = request_context.get("authorizer", {})
    claims = authorizer.get("claims", {})

    # User ID from Cognito (sub = subject, unique user identifier)
    user_id = claims.get("sub", "unknown-user")
    user_email = claims.get("email", "no-email")

    print(f"Authenticated user: {user_id} ({user_email})")

    try:
        body = json.loads(event.get("body", "{}"))
    except (json.JSONDecodeError, TypeError):
        return _response(400, {"error": "Invalid JSON body"})

    prompt = body.get("prompt", "").strip()

    # Validate prompt size (prevent abuse)
    MAX_PROMPT_LENGTH = 4000
    if len(prompt) > MAX_PROMPT_LENGTH:
        return _response(400, {"error": f"Prompt too long. Max {MAX_PROMPT_LENGTH} characters"})

    if not prompt:
        return _response(400, {"error": "prompt required"})

    # session_id: unique per conversation, sent by the iOS app.
    # Same ID across messages in a conversation keeps context.
    # New ID when starting a fresh conversation.
    # Falls back to a UUID if not provided (stateless — no cross-message context).
    session_id = body.get("session_id") or str(uuid.uuid4())
    # Prefix ensures minimum length and traceability
    if not session_id.startswith("ioschat-"):
        session_id = f"ioschat-{user_id[:8]}-{session_id}"

    # Save to DynamoDB
    message_id = str(uuid.uuid4())
    table.put_item(Item={
        "id": message_id,
        "user_id": user_id,
        "user_email": user_email,
        "session_id": session_id,
        "prompt": prompt,
        "source": "ios_chat"
    })

    # Invoke AgentCore
    agentcore = AgentCoreService(AGENT_ARN)
    response_text = agentcore.invoke_agent(user_id, prompt, session_id)

    return _response(200, {"response": response_text, "message_id": message_id})


def _response(status_code, body):
    return {
        "statusCode": status_code,
        "headers": {"Content-Type": "application/json", "Access-Control-Allow-Origin": "*"},
        "body": json.dumps(body),
    }
