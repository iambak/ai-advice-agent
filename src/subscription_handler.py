import json
import urllib3
import logging
import os
from typing import Dict, Any, Optional

logger = logging.getLogger()
logger.setLevel(logging.INFO)

http = urllib3.PoolManager()

def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    AWS Lambda handler for user subscription to agents

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
        logger.info(f"Received subscription request: {json.dumps(event)}")

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

        # Extract user_id from path parameters
        path_parameters = event.get('pathParameters', {})
        user_id = path_parameters.get('user_id') if path_parameters else None

        if not user_id:
            return {
                'statusCode': 400,
                'headers': headers,
                'body': json.dumps({
                    'status': 'error',
                    'error': {
                        'code': 'INVALID_REQUEST',
                        'message': 'user_id is required in path'
                    }
                })
            }

        # Validate required fields in body
        agent_name = body.get('agent_name')
        if not agent_name:
            return {
                'statusCode': 400,
                'headers': headers,
                'body': json.dumps({
                    'status': 'error',
                    'error': {
                        'code': 'INVALID_REQUEST',
                        'message': 'agent_name is required in request body'
                    }
                })
            }

        # Get permission API configuration
        permission_api_url = os.environ.get('PERMISSION_API_URL',
                                          'https://kpfnbcvnfb.execute-api.us-east-1.amazonaws.com/dev')
        permission_api_url = permission_api_url.rstrip('/')

        # Subscribe user to the agent
        result = subscribe_user_to_agent(user_id, agent_name, permission_api_url)

        if result['success']:
            return {
                'statusCode': 200,
                'headers': headers,
                'body': json.dumps({
                    'status': 'success',
                    'data': {
                        'message': f'Successfully subscribed user {user_id} to {agent_name}',
                        'user_id': user_id,
                        'agent_name': agent_name,
                        'timestamp': context.aws_request_id if context else None
                    }
                })
            }
        else:
            # Return appropriate error status based on the error type
            status_code = result.get('status_code', 500)
            return {
                'statusCode': status_code,
                'headers': headers,
                'body': json.dumps({
                    'status': 'error',
                    'error': {
                        'code': result.get('error_code', 'SUBSCRIPTION_FAILED'),
                        'message': result.get('message', 'Failed to subscribe user to agent'),
                        'user_id': user_id,
                        'agent_name': agent_name
                    }
                })
            }

    except Exception as e:
        logger.error(f"Unexpected error in subscription handler: {e}")
        return {
            'statusCode': 500,
            'headers': headers,
            'body': json.dumps({
                'status': 'error',
                'error': {
                    'code': 'INTERNAL_ERROR',
                    'message': 'An internal error occurred. Please try again later.'
                }
            })
        }

def subscribe_user_to_agent(user_id: str, agent_name: str, permission_api_url: str) -> Dict[str, Any]:
    """
    Subscribe a user to an agent by calling the permission API

    Args:
        user_id: The user identifier
        agent_name: The name of the agent to subscribe to
        permission_api_url: Base URL for the permission API

    Returns:
        Dict: Result with success flag and details
    """
    try:
        # First check if user profile exists
        profile_url = f"{permission_api_url}/profiles/{user_id}"
        logger.info(f"Checking user profile at: {profile_url}")

        profile_response = http.request('GET', profile_url, timeout=10)
        logger.info(f"Profile check response: {profile_response.status}")

        if profile_response.status == 404:
            return {
                'success': False,
                'status_code': 403,
                'error_code': 'PROFILE_NOT_FOUND',
                'message': f'User profile {user_id} not found. Please contact an administrator to create your profile.'
            }
        elif profile_response.status != 200:
            logger.error(f"Profile check failed with status {profile_response.status}")
            return {
                'success': False,
                'status_code': 500,
                'error_code': 'PROFILE_CHECK_FAILED',
                'message': 'Unable to verify user profile. Please try again later.'
            }

        # Check current permissions to see if user is already subscribed
        permissions_url = f"{permission_api_url}/permissions/{user_id}"
        logger.info(f"Checking current permissions at: {permissions_url}")

        permissions_response = http.request('GET', permissions_url, timeout=10)
        logger.info(f"Permissions check response: {permissions_response.status}")

        if permissions_response.status == 200:
            # User has existing permissions, check if already subscribed
            try:
                permissions_data = json.loads(permissions_response.data.decode('utf-8'))
                current_agents = permissions_data.get('data', {}).get('permitted_agents', [])

                if agent_name in current_agents:
                    return {
                        'success': True,
                        'message': f'User {user_id} is already subscribed to {agent_name}',
                        'already_subscribed': True
                    }
            except (json.JSONDecodeError, KeyError) as e:
                logger.warning(f"Could not parse permissions response: {e}")

        # Proceed with subscription - call the permission API to add the agent
        subscription_url = f"{permission_api_url}/permissions/{user_id}/agents"
        logger.info(f"Subscribing user to agent at: {subscription_url}")

        subscription_payload = {
            "agent_name": agent_name
        }

        subscription_response = http.request(
            'POST',
            subscription_url,
            body=json.dumps(subscription_payload).encode('utf-8'),
            headers={'Content-Type': 'application/json'},
            timeout=15
        )

        logger.info(f"Subscription response: {subscription_response.status}")

        if subscription_response.status == 200:
            # Subscription successful
            try:
                response_data = json.loads(subscription_response.data.decode('utf-8'))
                return {
                    'success': True,
                    'message': f'Successfully subscribed user {user_id} to {agent_name}',
                    'response_data': response_data
                }
            except json.JSONDecodeError:
                # Even if we can't parse the response, if status was 200, treat as success
                return {
                    'success': True,
                    'message': f'Successfully subscribed user {user_id} to {agent_name}'
                }

        elif subscription_response.status == 400:
            # Bad request - likely invalid agent name or request format
            return {
                'success': False,
                'status_code': 400,
                'error_code': 'INVALID_AGENT',
                'message': f'Invalid agent name "{agent_name}" or request format'
            }

        elif subscription_response.status == 409:
            # Conflict - user might already be subscribed
            return {
                'success': True,
                'message': f'User {user_id} is already subscribed to {agent_name}',
                'already_subscribed': True
            }

        else:
            # Other error
            logger.error(f"Subscription failed with status {subscription_response.status}: {subscription_response.data.decode('utf-8')}")
            return {
                'success': False,
                'status_code': 500,
                'error_code': 'SUBSCRIPTION_FAILED',
                'message': f'Failed to subscribe to {agent_name}. Please try again later.'
            }

    except urllib3.exceptions.TimeoutError:
        logger.error("Timeout calling permission API")
        return {
            'success': False,
            'status_code': 500,
            'error_code': 'TIMEOUT',
            'message': 'Request timed out. Please try again later.'
        }

    except Exception as e:
        logger.error(f"Error subscribing user to agent: {e}")
        return {
            'success': False,
            'status_code': 500,
            'error_code': 'INTERNAL_ERROR',
            'message': 'An internal error occurred during subscription. Please try again later.'
        }

# For local testing
if __name__ == "__main__":
    # Test scenario 1: Valid subscription request
    test_event = {
        'httpMethod': 'POST',
        'pathParameters': {'user_id': 'raghav'},
        'body': json.dumps({
            'agent_name': 'advice-agent'
        })
    }

    class MockContext:
        aws_request_id = 'test-subscription-request-id'

    print("=== Test: Valid Subscription Request ===")
    result = lambda_handler(test_event, MockContext())
    print(json.dumps(result, indent=2))

    # Test scenario 2: Missing agent_name
    test_event_missing_agent = {
        'httpMethod': 'POST',
        'pathParameters': {'user_id': 'raghav'},
        'body': json.dumps({})
    }

    print("\n=== Test: Missing agent_name ===")
    result_missing = lambda_handler(test_event_missing_agent, MockContext())
    print(json.dumps(result_missing, indent=2))