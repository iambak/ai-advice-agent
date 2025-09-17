# AI Advice Agent - API Contract

## Overview
The AI Advice Agent provides personalized financial advice through a permission-based system. It serves as middleware that forwards questions to an external advice API and enhances responses using AWS Bedrock for optimal formatting.

## Base URL
```
https://btusv50ei3.execute-api.us-east-1.amazonaws.com/dev
```

## Authentication & Authorization
- **Permission-based access**: Each user must have permission to access the advice agent
- **User validation**: System checks user profile existence and permissions before processing
- **Subscription model**: Users without permission can be offered subscription access

## Endpoints

### POST /advice
Get personalized financial advice for a user.

#### Request Format
```json
{
  "user_id": "string (required)",
  "question": "string (required)",
  "context": "string (optional)"
}
```

#### Request Parameters
- **user_id** (required): Unique identifier for the user requesting advice
- **question** (required): The financial question or topic to get advice on
- **context** (optional): Additional context to improve advice quality and personalization

#### Response Formats

##### Success Response (200)
```json
{
  "status": "success",
  "data": {
    "advice": "string",
    "user_id": "string",
    "timestamp": "string"
  }
}
```

**Advice Format:**
- Begins with "TL;DR:" summary section (2-3 key sentences)
- Followed by detailed advice in clean paragraph format
- No markdown formatting (plain text paragraphs)
- Includes live market data when relevant (prices, dates)
- Contains disclaimers and risk warnings
- Preserves all information from source without additions

##### Permission Denied (403)
```json
{
  "status": "error",
  "error": {
    "code": "ACCESS_DENIED",
    "message": "User does not have permission to access advice agent",
    "user_id": "string"
  }
}
```

##### Subscription Required (403)
```json
{
  "status": "error",
  "error": {
    "code": "SUBSCRIPTION_REQUIRED",
    "message": "User profile exists but permission is required. Would you like to subscribe to the advice agent?",
    "user_id": "string",
    "subscription_info": {
      "instructions": "To grant permission, make a POST request to https://kpfnbcvnfb.execute-api.us-east-1.amazonaws.com/dev/permission/user/agents with body: {\"user_id\": \"[user_id]\", \"agent_name\": \"advice-agent\", \"permission\": \"granted\"}"
    }
  }
}
```

##### Profile Not Found (404)
```json
{
  "status": "error",
  "error": {
    "code": "PROFILE_NOT_FOUND",
    "message": "User profile not found. Please contact support or speak to the admin to create a profile.",
    "user_id": "string"
  }
}
```

##### Bad Request (400)
```json
{
  "status": "error",
  "error": {
    "code": "INVALID_REQUEST",
    "message": "Missing required fields or invalid request format",
    "details": "string"
  }
}
```

##### Service Error (500)
```json
{
  "status": "error",
  "error": {
    "code": "SERVICE_ERROR",
    "message": "Internal service error occurred",
    "details": "string"
  }
}
```

## Example Usage

### Successful Advice Request
```bash
curl -X POST https://btusv50ei3.execute-api.us-east-1.amazonaws.com/dev/advice \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "john_doe",
    "question": "What are the best ethical ETFs for long-term growth?",
    "context": "Looking to invest $50k for retirement in 20 years"
  }'
```

**Response:**
```json
{
  "status": "success",
  "data": {
    "advice": "TL;DR:\nConsider VESG:ASX (global ethical) + VETH:ASX (Australian ethical) for core exposure. Start with 70% global / 30% domestic allocation. Add bond ETFs if you need lower volatility.\n\nFor long-term ethical investing focused on growth, Vanguard's ethical ETF options provide excellent core exposure. VESG:ASX offers ethically-screened international developed market exposure excluding Australia, while VETH:ASX covers the Australian market with fossil fuel and controversial industry exclusions...",
    "user_id": "john_doe",
    "timestamp": "abc123-def456-ghi789"
  }
}
```

### Permission Required Scenario
```bash
curl -X POST https://btusv50ei3.execute-api.us-east-1.amazonaws.com/dev/advice \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "new_user",
    "question": "Should I invest in crypto?",
    "context": "First time investor"
  }'
```

**Response:**
```json
{
  "status": "error",
  "error": {
    "code": "SUBSCRIPTION_REQUIRED",
    "message": "User profile exists but permission is required. Would you like to subscribe to the advice agent?",
    "user_id": "new_user",
    "subscription_info": {
      "instructions": "To grant permission, make a POST request to https://kpfnbcvnbcvnfb.execute-api.us-east-1.amazonaws.com/dev/permission/user/agents with body: {\"user_id\": \"new_user\", \"agent_name\": \"advice-agent\", \"permission\": \"granted\"}"
    }
  }
}
```

## Agent Integration Notes

### For Calling Agents
1. **Always include user_id**: Required for permission validation
2. **Handle permission errors gracefully**: Guide users through subscription process
3. **Provide meaningful context**: Improves advice quality and personalization
4. **Parse TL;DR format**: Response starts with summary, followed by details
5. **Respect rate limits**: External API may have processing delays (2-6 seconds typical)

### Response Processing
- **TL;DR Section**: Extract key points for quick user consumption
- **Detailed Content**: Full advice in paragraph format, ready for display
- **Live Data**: Responses include current market prices and timestamps
- **Disclaimers**: All advice includes appropriate risk warnings

### Error Handling
- **403 Errors**: User permission issues - guide through subscription
- **404 Errors**: User profile not found - direct to admin/support
- **500 Errors**: Service issues - retry with exponential backoff
- **400 Errors**: Request format issues - validate input parameters

### Performance Characteristics
- **Typical Response Time**: 3-8 seconds (includes external API + AI processing)
- **Timeout**: 5 minutes maximum
- **Availability**: 99.9% uptime target
- **Rate Limits**: None currently enforced

## Permission API Integration
To grant user permission programmatically:

```bash
curl -X POST https://kpfnbcvnfb.execute-api.us-east-1.amazonaws.com/dev/permission/user/agents \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "user_id_here",
    "agent_name": "advice-agent",
    "permission": "granted"
  }'
```

## Architecture Overview
1. **Permission Check**: Validates user access via Permission API
2. **External API Call**: Forwards question to specialized advice service
3. **AI Enhancement**: Uses AWS Bedrock (Amazon Titan) to format response
4. **Response Delivery**: Returns formatted advice in consistent format

## Support & Contact
- **API Issues**: Monitor CloudWatch logs for debugging
- **Permission Issues**: Check Permission API service status
- **User Onboarding**: Direct users to admin for profile creation