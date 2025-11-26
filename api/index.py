import json

# Vercel expects a "handler" function
def handler(request):
    try:
        # Example: process GET or POST
        method = request.get("method", "GET")
        
        if method == "GET":
            response_data = {
                "message": "Hello! Your GET request worked.",
            }
        elif method == "POST":
            body = request.get("body")
            # If JSON, parse it
            try:
                body_data = json.loads(body) if body else {}
            except json.JSONDecodeError:
                body_data = {}
            
            response_data = {
                "message": "POST request received.",
                "received": body_data
            }
        else:
            response_data = {"message": f"{method} not supported."}

        return {
            "statusCode": 200,
            "body": json.dumps(response_data),
            "headers": {"Content-Type": "application/json"}
        }

    except Exception as e:
        # Always return 500 on unexpected errors
        return {
            "statusCode": 500,
            "body": json.dumps({"error": str(e)}),
            "headers": {"Content-Type": "application/json"}
        }
