# 💬 Meta AgentCore Chat

[![AWS CDK](https://img.shields.io/badge/AWS_CDK-2.241.0-orange.svg?style=for-the-badge&logo=amazon-aws)](https://aws.amazon.com/cdk/)
[![Swift](https://img.shields.io/badge/Swift-5.9-FA7343.svg?style=for-the-badge&logo=swift)](https://swift.org)
[![Strands](https://img.shields.io/badge/🧬-Strands_Agents-blue.svg?style=for-the-badge)](https://strandsagents.com)
[![AgentCore](https://img.shields.io/badge/Amazon-Bedrock_AgentCore-orange.svg?style=for-the-badge&logo=amazon-aws)](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/what-is-bedrock-agentcore.html)

*Conversational AI assistant powered by [Amazon Bedrock AgentCore](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/what-is-bedrock-agentcore.html) with **Meta Ray-Ban smart glasses integration** and powerful tools: web search, browser automation, math, and reasoning.*

---

## 🎯 What This Does

Chat with an AI agent using **Meta Ray-Ban glasses** via voice commands, or use the iOS keyboard. The agent has access to 6 powerful tools to help you.

### Voice Flow with Glasses

```
"Hey Penelope" → 🔊 "Ready" → "search the web for AWS news" → 🤖 agent uses tavily → 🔊 speaks response → loop
```

**Hands-free.** No need to touch your phone.

---

## 🏗️ Architecture

```
Meta Ray-Ban Glasses / iOS Keyboard
    ↕ Bluetooth (via Meta AI app) / Direct input
iOS App (SwiftUI)
    ↕ HTTPS + Cognito JWT token
API Gateway (+ Cognito Authorizer)
    ↓
Lambda → MetaChatAgent Runtime → Bedrock (chat_agent.py)
    ↓              ↓                       ↓
DynamoDB    AgentCore Memory        7 Tools: calculator, current_time,
(messages)  (facts + prefs)         think, tavily, http_request, browser,
                                    save_to_obsidian → S3 (direct write)
```

---

## 🛠️ Agent Tools

| 🔧 Tool | 🎯 What It Does | 📋 Example |
|---------|-----------------|------------|
| **calculator** | Math, unit conversions, numerical computations | "What's 15% tip on $84.50?" |
| **current_time** | Current date and time | "What day is it today?" |
| **think** | Deep reasoning, multi-step problem solving | "Compare pros and cons of X vs Y" |
| **tavily** | Web search for current events, facts, news | "What's the latest news about AWS?" |
| **http_request** | Call public APIs directly | "Get the current Bitcoin price" |
| **browser** | Navigate and interact with real websites | "Go to example.com and check pricing" |

> 💡 The agent prefers `tavily` for quick web lookups and only uses `browser` when real page interaction is needed.

---

## 📦 Components

| Component | Path | Description |
|-----------|------|-------------|
| **Backend** | `backend/` | CDK stack: API Gateway (Cognito auth) + Lambda + AgentCore Runtime + DynamoDB + Cognito + Memory |
| **iOS App** | `ios/` | SwiftUI app with Meta Glasses integration, Cognito auth, voice commands |
| **Agent** | `backend/agent_files/chat_agent.py` | Strands agent with 6 tools, long-term memory, configurable model |
| **Memory** | `backend/memory/` | AgentCore Memory Store: semantic facts + user preferences (90-day retention) |
| **Deploy script** | `update_ios_config.py` | Deploys CDK and updates `AppConfig.swift` automatically |

---

## 🚀 Setup Guide

### Prerequisites

- **AWS CLI** configured with appropriate permissions
- **Python 3.10+** and **AWS CDK** installed
- **Xcode 15+** on a Mac (for iOS app)
- **iPhone** with iOS 17+ and USB cable
- **Meta Ray-Ban glasses** paired with Meta AI app on your iPhone
- **Tavily API key** from [tavily.com](https://tavily.com) (for web search)
- **Apple ID** (free is fine for testing)

---

### Step 1: Get your Apple Team ID

You need this before registering with Meta.

1. Open Xcode → **Settings** (Cmd+,) → **Accounts** tab
2. Click **+** button → select **Apple ID** → sign in
3. Click on your account name → your **Team ID** appears on the right (e.g. `YDH73YQ2RH`)
4. Click **Manage Certificates** → click **+** → select **Apple Development** → Done

> 💡 The Team ID is a 10-character alphanumeric string. Write it down — you'll need it later.

---

### Step 2: Deploy the backend and configure iOS automatically

From the `meta-agentcore-chat/` folder:

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cd ..
```

Activate the venv and run the deploy script — it stores secrets in SSM, deploys the CDK stack, and updates `AppConfig.swift` automatically:

```bash
source backend/.venv/bin/activate

python update_ios_config.py \
  -c tavily_api_key="YOUR_TAVILY_KEY" \
  -c github_pat="YOUR_GITHUB_PAT" \
  -c team_id="YOUR_TEAM_ID" \
  -c bundle_id="com.example.MetaChatAgent" \
  -c obsidian_bucket="YOUR_S3_BUCKET"
```

The script:
1. Stores `tavily_api_key` and `github_pat` as **SSM SecureString** (encrypted, never in CloudFormation)
2. Runs `cdk deploy` using the local venv
3. Reads the CDK outputs (`ApiUrl`, `UserPoolId`, `AppClientId`)
4. Updates `ios/MetaChatAgent/Services/AppConfig.swift`

> If you already deployed and just want to update secrets or iOS config:
> ```bash
> source backend/.venv/bin/activate
> python update_ios_config.py --skip-deploy -c tavily_api_key="NEW_KEY"
> ```

**Note the `UniversalLinkDomain` output** — you'll need it in Step 3:
```
<id>.execute-api.us-east-1.amazonaws.com
```

---

### Step 3: Register on Meta Wearables Developer Center

This is required so Meta AI knows your app is authorized to access the glasses.

> ⚠️ **Important**: Use the **same Meta account** as the Meta AI app on your phone.

1. Go to [wearables.developer.meta.com](https://wearables.developer.meta.com/) and sign in
2. Create an **organization** if you don't have one:
   - Follow the [onboarding guide](https://wearables.developer.meta.com/docs/onboarding-and-organization-management)
3. Click **New Project** and fill in:
   - **Project name**: e.g. "Meta Chat Agent"
   - **Description**: e.g. "AI chat agent with voice control"
4. Go to **App Configuration** and fill in:
   - **Bundle ID**: `com.example.MetaChatAgent` (or your own unique ID)
   - **Team ID**: your Apple Team ID from Step 1
   - **Universal Link**: Use the `UniversalLinkDomain` output from Step 2, formatted as:
     ```
     https://<UniversalLinkDomain>/prod/?metaWearablesAction=register
     ```
     Example: `https://<Resource-ID>.execute-api.<YOUR-REGION>.amazonaws.com/prod/?metaWearablesAction=register`
5. Go to **Permissions** tab → request **Microphone** access (not Camera) → paste justification:
   > This app uses voice commands through Meta Ray-Ban glasses to interact with an AI chat agent. The microphone is used for wake word detection and voice input. No photos are captured.
6. Go to **Release Channels** → create a new channel → add yourself as a tester
7. **Note these values** (you'll need them in Step 5):
   - **Meta App ID** (also called Application ID)
   - **Client Token**

For details see [Meta project management guide](https://wearables.developer.meta.com/docs/manage-projects).

---

### Step 4: Update backend with Meta configuration

Now that you have your Team ID and Bundle ID from Meta Developer Center, redeploy with those values using the same script:

```bash
source backend/.venv/bin/activate

python update_ios_config.py \
  -c tavily_api_key="YOUR_TAVILY_KEY" \
  -c github_pat="YOUR_GITHUB_PAT" \
  -c team_id="YOUR_TEAM_ID" \
  -c bundle_id="com.example.MetaChatAgent" \
  -c obsidian_bucket="YOUR_S3_BUCKET"
```

This updates secrets in SSM, redeploys, and refreshes `AppConfig.swift`.

Verify the AASA file:

```bash
curl https://<UniversalLinkDomain>/prod/.well-known/apple-app-site-association
```

Should return JSON with your Team ID and Bundle ID.

---

### Step 5: Enable Developer Mode in Meta AI app

This allows Meta AI to work with third-party apps.

1. Open the **Meta AI** app on your iPhone
2. Go to **Settings** (gear icon) → **App Info**
3. **Tap the version number 5 times** — a Developer Mode toggle appears
4. Toggle **Developer Mode → ON** → tap **Enable**

---

### Step 6: Configure the iOS app

#### 6a. API + Cognito config (already done automatically by `update_ios_config.py`)

The script in Step 2 already updated `AppConfig.swift` with `apiBaseURL`, `userPoolId`, and `appClientId`. No manual edit needed.

#### 6b. Set the Meta credentials

Edit `ios/MetaChatAgent/Info.plist` (or use Xcode UI in Step 6):

| Key (under `MWDAT`) | Value | Where to find it |
|-----|-------|-------------------|
| `MetaAppID` | Your Meta App ID | Meta Developer Center → your project (Step 3) |
| `ClientToken` | Your Client Token | Meta Developer Center → your project (Step 3) |
| `TeamID` | Your Apple Team ID | From Step 1 (e.g. `YDH73YQ2RH`) |
| `AppLinkURLScheme` | `metachatagent://` | Already set — don't change |

---

### Step 7: Add Meta SDK dependencies in Xcode

1. Open the project:
   ```bash
   cd ios
   open MetaChatAgent.xcodeproj
   ```

2. **Add Swift Package Dependencies:**
   - In Xcode, click the **blue project icon** (top of left panel)
   - Select the **MetaChatAgent** project (not target)
   - Click **Package Dependencies** tab
   - Click **+** button
   - Enter: `https://github.com/facebook/meta-wearables-dat-ios`
   - Click **Add Package**
   - Select **MWDATCore** and **MWDATCamera**
   - Click **Add Package**

3. **Add new files to target** (if not already showing a checkmark):
   - In left panel, find these files:
     - `ViewModels/WearablesViewModel.swift`
     - `ViewModels/StreamViewModel.swift`
     - `Services/VoiceCommandService.swift`
     - `Services/CognitoAuthService.swift`
     - `Services/SpeechService.swift`
     - `Views/MainView.swift`
     - `Views/AgentView.swift`
     - `Views/AuthView.swift`
   - For each file, click it → in right panel → **Target Membership** → check ✅ **MetaChatAgent**

4. **Configure Signing:**
   - Select **MetaChatAgent** target (under TARGETS)
   - Go to **Signing & Capabilities** tab
   - Check ✅ **Automatically manage signing**
   - **Team**: select your Apple ID
   - **Bundle Identifier**: set to the **same Bundle ID** you registered in Meta Developer Center (Step 3)

5. **Enable Background Audio** (required for hands-free with screen off):
   - Still in **Signing & Capabilities** tab
   - Click **+ Capability** → select **Background Modes**
   - Check ✅ **Audio, AirPlay, and Picture in Picture**

6. **Edit Info.plist values (optional, if not done in Step 6b):**
   - Click **Info** tab
   - Expand **MWDAT**
   - Set `MetaAppID`, `ClientToken`, `TeamID`

---

### Step 8: Enable Developer Mode on iPhone

1. On your iPhone: **Settings → Privacy & Security → Developer Mode → ON**
2. iPhone will restart — this is normal
3. After restart, confirm when prompted

---

### Step 9: Build and run

1. Connect your iPhone via USB → tap **Trust** when prompted
2. In Xcode, select your iPhone as target (NOT "My Mac")
3. Press **Cmd+R** to build and run
4. If you see **"Untrusted Developer"** on iPhone:
   - iPhone → **Settings → General → VPN & Device Management** → tap your email → **Trust**
5. The app opens with a **login screen** — create an account with your email
6. Check your email for the **verification code** and enter it in the app
7. Sign in and proceed to connect your glasses

---

### Step 10: Use the app

1. Open **MetaChatAgent** on your iPhone
2. Tap **Connect Glasses** → Meta AI app opens → **authorize** → redirected back
3. The app now listens for the wake word **"Hey Penelope"**

#### Voice commands (with glasses):

```
👉 Say: "Hey Penelope"
   → You hear: "Ready" through the glasses speakers
   → Ask your question (you have ~6 seconds before it times out)

👉 Ask: "What is 2 + 2?"
   → Agent responds through glasses speakers (2-3 sentences max)

👉 Ask: "Search the web for AWS news"
   → Agent uses tavily, responds with latest news

👉 Ask: "Calculate 15% tip on $84.50"
   → Agent uses calculator, responds with result
```

**Voice behavior:**
- If you say "Hey Penelope" and stay silent for 6 seconds → automatically returns to listening mode
- After the agent responds, it waits for your next "Hey Penelope"
- Works with the screen off (requires Background Audio capability in Step 7)

#### Keyboard (without saying "Hey Penelope"):

Use the text field at the bottom to type questions directly.

---

## 🔧 Adding Your Own Tools

The agent is extensible — you can add any capability as a `@tool` in `backend/agent_files/chat_agent.py`.

### Pattern

```python
from strands import tool

@tool
def my_tool(param: str) -> str:
    """
    One-line description of what this tool does.

    Call this when the user asks about [specific trigger phrases or scenarios].

    Args:
        param: Description of what this parameter is.

    Returns:
        What the tool returns and in what format.
    """
    # implementation
    return result
```

Then add it to the tools list in `get_or_create_agent()`:

```python
tools = [calculator, current_time, ..., my_tool]
```

And mention it in the system prompt so the agent knows when to use it:

```python
"- my_tool: when the user asks about [X]"
```

### If your tool needs an API key

Store it in SSM, never hardcode it:

```bash
# Add to SSM
python update_ios_config.py --skip-deploy -c my_api_key="YOUR_KEY"
```

Add the SSM path as an env var in the stack (`meta_agentcore_chat_stack.py`):

```python
"SSM_MY_API_KEY": "/metachat/my_api_key",
```

Read it at agent cold start in `chat_agent.py`:

```python
MY_API_KEY = _get_secret(os.getenv("SSM_MY_API_KEY", ""))
```

### After adding a tool

Rebuild the deployment package and redeploy:

```bash
source backend/.venv/bin/activate
bash backend/create_deployment_package.sh
python update_ios_config.py -c team_id="..." -c bundle_id="..."
```

> See: [Strands Agents — Tools documentation](https://strandsagents.com/latest/documentation/docs/user-guide/concepts/tools/python-tool/)

---

## ⚙️ Configuration

| Variable | Where | Default | Description |
|----------|-------|---------|-------------|
| `MODEL_ID` | CDK context | `anthropic.claude-3-haiku-20240307-v1:0` | Bedrock model — **change if using a different Bedrock model** (ignored when Anthropic/OpenAI key is set) |
| `TAVILY_API_KEY` | SSM SecureString | *(required)* | Tavily web search API key |
| `BEDROCK_AGENTCORE_MEMORY_ID` | AgentCore env var | Set automatically by CDK | AgentCore Memory Store ID |
| `OBSIDIAN_BUCKET` | CDK context | `your-s3-bucket-name` | S3 bucket name for Obsidian vault |
| `personal_account_role_arn` | CDK context | *(optional)* | Cross-account IAM role ARN if bucket is in a different AWS account |

### Model provider

Priority: **Anthropic → OpenAI → Bedrock (default)**. Switch without redeploying:

```bash
source backend/.venv/bin/activate

# Activate Anthropic (claude-opus-4-6)
python update_ios_config.py --skip-deploy -c anthropic_api_key="sk-ant-..."

# Activate OpenAI (gpt-4o)
python update_ios_config.py --skip-deploy -c openai_api_key="sk-..."

# Back to Bedrock: remove the key from SSM Parameter Store console
```

Change at deploy time:

```bash
python update_ios_config.py \
  -c model_id="us.anthropic.claude-3-5-haiku-20241022-v1:0" \
  -c tavily_api_key="tvly-xxx"
```

---

## 📓 Obsidian Integration

The agent can save ideas directly to your personal [Obsidian](https://obsidian.md/) vault stored in S3. The `MetaChatAgent` LLM structures the raw idea (title, summary, problem, solution, next steps) and writes the Markdown note directly to S3 — single LLM call, minimal latency.

### Voice usage

```
👉 Say: "Hey Penelope — save this idea: build an AI podcast summarizer"
   → Agent structures: title, summary, problem, solution, next steps
   → Writes Markdown note to s3://your-bucket/Ideas/2025-03-08 AI Podcast Summarizer.md
   → You hear: "Saved: AI Podcast Summarizer"
```

### S3 bucket setup

**Option A — Bucket in the same AWS account (default, simplest)**

The agent's execution role (`AmazonS3FullAccess`) can write directly. Just set the bucket name:

```bash
python update_ios_config.py -c obsidian_bucket="your-bucket-name" ...
```

**Option B — Bucket in a different AWS account (cross-account)**

If your Obsidian S3 bucket lives in a separate AWS account, create a cross-account IAM role in that account following least-privilege principles:

**Step 1 — Get the AgentCore execution role ARN** (from the deployment account):
```bash
aws cloudformation describe-stack-resources \
  --stack-name MetaChatAgentCoreStack \
  --query "StackResources[?contains(LogicalResourceId,'AgentCoreExecutionRole')].PhysicalResourceId" \
  --output text | xargs aws iam get-role --role-name --query 'Role.Arn' --output text
```

**Step 2 — Create an IAM role in your personal account** with:

*Trust policy* — only the specific execution role can assume it, with ExternalId to prevent [confused deputy attacks](https://docs.aws.amazon.com/IAM/latest/UserGuide/confused-deputy.html):
```json
{
  "Version": "2012-10-17",
  "Statement": [{
    "Effect": "Allow",
    "Principal": { "AWS": "<AgentCoreExecutionRoleArn>" },
    "Action": "sts:AssumeRole",
    "Condition": { "StringEquals": { "sts:ExternalId": "metachat-obsidian-access" } }
  }]
}
```

*Permissions policy* — minimum required, write-only:
```json
{
  "Version": "2012-10-17",
  "Statement": [{
    "Effect": "Allow",
    "Action": "s3:PutObject",
    "Resource": "arn:aws:s3:::your-bucket-name/*"
  }]
}
```

**Step 3 — Redeploy** with the role ARN:
```bash
source backend/.venv/bin/activate
python update_ios_config.py \
  -c obsidian_bucket="your-bucket-name" \
  -c personal_account_role_arn="arn:aws:iam::ACCOUNT_ID:role/ObsidianVaultWriterRole" \
  -c team_id="..." -c bundle_id="..."
```

> **Runtime vs Gateway**: This integration uses an [AgentCore **Runtime**](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/runtime-get-started.html) (not a [Gateway](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/gateway.html)) because it needs LLM reasoning to infer structure from raw idea text. An [AgentCore Gateway](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/gateway.html) is a proxy that exposes existing APIs as tools without reasoning.

---

## 🧠 Memory Architecture — STM and LTM

This agent uses two layers of memory, following best practices for conversational AI systems:

### Short-Term Memory (STM) — Conversation Context

**What it is:** The context of the current conversation — what was said in THIS session.

**How it works:** Managed by the [AgentCore Runtime `runtimeSessionId`](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/runtime-sessions.html). All messages sharing the same `sessionId` maintain conversation context. The agent remembers "the second movie" if it was mentioned earlier in the same session.

**Lifecycle:**
- A new `sessionId` (UUID) is generated each time the glasses connect to the iOS app
- All voice interactions within that connection use the same `sessionId`
- When the glasses disconnect, the session ends — context is cleared
- Reconnecting starts a fresh conversation

```
Glasses connect → sessionId = "ioschat-a1b2c3d4-uuid..."
  "Hey Penelope, what movies are in Miami?" ──┐
  "Hey Penelope, what time is the second one?" ──┘ Same session, agent remembers
Glasses disconnect → session ends
Glasses reconnect → new sessionId → fresh conversation ✅
```

> See: [AgentCore Runtime Sessions](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/runtime-sessions.html)

### Long-Term Memory (LTM) — Persistent User Knowledge

**What it is:** Facts and preferences about the user that persist across all sessions indefinitely.

**How it works:** Powered by [AgentCore Memory Store](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/memory.html), keyed by the user's `actorId` (derived from their Cognito identity). The agent automatically reads and writes LTM without explicit user action.

| Memory Type | Namespace | What it stores |
|-------------|-----------|----------------|
| **Semantic** | `/users/{actorId}/facts` | Facts the user shares — "I live in Miami", "I work at AWS" |
| **User Preference** | `/users/{actorId}/preferences` | Learned preferences — "prefers short answers", "speaks Spanish" |

**Lifecycle:** 90-day retention. Survives disconnections, app restarts, and new conversations.

```
Session 1: "I'm a software engineer in Miami"
  → LTM stores: {fact: "software engineer", location: "Miami"}

Session 2 (next day, new sessionId):
  "Hey Penelope, what tech meetups are near me?"
  → Agent reads LTM → knows user is in Miami → gives relevant answer ✅
```

> See: [AgentCore Memory](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/memory.html) · [actorId and runtimeSessionId](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/runtime-sessions.html)

### Session and Identity Parameters

| Parameter | Value | Type | Purpose |
|-----------|-------|------|---------|
| `actorId` | `ioschat:{cognitoSub}` | Stable per user | LTM identity — same across all sessions |
| `runtimeSessionId` | `ioschat-{userId[:8]}-{uuid}` | Unique per conversation | STM isolation — reused within one glasses connection |

---

## 🔐 Authentication

The iOS app uses **AWS Cognito** for secure authentication:

1. User creates an account with email + password (verified by email code)
2. On sign in, Cognito returns a JWT `IdToken` (valid 1 hour)
3. Every API request sends `Authorization: <IdToken>` — API Gateway validates it automatically
4. Tokens stored in **iOS Keychain** (not UserDefaults)
5. `RefreshToken` (30 days) renews the session automatically in the background

---

## 🔑 Session & Identity

The iOS app sends `device_id` (`UIDevice.identifierForVendor`) to the backend, which builds:

| Parameter | Value | Purpose |
|-----------|-------|---------|
| `actorId` | `ioschat::{device_id}` | User identity for AgentCore Memory |
| `runtimeSessionId` | `ioschat-session-device-{device_id}` | Session isolation (microVM per device) |

---

## 🔍 Troubleshooting

| Problem | Solution |
|---------|----------|
| Agent returns "No response" | Check `AgentRuntimeArn` in Lambda env vars matches CDK output |
| Agent doesn't remember previous conversations | Verify `BEDROCK_AGENTCORE_MEMORY_ID` is set in AgentCore Runtime env vars (set automatically by CDK) |
| "Obsidian vault is not configured" | Verify `OBSIDIAN_BUCKET` is set — redeploy with `-c obsidian_bucket=your-bucket` |
| Obsidian save fails with S3 access error | Ensure AgentCore execution role has `s3:PutObject` on the bucket. For cross-account: set `personal_account_role_arn` |
| Tavily search fails | Verify `TAVILY_API_KEY` is set: `python update_ios_config.py -c tavily_api_key=...` |
| Browser tool slow | Expected — launches managed Chrome. Use `tavily` for quick searches |
| iOS app "API request failed" | Run `python update_ios_config.py --skip-deploy` to refresh `AppConfig.swift` |
| Login fails with "Authentication error" | Check `userPoolId` and `appClientId` in `AppConfig.swift` match CDK outputs |
| "Session expired" error | Sign out and sign back in |
| "Connect Glasses" opens Meta AI but nothing happens | Check Meta App ID, Client Token in Info.plist. Verify Developer Mode ON in Meta AI |
| "No such module 'MWDATCore'" | Add Swift Package as in Step 7 |
| Build fails with signing error | Step 1: create Apple Development certificate |
| "Untrusted Developer" on iPhone | Settings → General → VPN & Device Management → Trust |
| iPhone not showing in Xcode | Unplug/replug USB, tap "Trust" again |
| Wake word not working | Check microphone permissions in iPhone Settings |
| "Hey Penelope" works once then stops | Enable Background Audio in Xcode: Signing & Capabilities → Background Modes → ✅ Audio |
| No sound when saying "Hey Penelope" | "Ready" plays through glasses via BT HFP — ensure glasses are connected |
| Glasses say "You are not registered" | Open the app and sign in with your account |
| Wake word times out immediately | Say your question within 6 seconds of "Ready" |

---

## 🧪 Testing Without iOS

Get a Cognito token first, then call the API:

```bash
# 1. Get a Cognito token (use the AppClientId and UserPoolId from CDK outputs)
TOKEN=$(aws cognito-idp initiate-auth \
  --auth-flow USER_PASSWORD_AUTH \
  --auth-parameters USERNAME=your@email.com,PASSWORD=yourpassword \
  --client-id <AppClientId> \
  --region us-east-1 \
  --query 'AuthenticationResult.IdToken' \
  --output text)

# 2. Call the API (use the ApiUrl from CDK outputs)
curl -X POST "<ApiUrl>/chat" \
  -H "Content-Type: application/json" \
  -H "Authorization: $TOKEN" \
  -d '{"prompt": "What is 2+2?", "device_id": "test-device-001"}'
```

---

## 📖 References

- [Amazon Bedrock AgentCore](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/what-is-bedrock-agentcore.html)
- [AgentCore Runtime Sessions](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/runtime-sessions.html)
- [AgentCore Browser Tool](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/built-in-tools.html)
- [Strands Agents Framework](https://strandsagents.com)
- [Strands Community Tools](https://strandsagents.com/latest/documentation/docs/user-guide/concepts/tools/community-tools/)
- [Tavily API](https://tavily.com)
- [Meta Wearables Developer Center](https://wearables.developer.meta.com/)
- [Meta Wearables iOS Integration](https://wearables.developer.meta.com/docs/build-integration-ios)
- [Meta DAT iOS SDK](https://github.com/facebook/meta-wearables-dat-ios)
