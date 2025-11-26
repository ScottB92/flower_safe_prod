import json

def handler(request):
    try:
        return {
            "statusCode": 200,
            "body": json.dumps({"message": "Hello from Vercel Python!"}),
            "headers": {"Content-Type": "application/json"}
        }
    except Exception as e:
        return {
            "statusCode": 500,
            "body": json.dumps({"error": str(e)}),
            "headers": {"Content-Type": "application/json"}
        }
