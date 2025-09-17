# AI Advice Agent

A specialized AI agent that provides personalized advice to users. This agent integrates with the [Agent Permission API](../agent-permission/) to ensure only authorized users can access the service.

## 🚀 Live Service

**Base URL**: `https://your-advice-agent.execute-api.us-east-1.amazonaws.com/dev/`

## 📋 Permission Requirements

This agent requires users to have the `advice-agent` permission in the Agent Permission system.

### Permission API Integration

**Permission API Base URL**: `https://kpfnbcvnfb.execute-api.us-east-1.amazonaws.com/dev/`

**API Contract**: See [../agent-permission/api-contract.yaml](../agent-permission/api-contract.yaml) for complete API documentation.

## 🔐 User Permission Check

Before providing advice, this agent verifies user permissions using the Permission API:

```python
import requests

def check_user_permission(user_id):
    """Check if user has permission to access the advice agent"""
    permission_api_url = "https://kpfnbcvnfb.execute-api.us-east-1.amazonaws.com/dev"

    try:
        response = requests.get(f"{permission_api_url}/permissions/{user_id}")

        if response.status_code == 200:
            data = response.json()
            return "advice-agent" in data["data"]["permitted_agents"]
        elif response.status_code == 404:
            return False  # User not found
        else:
            # Service error
            print(f"Permission check failed: {response.status_code}")
            return False

    except requests.RequestException as e:
        print(f"Network error checking permissions: {e}")
        return False

def provide_advice(user_id, question):
    """Main advice function with permission checking"""
    if not check_user_permission(user_id):
        return {
            "error": "ACCESS_DENIED",
            "message": "You don't have permission to access the advice agent. Please contact an administrator."
        }

    # Provide advice logic here
    return {
        "advice": generate_advice(question),
        "user_id": user_id
    }
```

## 🤖 Grant User Permission

To grant a user access to the advice agent:

```bash
# Grant advice-agent permission to a user
curl -X POST "https://kpfnbcvnfb.execute-api.us-east-1.amazonaws.com/dev/permissions/{user_id}/agents" \
  -H "Content-Type: application/json" \
  -d '{"agent_name": "advice-agent"}'

# Response:
{
  "status": "success",
  "data": {
    "user_id": "john",
    "agent_added": "advice-agent",
    "permitted_agents": ["advice-agent"]
  },
  "message": "Permission added successfully"
}
```

## 📖 API Endpoints

### Get Advice
```http
POST /advice
Content-Type: application/json

{
  "user_id": "john",
  "question": "How should I approach learning Python?",
  "context": "I'm a beginner programmer"
}
```

**Response (Success):**
```json
{
  "status": "success",
  "data": {
    "advice": "Start with Python basics: variables, data types, and control structures...",
    "user_id": "john",
    "timestamp": "2025-09-17T14:30:00Z"
  }
}
```

**Response (Permission Denied):**
```json
{
  "status": "error",
  "error": {
    "code": "ACCESS_DENIED",
    "message": "You don't have permission to access the advice agent"
  }
}
```

## 🛠️ Local Development

### Prerequisites
- AWS SAM CLI: `brew install aws-sam-cli`
- Python 3.9+
- Access to the Permission API

### Quick Start
```bash
# Clone and enter directory
git clone <repository-url>
cd ai-advice-agent

# Install dependencies
pip install -r requirements.txt

# Set up environment
cp .env.example .env
# Edit .env with your configuration

# Build and start local API
sam build
sam local start-api --port 3001 --env-vars env.json

# Test locally
curl -X POST http://localhost:3001/advice \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "john",
    "question": "What career advice do you have for software engineers?"
  }'
```

### Environment Variables

Create `.env` file:
```bash
PERMISSION_API_URL=https://kpfnbcvnfb.execute-api.us-east-1.amazonaws.com/dev
AGENT_NAME=advice-agent
LOG_LEVEL=INFO
```

Create `env.json` for SAM Local:
```json
{
  "Parameters": {
    "PERMISSION_API_URL": "https://kpfnbcvnfb.execute-api.us-east-1.amazonaws.com/dev",
    "AGENT_NAME": "advice-agent",
    "ENVIRONMENT": "local"
  }
}
```

## 🚀 AWS Deployment

### Deploy to AWS
```bash
# Deploy using SAM
sam build
sam deploy --guided

# Or use the deployment script
chmod +x deploy.sh
./deploy.sh
```

### Production Configuration
- **Region**: us-east-1 (same as Permission API)
- **Stack Name**: ai-advice-agent
- **Lambda**: Python 3.9, 512MB memory, 30s timeout
- **API Gateway**: REST API with CORS enabled

## 🔒 Security Features

- **Permission Verification**: Every request checks user permissions
- **Rate Limiting**: AWS API Gateway rate limits apply
- **CORS**: Configured for cross-origin requests
- **Error Handling**: Graceful handling of permission API failures
- **Input Validation**: All inputs are sanitized and validated

## 📊 Integration Workflow

```
User Request → Advice Agent → Permission API → Grant/Deny → Response
```

1. **User submits advice request** with `user_id` and `question`
2. **Advice agent checks permissions** via Permission API
3. **Permission API responds** with user's permitted agents
4. **Advice agent verifies** `advice-agent` is in permitted list
5. **If authorized**: Generate and return advice
6. **If unauthorized**: Return permission denied error

## 🤝 User Management

### Check User Profile
```bash
# Get user profile details
curl "https://kpfnbcvnfb.execute-api.us-east-1.amazonaws.com/dev/profiles/{user_id}"
```

### Create New User Profile
```bash
# Create profile (auto-generates user_id from first_name)
curl -X POST "https://kpfnbcvnfb.execute-api.us-east-1.amazonaws.com/dev/profiles" \
  -H "Content-Type: application/json" \
  -d '{
    "first_name": "John",
    "last_name": "Doe",
    "email": "john.doe@example.com",
    "role": "Software Developer"
  }'
```

## 📜 Error Codes

| Code | Description | Action |
|------|-------------|--------|
| `ACCESS_DENIED` | User lacks advice-agent permission | Grant permission via Permission API |
| `USER_NOT_FOUND` | User doesn't exist in system | Create user profile first |
| `INVALID_REQUEST` | Malformed request data | Check request format |
| `SERVICE_UNAVAILABLE` | Permission API or advice service down | Retry later |

## 🔗 Related Services

- **Permission API**: [../agent-permission/](../agent-permission/) - User permission management
- **API Contract**: [../agent-permission/api-contract.yaml](../agent-permission/api-contract.yaml) - Complete API documentation

## 📝 Example Usage

### Full Integration Example
```python
import requests

class AdviceAgentClient:
    def __init__(self):
        self.permission_api = "https://kpfnbcvnfb.execute-api.us-east-1.amazonaws.com/dev"
        self.advice_api = "https://your-advice-agent.execute-api.us-east-1.amazonaws.com/dev"

    def get_advice(self, user_id, question, context=None):
        # Check permissions first
        perm_response = requests.get(f"{self.permission_api}/permissions/{user_id}")

        if perm_response.status_code != 200:
            return {"error": "Could not verify permissions"}

        permitted = perm_response.json()["data"]["permitted_agents"]
        if "advice-agent" not in permitted:
            return {"error": "Access denied - missing advice-agent permission"}

        # Request advice
        advice_response = requests.post(f"{self.advice_api}/advice", json={
            "user_id": user_id,
            "question": question,
            "context": context
        })

        return advice_response.json()

# Usage
client = AdviceAgentClient()
result = client.get_advice("john", "How can I improve my coding skills?")
print(result)
```

## 🆘 Support

For issues or questions:
1. Check user permissions in the [Permission API](../agent-permission/)
2. Verify the user exists in the system
3. Review error responses for specific error codes
4. Test with SAM Local for development issues

## 📜 License

MIT License - see LICENSE file for details.