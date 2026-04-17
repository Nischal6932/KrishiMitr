from flask import Flask
import sys
import os

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import the Flask app
from app import app

# Handler for Netlify Functions
def handler(event, context):
    from werkzeug.serving import run_wsgi
    from io import BytesIO
    import json
    
    # Convert Netlify event to WSGI environ
    method = event.get('httpMethod', 'GET')
    path = event.get('path', '/')
    headers = event.get('headers', {})
    body = event.get('body', '') or ''
    query_params = event.get('queryStringParameters', {}) or {}
    
    # Build query string
    query_string = '&'.join([f"{k}={v}" for k, v in query_params.items()]) if query_params else ''
    
    environ = {
        'REQUEST_METHOD': method,
        'PATH_INFO': path,
        'QUERY_STRING': query_string,
        'CONTENT_TYPE': headers.get('content-type', ''),
        'CONTENT_LENGTH': str(len(body)) if body else '0',
        'HTTP_HOST': headers.get('host', 'localhost'),
        'SERVER_NAME': 'localhost',
        'SERVER_PORT': '80',
        'HTTP_': '',
        'wsgi.version': (1, 0),
        'wsgi.url_scheme': 'https',
        'wsgi.input': BytesIO(body.encode() if isinstance(body, str) else body),
        'wsgi.errors': sys.stderr,
        'wsgi.multithread': False,
        'wsgi.multiprocess': False,
        'wsgi.run_once': False,
    }
    
    # Add headers
    for key, value in headers.items():
        key = key.upper().replace('-', '_')
        if key not in ('CONTENT_TYPE', 'CONTENT_LENGTH'):
            environ[f'HTTP_{key}'] = value
    
    # Response handler
    response_body = []
    response_status = None
    response_headers = []
    
    def start_response(status, headers):
        nonlocal response_status, response_headers
        response_status = status
        response_headers = headers
        return response_body.append
    
    # Call Flask app
    response = app(environ, start_response)
    
    # Build response
    body_bytes = b''.join(response)
    
    # Determine if response is binary
    try:
        body_str = body_bytes.decode('utf-8')
        is_base64 = False
    except:
        import base64
        body_str = base64.b64encode(body_bytes).decode('utf-8')
        is_base64 = True
    
    return {
        'statusCode': int(response_status.split()[0]),
        'headers': {k: v for k, v in response_headers},
        'body': body_str,
        'isBase64Encoded': is_base64
    }
