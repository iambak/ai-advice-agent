# AWS Lambda deployment version
# This is the main handler file for AWS deployment

import sys
import os

# Add the src directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from advice_agent import lambda_handler

# Re-export the handler for AWS Lambda
lambda_handler = lambda_handler