# 🔒 Security Recommendations for Meta AgentCore Chat

## Current Security Issues

### 🚨 CRITICAL Issues

1. **API Key Hardcoded in iOS App**
   - **Risk:** Anyone can decompile the app and extract the API key
   - **Impact:** Unlimited API access, massive AWS costs, abuse of Bedrock limits
   - **Priority:** URGENT

2. **No Real User Authentication**
   - **Risk:** Anyone with API key can impersonate any device_id
   - **Impact:** No user accountability, potential abuse
   - **Priority:** HIGH

### ⚠️ MEDIUM Risk Issues

3. **Open CORS Policy**
   - **Risk:** Any website can call your API
   - **Impact:** Potential for abuse from web-based attacks
   - **Priority:** MEDIUM

4. **No Input Size Validation**
   - **Risk:** Large prompts can increase costs
   - **Impact:** Cost escalation, potential DoS
   - **Priority:** MEDIUM

5. **No WAF Protection**
   - **Risk:** Vulnerable to DDoS, bots, common attacks
   - **Impact:** Service disruption, cost increase
   - **Priority:** MEDIUM

---

## 🛡️ Recommended Solutions

### Option 1: AWS Cognito + Request Signing (RECOMMENDED)

**Implementation:**

#### Backend Changes:

1. **Add Cognito to CDK Stack:**

```python
# In meta_agentcore_chat_stack.py
from aws_cdk import aws_cognito as cognito

# Create Cognito User Pool
user_pool = cognito.UserPool(
    self, "ChatUserPool",
    self_sign_up_enabled=True,
    sign_in_aliases=cognito.SignInAliases(email=True),
    password_policy=cognito.PasswordPolicy(
        min_length=8,
        require_lowercase=True,
        require_uppercase=True,
        require_digits=True,
    ),
)

# Create App Client for iOS
app_client = user_pool.add_client(
    "iOSAppClient",
    auth_flows=cognito.AuthFlow(user_srp=True),
    generate_secret=False,
)

# Add Cognito Authorizer to API Gateway
authorizer = apigw.CognitoUserPoolsAuthorizer(
    self, "CognitoAuthorizer",
    cognito_user_pools=[user_pool],
)

# Apply to endpoints
chat_resource.add_method(
    "POST",
    integration,
    authorizer=authorizer,
    authorization_type=apigw.AuthorizationType.COGNITO,
)

# Output pool ID
CfnOutput(self, "UserPoolId", value=user_pool.user_pool_id)
CfnOutput(self, "AppClientId", value=app_client.user_pool_client_id)
```

2. **Update Lambda to validate Cognito token:**

```python
def lambda_handler(event, context):
    # Cognito automatically validates the token
    # User info is in event['requestContext']['authorizer']['claims']
    user_claims = event.get('requestContext', {}).get('authorizer', {}).get('claims', {})
    user_id = user_claims.get('sub', 'unknown')  # Real user ID from Cognito

    # Use real user_id instead of device_id
    # Rest of your code...
```

#### iOS Changes:

1. **Add AWS Amplify:**

```swift
// In Package.swift or Xcode SPM
dependencies: [
    .package(url: "https://github.com/aws-amplify/amplify-swift", from: "2.0.0")
]
```

2. **Configure Amplify:**

```swift
// In AppConfig.swift
import Amplify
import AWSCognitoAuthPlugin

static func configureAmplify() {
    let authConfig = AWSCognitoPluginConfiguration(
        region: "us-east-1",
        userPoolId: "us-east-1_XXXXXXX",
        userPoolClientId: "xxxxxxxxxxxxxxxxxxxx"
    )

    try? Amplify.add(plugin: AWSCognitoAuthPlugin(configuration: authConfig))
    try? Amplify.configure()
}
```

3. **Update API Service to use tokens:**

```swift
// In ChatAPIService.swift
func send(prompt: String) async throws -> String {
    // Get Cognito token
    let session = try await Amplify.Auth.fetchAuthSession()
    guard let token = (session as? AuthCognitoTokensProvider)?.getTokens()?.idToken else {
        throw ChatError.notAuthenticated
    }

    var request = URLRequest(url: AppConfig.chatURL)
    request.httpMethod = "POST"
    request.setValue("application/json", forHTTPHeaderField: "Content-Type")
    request.setValue(token, forHTTPHeaderField: "Authorization")  // Use Cognito token
    request.httpBody = try JSONSerialization.data(withJSONObject: body)

    // Rest of your code...
}
```

**Benefits:**
- ✅ No hardcoded API keys
- ✅ Real user authentication
- ✅ Token expiration and refresh
- ✅ User management (sign up, sign in, password reset)

**Cost:** ~$0.0055 per MAU (Monthly Active User) for first 50k users

---

### Option 2: Request Signing with Symmetric Key (Simpler)

**Implementation:**

1. **Generate a secret in AWS Secrets Manager:**

```bash
aws secretsmanager create-secret \
    --name meta-chat-signing-secret \
    --secret-string "$(openssl rand -base64 32)" \
    --region us-east-1
```

2. **Lambda validates signed requests:**

```python
import hmac
import hashlib
import time

SECRET_NAME = "meta-chat-signing-secret"
secrets_client = boto3.client('secretsmanager')

def verify_signature(body, signature, timestamp):
    # Check timestamp (prevent replay attacks)
    if abs(time.time() - int(timestamp)) > 300:  # 5 minutes
        return False

    # Get signing secret
    secret = secrets_client.get_secret_value(SecretId=SECRET_NAME)['SecretString']

    # Calculate expected signature
    message = f"{timestamp}:{body}"
    expected = hmac.new(secret.encode(), message.encode(), hashlib.sha256).hexdigest()

    return hmac.compare_digest(expected, signature)

def lambda_handler(event, context):
    headers = event.get('headers', {})
    signature = headers.get('x-signature')
    timestamp = headers.get('x-timestamp')
    body = event.get('body', '')

    if not verify_signature(body, signature, timestamp):
        return _response(403, {"error": "Invalid signature"})

    # Rest of your code...
```

3. **iOS signs every request:**

```swift
// In ChatAPIService.swift
import CryptoKit

private let signingKey = "YOUR_SIGNING_KEY"  // Store securely

func signRequest(body: Data) -> (signature: String, timestamp: String) {
    let timestamp = String(Int(Date().timeIntervalSince1970))
    let message = "\(timestamp):\(String(data: body, encoding: .utf8) ?? "")"

    let key = SymmetricKey(data: signingKey.data(using: .utf8)!)
    let signature = HMAC<SHA256>.authenticationCode(for: message.data(using: .utf8)!, using: key)

    return (signature.hexString, timestamp)
}

func send(prompt: String) async throws -> String {
    let body: [String: Any] = ["prompt": prompt, "device_id": deviceId]
    let jsonData = try JSONSerialization.data(withJSONObject: body)

    let (signature, timestamp) = signRequest(body: jsonData)

    var request = URLRequest(url: AppConfig.chatURL)
    request.httpMethod = "POST"
    request.setValue("application/json", forHTTPHeaderField: "Content-Type")
    request.setValue(signature, forHTTPHeaderField: "x-signature")
    request.setValue(timestamp, forHTTPHeaderField: "x-timestamp")
    request.httpBody = jsonData

    // Rest of your code...
}
```

**Benefits:**
- ✅ No hardcoded API keys
- ✅ Prevents tampering
- ✅ Prevents replay attacks
- ✅ Simpler than Cognito

**Drawback:**
- ❌ Key still in iOS app (but harder to extract and use)
- ❌ No user management

---

### Option 3: Additional Security Hardening

**1. Add AWS WAF:**

```python
# In CDK stack
from aws_cdk import aws_wafv2 as waf

web_acl = waf.CfnWebACL(
    self, "ChatApiWAF",
    scope="REGIONAL",
    default_action=waf.CfnWebACL.DefaultActionProperty(allow={}),
    visibility_config=waf.CfnWebACL.VisibilityConfigProperty(
        cloud_watch_metrics_enabled=True,
        metric_name="ChatApiWAF",
        sampled_requests_enabled=True,
    ),
    rules=[
        # Rate limiting per IP
        waf.CfnWebACL.RuleProperty(
            name="RateLimitRule",
            priority=1,
            statement=waf.CfnWebACL.StatementProperty(
                rate_based_statement=waf.CfnWebACL.RateBasedStatementProperty(
                    limit=100,  # 100 requests per 5 minutes per IP
                    aggregate_key_type="IP",
                )
            ),
            action=waf.CfnWebACL.RuleActionProperty(block={}),
            visibility_config=waf.CfnWebACL.VisibilityConfigProperty(
                cloud_watch_metrics_enabled=True,
                metric_name="RateLimitRule",
                sampled_requests_enabled=True,
            ),
        ),
        # AWS Managed Rules
        waf.CfnWebACL.RuleProperty(
            name="AWSManagedRules",
            priority=2,
            statement=waf.CfnWebACL.StatementProperty(
                managed_rule_group_statement=waf.CfnWebACL.ManagedRuleGroupStatementProperty(
                    vendor_name="AWS",
                    name="AWSManagedRulesCommonRuleSet",
                )
            ),
            override_action=waf.CfnWebACL.OverrideActionProperty(none={}),
            visibility_config=waf.CfnWebACL.VisibilityConfigProperty(
                cloud_watch_metrics_enabled=True,
                metric_name="AWSManagedRules",
                sampled_requests_enabled=True,
            ),
        ),
    ],
)

# Associate with API Gateway
waf_association = waf.CfnWebACLAssociation(
    self, "WAFAssociation",
    resource_arn=f"arn:aws:apigateway:{region}::/restapis/{api.rest_api_id}/stages/prod",
    web_acl_arn=web_acl.attr_arn,
)
```

**2. Add Input Validation:**

```python
def lambda_handler(event, context):
    # ... existing code ...

    # Validate prompt size
    MAX_PROMPT_LENGTH = 4000  # tokens
    if len(prompt) > MAX_PROMPT_LENGTH:
        return _response(400, {"error": f"Prompt too long. Max {MAX_PROMPT_LENGTH} chars"})

    # Sanitize input
    prompt = prompt.replace('\x00', '')  # Remove null bytes

    # Rest of your code...
```

**3. Restrict CORS:**

```python
default_cors_preflight_options=apigw.CorsOptions(
    allow_origins=["https://yourdomain.com"],  # Only your domain
    allow_methods=["POST", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization"],
    allow_credentials=True,
)
```

**4. Add CloudWatch Alarms:**

```python
from aws_cdk import aws_cloudwatch as cw, aws_cloudwatch_actions as cw_actions

# Alarm for high API usage
high_usage_alarm = cw.Alarm(
    self, "HighUsageAlarm",
    metric=api.metric_count(),
    threshold=10000,
    evaluation_periods=1,
    comparison_operator=cw.ComparisonOperator.GREATER_THAN_THRESHOLD,
)

# Alarm for 4xx errors
error_alarm = cw.Alarm(
    self, "ErrorAlarm",
    metric=api.metric_client_error(),
    threshold=100,
    evaluation_periods=1,
)
```

**5. Enable DynamoDB Encryption:**

```python
from aws_cdk import aws_dynamodb as dynamodb

table = dynamodb.Table(
    self, "Messages",
    encryption=dynamodb.TableEncryption.AWS_MANAGED,  # Or CUSTOMER_MANAGED for KMS
    point_in_time_recovery=True,
    # ... rest of config
)
```

---

## 📋 Implementation Priority

| Priority | Action | Effort | Impact |
|----------|--------|--------|--------|
| 🚨 **P0** | Implement Cognito or Request Signing | Medium | Critical |
| ⚠️ **P1** | Add input validation & size limits | Low | High |
| ⚠️ **P1** | Restrict CORS to specific origins | Low | Medium |
| ⚠️ **P2** | Add AWS WAF | Medium | High |
| ℹ️ **P3** | Enable DynamoDB encryption | Low | Medium |
| ℹ️ **P3** | Add CloudWatch alarms | Low | Medium |

---

## 💰 Cost Considerations

| Security Feature | Estimated Monthly Cost |
|-----------------|----------------------|
| AWS Cognito | $0.28 - $275 (based on MAU) |
| AWS WAF | $5 + $1 per million requests |
| Secrets Manager | $0.40 per secret |
| KMS (for encryption) | $1 per key + $0.03 per 10k requests |
| CloudWatch Alarms | $0.10 per alarm |

---

## 🎯 Quick Win: Immediate Actions

1. **Rotate API Key immediately** after implementing better auth
2. **Enable CloudWatch Logs** for all Lambda functions
3. **Set up billing alerts** in AWS to catch unexpected usage
4. **Implement rate limiting per device_id** in Lambda
5. **Add request logging** to track usage patterns

---

## 📚 Additional Resources

- [AWS Well-Architected Security Pillar](https://docs.aws.amazon.com/wellarchitected/latest/security-pillar/welcome.html)
- [OWASP Mobile Security](https://owasp.org/www-project-mobile-security/)
- [AWS Cognito Best Practices](https://docs.aws.amazon.com/cognito/latest/developerguide/security-best-practices.html)
