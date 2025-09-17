import json
import os
import requests
import logging
import boto3
from typing import Dict, Any, Optional, Tuple
from enum import Enum

class PermissionStatus(Enum):
    """Enum for different permission check results"""
    GRANTED = "granted"
    USER_EXISTS_NO_PERMISSION = "user_exists_no_permission"
    PROFILE_NOT_FOUND = "profile_not_found"
    ERROR = "error"

logger = logging.getLogger()
logger.setLevel(logging.INFO)

class PermissionChecker:
    """Handles permission verification with the Agent Permission API"""

    def __init__(self, permission_api_url: str):
        self.permission_api_url = permission_api_url.rstrip('/')

    def check_user_permission(self, user_id: str, agent_name: str = "advice-agent") -> Tuple[PermissionStatus, Optional[Dict]]:
        """
        Check if user has permission to access the specified agent
        First checks if user profile exists, then checks permissions

        Args:
            user_id: The user identifier
            agent_name: The agent name to check permission for

        Returns:
            Tuple[PermissionStatus, Optional[Dict]]: Status and optional user data
        """
        try:
            # First check if user profile exists
            profile_response = requests.get(
                f"{self.permission_api_url}/profiles/{user_id}",
                timeout=10
            )

            if profile_response.status_code == 404:
                logger.warning(f"User profile {user_id} not found")
                return PermissionStatus.PROFILE_NOT_FOUND, None
            elif profile_response.status_code != 200:
                logger.error(f"Profile check failed with status {profile_response.status_code}")
                return PermissionStatus.ERROR, None

            # Profile exists, now check permissions
            permission_response = requests.get(
                f"{self.permission_api_url}/permissions/{user_id}",
                timeout=10
            )

            if permission_response.status_code == 200:
                data = permission_response.json()
                permitted_agents = data.get("data", {}).get("permitted_agents", [])
                if agent_name in permitted_agents:
                    return PermissionStatus.GRANTED, data.get("data")
                else:
                    return PermissionStatus.USER_EXISTS_NO_PERMISSION, data.get("data")
            elif permission_response.status_code == 404:
                # User profile exists but no permissions set yet
                logger.info(f"User {user_id} has profile but no permissions set")
                return PermissionStatus.USER_EXISTS_NO_PERMISSION, None
            else:
                logger.error(f"Permission check failed with status {permission_response.status_code}")
                return PermissionStatus.ERROR, None

        except requests.RequestException as e:
            logger.error(f"Network error checking permissions for {user_id}: {e}")
            return PermissionStatus.ERROR, None
        except Exception as e:
            logger.error(f"Unexpected error checking permissions for {user_id}: {e}")
            return PermissionStatus.ERROR, None

class AdviceGenerator:
    """Smart middleware that gets advice from external API and enhances it with Bedrock"""

    def __init__(self):
        """Initialize external API and Bedrock clients"""
        self.bedrock_client = boto3.client('bedrock-runtime', region_name=os.environ.get('BEDROCK_REGION', 'us-east-1'))
        self.model_id = os.environ.get('BEDROCK_MODEL_ID', 'anthropic.claude-3-haiku-20240307-v1:0')
        self.external_api_url = os.environ.get('EXTERNAL_ADVICE_API_URL', 'http://3.93.70.165:8000/advise')
        self.default_length = os.environ.get('ADVICE_LENGTH', 'long')
        self.default_temperature = float(os.environ.get('ADVICE_TEMPERATURE', '0.5'))

    def generate_advice(self, question: str, context: Optional[str] = None, user_id: str = None) -> str:
        """
        Two-stage advice generation: External API + Bedrock enhancement

        Args:
            question: The user's question
            context: Optional context to help generate better advice
            user_id: User identifier for personalization

        Returns:
            str: Enhanced and beautified advice
        """
        if not question or not question.strip():
            return "I'd be happy to help! Could you please ask me a specific question?"

        try:
            # Stage 1: Get raw advice from external API
            raw_advice = self._get_external_advice(question, context)

            # Stage 2: Enhance and beautify with Bedrock
            enhanced_advice = self._enhance_with_bedrock(raw_advice, question, context, user_id)

            logger.info(f"Successfully generated enhanced advice for user {user_id}")
            return enhanced_advice

        except Exception as e:
            logger.error(f"Error in two-stage advice generation: {e}")
            return self._fallback_advice(question, context)

    def _get_external_advice(self, question: str, context: Optional[str] = None) -> str:
        """Get raw advice from external API"""
        try:
            # Combine question and context for external API
            full_question = question
            if context:
                full_question = f"{question}. Additional context: {context}"

            # Prepare request for external API
            payload = {
                "question": full_question,
                "length": self.default_length,
                "temperature": self.default_temperature
            }

            logger.info(f"Calling external advice API: {self.external_api_url}")

            # Call external API
            response = requests.post(
                self.external_api_url,
                json=payload,
                headers={"Content-Type": "application/json"},
                timeout=30
            )

            if response.status_code == 200:
                # Try to extract advice from JSON response
                try:
                    data = response.json()
                    # Handle different possible response formats
                    if isinstance(data, dict):
                        # Check for error in response
                        if 'error' in data:
                            logger.error(f"External API returned error: {data['error']}")
                            raise Exception(f"External API error: {data['error']}")

                        advice = data.get('advice', data.get('response', data.get('answer', str(data))))
                    else:
                        advice = str(data)

                    # Validate we got meaningful advice
                    if not advice or advice.strip() == "" or len(advice.strip()) < 10:
                        raise Exception("External API returned empty or invalid advice")

                    logger.info("Successfully received advice from external API")
                    return advice
                except json.JSONDecodeError:
                    # If not JSON, treat as plain text
                    if response.text and len(response.text.strip()) > 10:
                        return response.text
                    else:
                        raise Exception("External API returned invalid response format")
            else:
                logger.error(f"External API returned status {response.status_code}: {response.text}")
                raise Exception(f"External API error: {response.status_code}")

        except requests.RequestException as e:
            logger.error(f"Network error calling external API: {e}")
            raise Exception(f"Failed to connect to external advice service: {e}")
        except Exception as e:
            logger.error(f"Error getting external advice: {e}")
            raise

    def _enhance_with_bedrock(self, raw_advice: str, question: str, context: Optional[str] = None, user_id: str = None) -> str:
        """Enhance raw advice using Bedrock"""
        try:
            # Build enhancement prompt
            prompt = self._build_enhancement_prompt(raw_advice, question, context)

            # Prepare Bedrock request for Titan Text G1 Premier
            request_body = {
                "inputText": prompt,
                "textGenerationConfig": {
                    "maxTokenCount": 800,
                    "temperature": 0.3,
                    "topP": 0.9
                }
            }

            # Invoke Bedrock
            response = self.bedrock_client.invoke_model(
                modelId=self.model_id,
                body=json.dumps(request_body),
                contentType="application/json"
            )

            # Parse response
            response_body = json.loads(response['body'].read())
            enhanced_advice = response_body['results'][0]['outputText']

            logger.info(f"Successfully enhanced advice using Bedrock for user {user_id}")
            return enhanced_advice.strip()

        except Exception as e:
            logger.error(f"Error enhancing advice with Bedrock: {e}")
            # If Bedrock fails, return the raw advice
            logger.info("Falling back to raw advice from external API")
            return raw_advice

    def _build_enhancement_prompt(self, raw_advice: str, question: str, context: Optional[str] = None) -> str:
        """Build prompt for Bedrock to enhance the raw advice"""
        prompt = f"""You are a text formatter. Your job is to reformat the provided advice content ONLY. Do not add any new information, recommendations, or data.

Original Question: {question}"""

        if context:
            prompt += f"\nUser Context: {context}"

        prompt += f"""

Raw Advice Content:
{raw_advice}

INSTRUCTIONS:
1. Create a TL;DR summary using ONLY the key points already mentioned in the content
2. Convert the rest into clean paragraph format using ONLY the existing information
3. DO NOT add any new advice, recommendations, or data
4. DO NOT make up any information that isn't in the original content
5. Simply reformat what's already there

REQUIRED FORMAT:

TL;DR: [Summarize only the existing key recommendations in 2-3 sentences]

[Convert the existing detailed advice into flowing paragraphs. Remove markdown formatting but keep all the same information, prices, data, and recommendations that were already provided. Just present it as readable paragraphs instead of bullet points and headers.]

CRITICAL: Use only the information provided in the raw advice content. Do not add anything new."""

        return prompt

    def _fallback_advice(self, question: str, context: Optional[str] = None) -> str:
        """Fallback advice if both external API and Bedrock fail"""
        advice = f"""Thank you for your question: "{question}"

I apologize, but I'm experiencing technical difficulties with our advice services. Here's some general guidance while we resolve the issue:

1. **Research Thoroughly**: Look for reliable sources and expert opinions on your topic
2. **Consider Multiple Perspectives**: Seek out different viewpoints to get a complete picture
3. **Start Small**: Break down complex decisions into smaller, manageable steps
4. **Seek Expert Input**: Consider consulting with professionals who specialize in this area
5. **Take Time to Reflect**: Don't rush important decisions - allow time for careful consideration"""

        if context:
            advice += f"\n\nGiven your context ({context}), please try again later for more personalized advice tailored to your specific situation."

        advice += "\n\nPlease try again in a few minutes, and we'll provide you with enhanced, personalized advice."

        return advice

def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    AWS Lambda handler for the advice agent

    Args:
        event: Lambda event containing HTTP request data
        context: Lambda context object

    Returns:
        Dict: HTTP response
    """

    # CORS headers
    headers = {
        'Content-Type': 'application/json',
        'Access-Control-Allow-Origin': '*',
        'Access-Control-Allow-Headers': 'Content-Type,X-Amz-Date,Authorization,X-Api-Key,X-Amz-Security-Token',
        'Access-Control-Allow-Methods': 'OPTIONS,POST,GET'
    }

    try:
        # Handle OPTIONS request for CORS
        if event.get('httpMethod') == 'OPTIONS':
            return {
                'statusCode': 200,
                'headers': headers,
                'body': json.dumps({'message': 'CORS preflight successful'})
            }

        # Parse request body
        if 'body' not in event or not event['body']:
            return {
                'statusCode': 400,
                'headers': headers,
                'body': json.dumps({
                    'status': 'error',
                    'error': {
                        'code': 'INVALID_REQUEST',
                        'message': 'Request body is required'
                    }
                })
            }

        try:
            body = json.loads(event['body'])
        except json.JSONDecodeError:
            return {
                'statusCode': 400,
                'headers': headers,
                'body': json.dumps({
                    'status': 'error',
                    'error': {
                        'code': 'INVALID_REQUEST',
                        'message': 'Invalid JSON in request body'
                    }
                })
            }

        # Validate required fields
        user_id = body.get('user_id')
        question = body.get('question')

        if not user_id:
            return {
                'statusCode': 400,
                'headers': headers,
                'body': json.dumps({
                    'status': 'error',
                    'error': {
                        'code': 'INVALID_REQUEST',
                        'message': 'user_id is required'
                    }
                })
            }

        if not question:
            return {
                'statusCode': 400,
                'headers': headers,
                'body': json.dumps({
                    'status': 'error',
                    'error': {
                        'code': 'INVALID_REQUEST',
                        'message': 'question is required'
                    }
                })
            }

        # Get configuration from environment
        permission_api_url = os.environ.get('PERMISSION_API_URL',
                                          'https://kpfnbcvnfb.execute-api.us-east-1.amazonaws.com/dev')
        agent_name = os.environ.get('AGENT_NAME', 'advice-agent')

        # Check user permissions
        permission_checker = PermissionChecker(permission_api_url)
        permission_status, user_data = permission_checker.check_user_permission(user_id, agent_name)

        if permission_status == PermissionStatus.GRANTED:
            # User has permission, proceed with advice generation
            pass
        elif permission_status == PermissionStatus.USER_EXISTS_NO_PERMISSION:
            # User exists but lacks permission - offer subscription
            return {
                'statusCode': 403,
                'headers': headers,
                'body': json.dumps({
                    'status': 'error',
                    'error': {
                        'code': 'SUBSCRIPTION_REQUIRED',
                        'message': f'You are not subscribed to the {agent_name} service.',
                        'user_id': user_id,
                        'action_available': True,
                        'action_message': f'Would you like to subscribe to the {agent_name} service?',
                        'subscription_instructions': {
                            'method': 'POST',
                            'url': f'{permission_api_url}/permissions/{user_id}/agents',
                            'body': {'agent_name': agent_name},
                            'description': 'Send a POST request to subscribe to the advice agent service'
                        }
                    }
                })
            }
        elif permission_status == PermissionStatus.PROFILE_NOT_FOUND:
            # User profile doesn't exist - direct to admin/support
            return {
                'statusCode': 403,
                'headers': headers,
                'body': json.dumps({
                    'status': 'error',
                    'error': {
                        'code': 'PROFILE_NOT_FOUND',
                        'message': 'User profile not found. Please contact an administrator or support to create your profile.',
                        'user_id': user_id,
                        'action_available': False,
                        'support_message': 'Contact your system administrator or support team to set up your user profile before using this service.'
                    }
                })
            }
        else:
            # Error case
            return {
                'statusCode': 500,
                'headers': headers,
                'body': json.dumps({
                    'status': 'error',
                    'error': {
                        'code': 'SERVICE_UNAVAILABLE',
                        'message': 'Unable to verify permissions. Please try again later.',
                        'user_id': user_id
                    }
                })
            }

        # Generate advice
        advice_generator = AdviceGenerator()
        advice = advice_generator.generate_advice(
            question=question,
            context=body.get('context'),
            user_id=user_id
        )

        # Return successful response
        return {
            'statusCode': 200,
            'headers': headers,
            'body': json.dumps({
                'status': 'success',
                'data': {
                    'advice': advice,
                    'user_id': user_id,
                    'timestamp': context.aws_request_id if context else None
                }
            })
        }

    except Exception as e:
        logger.error(f"Unexpected error in lambda_handler: {e}")
        return {
            'statusCode': 500,
            'headers': headers,
            'body': json.dumps({
                'status': 'error',
                'error': {
                    'code': 'SERVICE_UNAVAILABLE',
                    'message': 'An internal error occurred. Please try again later.'
                }
            })
        }

# For local testing
if __name__ == "__main__":
    import sys

    # Test scenario 1: User not found (default test)
    test_event_not_found = {
        'httpMethod': 'POST',
        'body': json.dumps({
            'user_id': 'test_user',
            'question': 'How can I improve my programming skills?',
            'context': 'I\'m a beginner developer'
        })
    }

    class MockContext:
        aws_request_id = 'test-request-id'

    print("=== Test 1: Profile Not Found ===")
    result = lambda_handler(test_event_not_found, MockContext())
    print(json.dumps(result, indent=2))

    # Test scenario 2: Show example response for user exists but no subscription
    print("\n=== Example Response: User Exists But No Subscription ===")
    subscription_example = {
        "statusCode": 403,
        "headers": {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Headers": "Content-Type,X-Amz-Date,Authorization,X-Api-Key,X-Amz-Security-Token",
            "Access-Control-Allow-Methods": "OPTIONS,POST,GET"
        },
        "body": json.dumps({
            "status": "error",
            "error": {
                "code": "SUBSCRIPTION_REQUIRED",
                "message": "You are not subscribed to the advice-agent service.",
                "user_id": "existing_user",
                "action_available": True,
                "action_message": "Would you like to subscribe to the advice-agent service?",
                "subscription_instructions": {
                    "method": "POST",
                    "url": "https://kpfnbcvnfb.execute-api.us-east-1.amazonaws.com/dev/permissions/existing_user/agents",
                    "body": {"agent_name": "advice-agent"},
                    "description": "Send a POST request to subscribe to the advice agent service"
                }
            }
        })
    }
    print(json.dumps(subscription_example, indent=2))