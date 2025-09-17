#!/bin/bash

# AI Advice Agent Deployment Script
# Deploys the advice agent to AWS using SAM

set -e  # Exit on any error

echo "🚀 Starting AI Advice Agent deployment..."

# Check if AWS CLI is configured
if ! aws sts get-caller-identity > /dev/null 2>&1; then
    echo "❌ AWS CLI not configured. Please run 'aws configure' first."
    exit 1
fi

# Check if SAM CLI is installed
if ! command -v sam &> /dev/null; then
    echo "❌ SAM CLI not found. Please install it with: brew install aws-sam-cli"
    exit 1
fi

# Get current AWS region
AWS_REGION=$(aws configure get region)
if [ -z "$AWS_REGION" ]; then
    AWS_REGION="us-east-1"
    echo "⚠️  No AWS region configured, defaulting to us-east-1"
fi

echo "📍 Deploying to region: $AWS_REGION"

# Set deployment parameters
STACK_NAME="ai-advice-agent"
PERMISSION_API_URL="https://kpfnbcvnfb.execute-api.us-east-1.amazonaws.com/dev"
AGENT_NAME="advice-agent"

echo "📦 Building SAM application..."
sam build

echo "🚀 Deploying to AWS..."
sam deploy \
    --stack-name "$STACK_NAME" \
    --region "$AWS_REGION" \
    --capabilities CAPABILITY_IAM \
    --parameter-overrides \
        PermissionApiUrl="$PERMISSION_API_URL" \
        AgentName="$AGENT_NAME" \
        LogLevel="INFO" \
    --confirm-changeset \
    --resolve-s3

if [ $? -eq 0 ]; then
    echo "✅ Deployment successful!"

    # Get the API endpoint
    API_ENDPOINT=$(aws cloudformation describe-stacks \
        --stack-name "$STACK_NAME" \
        --region "$AWS_REGION" \
        --query 'Stacks[0].Outputs[?OutputKey==`AdviceAgentApi`].OutputValue' \
        --output text)

    echo ""
    echo "🌐 API Endpoint: $API_ENDPOINT"
    echo ""
    echo "📝 Test your deployment:"
    echo "curl -X POST \"${API_ENDPOINT}advice\" \\"
    echo "  -H \"Content-Type: application/json\" \\"
    echo "  -d '{"
    echo "    \"user_id\": \"your_user_id\","
    echo "    \"question\": \"How can I improve my programming skills?\","
    echo "    \"context\": \"I am a beginner developer\""
    echo "  }'"
    echo ""
    echo "⚠️  Remember: Users need 'advice-agent' permission in the Permission API:"
    echo "curl -X POST \"$PERMISSION_API_URL/permissions/your_user_id/agents\" \\"
    echo "  -H \"Content-Type: application/json\" \\"
    echo "  -d '{\"agent_name\": \"advice-agent\"}'"
    echo ""
    echo "🎉 Deployment complete!"
else
    echo "❌ Deployment failed!"
    exit 1
fi