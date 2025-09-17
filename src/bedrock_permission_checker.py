import json
import urllib3
import logging
import os

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Create HTTP client
http = urllib3.PoolManager()

def lambda_handler(event, context):
    """
    AWS Lambda handler for Bedrock Agent permission checking.
    Handles both checkUserExists and getUserPermissions functions.
    """
    logger.info(f"Received event: {json.dumps(event)}")

    try:
        # Extract function information from Bedrock Agent event
        function_name = event.get('function', '')
        parameters = event.get('parameters', [])

        # Convert parameters list to dict for easier access
        param_dict = {}
        for param in parameters:
            param_dict[param.get('name')] = param.get('value')

        user_id = param_dict.get('user_id')

        if not user_id:
            return create_bedrock_response("ERROR", {"error": "user_id parameter is required"})

        # Route to appropriate function
        if function_name == 'checkUser':
            return check_user_exists(user_id)
        elif function_name == 'checkPermissions':
            return get_user_permissions(user_id)
        else:
            return create_bedrock_response("ERROR", {"error": f"Unknown function: {function_name}"})

    except Exception as e:
        logger.error(f"Error processing request: {str(e)}")
        return create_bedrock_response("ERROR", {"error": f"Internal error: {str(e)}"})

def check_user_exists(user_id):
    """Check if user exists"""
    try:
        base_url = os.environ.get('PERMISSION_API_BASE', 'https://kpfnbcvnfb.execute-api.us-east-1.amazonaws.com/dev')
        url = f"{base_url}/users/{user_id}"
        logger.info(f"Checking user profile at: {url}")

        resp = http.request('GET', url, timeout=10)
        logger.info(f"Profile check response: {resp.status}")

        if resp.status == 200:
            data = json.loads(resp.data.decode('utf-8'))
            return create_bedrock_response("SUCCESS", {
                "user_exists": True,
                "user_id": user_id,
                "status_code": resp.status,
                "profile_data": data
            })
        elif resp.status == 404:
            return create_bedrock_response("SUCCESS", {
                "user_exists": False,
                "user_id": user_id,
                "status_code": resp.status,
                "message": "User profile not found"
            })
        else:
            return create_bedrock_response("ERROR", {
                "user_exists": False,
                "user_id": user_id,
                "status_code": resp.status,
                "message": f"API returned status {resp.status}"
            })

    except Exception as e:
        logger.error(f"Error checking user profile: {str(e)}")
        return create_bedrock_response("ERROR", {"error": f"Failed to check user profile: {str(e)}"})

def get_user_permissions(user_id):
    """Check user permissions for agents"""
    try:
        base_url = os.environ.get('PERMISSION_API_BASE', 'https://kpfnbcvnfb.execute-api.us-east-1.amazonaws.com/dev')
        url = f"{base_url}/permissions/{user_id}"
        logger.info(f"Checking user permissions at: {url}")

        resp = http.request('GET', url, timeout=10)
        logger.info(f"Permission check response: {resp.status}")

        if resp.status == 200:
            data = json.loads(resp.data.decode('utf-8'))
            # Extract permitted agents from the response structure
            permitted_agents = data.get('data', {}).get('permitted_agents', [])

            return create_bedrock_response("SUCCESS", {
                "user_id": user_id,
                "permitted_agents": permitted_agents,
                "has_advice_permission": "advice-agent" in permitted_agents,
                "status_code": resp.status
            })
        elif resp.status == 404:
            return create_bedrock_response("SUCCESS", {
                "user_id": user_id,
                "permitted_agents": [],
                "has_advice_permission": False,
                "status_code": resp.status,
                "message": "User permissions not found"
            })
        else:
            return create_bedrock_response("ERROR", {
                "user_id": user_id,
                "permitted_agents": [],
                "has_advice_permission": False,
                "status_code": resp.status,
                "message": f"API returned status {resp.status}"
            })

    except Exception as e:
        logger.error(f"Error checking user permissions: {str(e)}")
        return create_bedrock_response("ERROR", {"error": f"Failed to check user permissions: {str(e)}"})

def create_bedrock_response(status, data):
    """Create properly formatted response for Bedrock Agent"""
    return {
        'messageVersion': '1.0',
        'response': {
            'actionGroup': 'permission-checker',
            'function': 'checkPermissions',
            'functionResponse': {
                'responseBody': {
                    'TEXT': {
                        'body': json.dumps({
                            'status': status,
                            'result': data
                        })
                    }
                }
            }
        }
    }