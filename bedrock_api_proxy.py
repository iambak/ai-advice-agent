import json
import urllib3
import logging
import os

logger = logging.getLogger()
logger.setLevel(logging.INFO)
http = urllib3.PoolManager()

def lambda_handler(event, context):
    """Simple Lambda proxy for Bedrock to invoke the advice API"""
    logger.info(f"Received Bedrock event: {json.dumps(event)}")

    try:
        param_dict = {}
        api_path = '/getAdvice'
        http_method = 'POST'

        # Handle Bedrock Agent action group format
        if 'actionGroupInvocationInput' in event:
            action_group_input = event['actionGroupInvocationInput']
            api_path = action_group_input.get('apiPath', '/getAdvice')
            http_method = action_group_input.get('verb', 'POST').upper()

            # Extract parameters from requestBody
            request_body = action_group_input.get('requestBody', {})
            content = request_body.get('content', {})
            json_content = content.get('application/json', {})

            # Handle both array format and properties object format
            if isinstance(json_content, list):
                # Format: [{"name": "user_id", "value": "abhinav"}]
                json_params = json_content
            elif isinstance(json_content, dict) and 'properties' in json_content:
                # Format: {"properties": [{"name": "user_id", "value": "abhinav"}]}
                json_params = json_content.get('properties', [])
            else:
                # Fallback - try to extract from any nested structure
                json_params = []
                logger.info(f"Unexpected json_content format: {json_content}")

            for param in json_params:
                if isinstance(param, dict):
                    param_name = param.get('name')
                    param_value = param.get('value')
                    if param_name and param_value is not None:
                        param_dict[param_name] = param_value

        else:
            # Handle legacy direct event format
            api_path = event.get('apiPath', '/getAdvice')
            http_method = event.get('httpMethod', 'POST')

            # Try requestBody format first
            request_body = event.get('requestBody', {})
            if request_body:
                content = request_body.get('content', {})
                json_content = content.get('application/json', {})

                if isinstance(json_content, list):
                    json_params = json_content
                elif isinstance(json_content, dict):
                    json_params = json_content.get('properties', [])
                else:
                    json_params = []

                for param in json_params:
                    if isinstance(param, dict):
                        param_name = param.get('name')
                        param_value = param.get('value')
                        if param_name and param_value is not None:
                            param_dict[param_name] = param_value

            # Fallback to legacy parameters format
            if not param_dict:
                parameters = event.get('parameters', [])
                for param in parameters:
                    if isinstance(param, dict):
                        param_name = param.get('name')
                        param_value = param.get('value')
                        if param_name and param_value is not None:
                            param_dict[param_name] = param_value

        logger.info(f"Extracted parameters: {param_dict}")
        logger.info(f"API Path: {api_path}")

        # Route based on API path
        if api_path == '/getAdvice':
            return get_advice(param_dict, api_path, http_method)
        elif api_path == '/subscribeToAgent':
            return subscribe_to_agent(param_dict, api_path, http_method)
        else:
            return create_bedrock_response("ERROR", {"error": f"Unknown API path: {api_path}"}, api_path, http_method)

    except Exception as e:
        logger.error(f"Error: {str(e)}")
        return create_bedrock_response("ERROR", {"error": str(e)})

def get_advice(params, api_path='/getAdvice', http_method='POST'):
    """Call the existing advice API endpoint"""
    try:
        logger.info(f"get_advice called with params: {params}")

        # Get required parameters
        user_id = params.get('user_id')
        question = params.get('question')
        context = params.get('context', '')

        logger.info(f"Extracted - user_id: '{user_id}', question: '{question}', context: '{context}'")

        if not user_id or not question:
            logger.error(f"Missing required parameters - user_id: {bool(user_id)}, question: {bool(question)}")
            return create_bedrock_response("ERROR", {"error": "user_id and question are required"}, api_path, http_method)

        # Your deployed API endpoint
        api_url = os.environ.get('ADVICE_API_URL', 'https://your-api-id.execute-api.us-east-1.amazonaws.com/dev/advice')

        # Call your existing advice API
        payload = {
            "user_id": user_id,
            "question": question,
            "context": context
        }

        response = http.request(
            'POST',
            api_url,
            body=json.dumps(payload).encode('utf-8'),
            headers={'Content-Type': 'application/json'},
            timeout=30
        )

        if response.status == 200:
            data = json.loads(response.data.decode('utf-8'))

            # Extract advice from your API response format
            if data.get('status') == 'success':
                advice = data.get('data', {}).get('advice', 'No advice available')
                return create_bedrock_response("SUCCESS", {
                    "advice": advice,
                    "user_id": user_id
                }, api_path, http_method)
            else:
                # Handle error response from your API
                error = data.get('error', {})
                return create_bedrock_response("ERROR", {
                    "error": error.get('message', 'API returned error'),
                    "code": error.get('code', 'UNKNOWN_ERROR')
                }, api_path, http_method)
        else:
            return create_bedrock_response("ERROR", {
                "error": f"API returned status {response.status}",
                "details": response.data.decode('utf-8')
            }, api_path, http_method)

    except Exception as e:
        logger.error(f"Error calling advice API: {str(e)}")
        return create_bedrock_response("ERROR", {"error": f"Failed to get advice: {str(e)}"}, api_path, http_method)

def subscribe_to_agent(params, api_path='/subscribeToAgent', http_method='POST'):
    """Call the subscription API endpoint"""
    try:
        # Get required parameters
        user_id = params.get('user_id')
        agent_name = params.get('agent_name', 'advice-agent')  # Default to advice-agent

        if not user_id:
            return create_bedrock_response("ERROR", {"error": "user_id is required"}, api_path, http_method)

        if not agent_name:
            return create_bedrock_response("ERROR", {"error": "agent_name is required"}, api_path, http_method)

        # Get the subscription API URL - using the main API base URL
        api_base = os.environ.get('ADVICE_API_URL', 'https://your-api-id.execute-api.us-east-1.amazonaws.com/dev')
        # Remove /advice if it's in the URL and add /subscribe/{user_id}
        if api_base.endswith('/advice'):
            api_base = api_base[:-7]  # Remove '/advice'
        subscription_url = f"{api_base}/subscribe/{user_id}"

        # Call the subscription API
        payload = {
            "agent_name": agent_name
        }

        logger.info(f"Calling subscription API: {subscription_url}")

        response = http.request(
            'POST',
            subscription_url,
            body=json.dumps(payload).encode('utf-8'),
            headers={'Content-Type': 'application/json'},
            timeout=15
        )

        if response.status == 200:
            data = json.loads(response.data.decode('utf-8'))

            # Extract subscription result from API response format
            if data.get('status') == 'success':
                subscription_data = data.get('data', {})
                return create_bedrock_response("SUCCESS", {
                    "message": subscription_data.get('message', f'Successfully subscribed {user_id} to {agent_name}'),
                    "user_id": user_id,
                    "agent_name": agent_name
                }, api_path, http_method)
            else:
                # Handle error response from subscription API
                error = data.get('error', {})
                return create_bedrock_response("ERROR", {
                    "error": error.get('message', 'Subscription failed'),
                    "code": error.get('code', 'SUBSCRIPTION_ERROR'),
                    "user_id": user_id,
                    "agent_name": agent_name
                }, api_path, http_method)

        elif response.status == 403:
            # Handle permission-related errors (user not found, etc.)
            try:
                error_data = json.loads(response.data.decode('utf-8'))
                error_info = error_data.get('error', {})
                return create_bedrock_response("ERROR", {
                    "error": error_info.get('message', 'Permission denied'),
                    "code": error_info.get('code', 'PERMISSION_DENIED'),
                    "user_id": user_id,
                    "agent_name": agent_name
                }, api_path, http_method)
            except json.JSONDecodeError:
                return create_bedrock_response("ERROR", {
                    "error": "Permission denied",
                    "code": "PERMISSION_DENIED",
                    "user_id": user_id,
                    "agent_name": agent_name
                }, api_path, http_method)

        else:
            return create_bedrock_response("ERROR", {
                "error": f"Subscription API returned status {response.status}",
                "details": response.data.decode('utf-8'),
                "user_id": user_id,
                "agent_name": agent_name
            }, api_path, http_method)

    except Exception as e:
        logger.error(f"Error calling subscription API: {str(e)}")
        return create_bedrock_response("ERROR", {"error": f"Failed to subscribe: {str(e)}"}, api_path, http_method)

def create_bedrock_response(status, data, api_path='/getAdvice', http_method='POST'):
    """Create properly formatted Bedrock Agent response"""
    return {
        'messageVersion': '1.0',
        'response': {
            'actionGroup': 'advice-proxy',
            'apiPath': api_path,
            'httpMethod': http_method,
            'httpStatusCode': 200,
            'responseBody': {
                'application/json': {
                    'body': json.dumps({
                        'status': status,
                        'result': data
                    })
                }
            }
        }
    }