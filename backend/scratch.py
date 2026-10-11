from google.genai import types

# Test OpenAPI 3.0 style exclusiveMinimum
schema_dict = {
    "type": "object",
    "properties": {
        "amount": {
            "type": "number",
            "minimum": 0.0,
            "exclusiveMinimum": True
        }
    }
}

try:
    config = types.GenerateContentConfig(response_mime_type="application/json", response_schema=schema_dict)
    print("OpenAPI 3.0 exclusiveMinimum (bool) accepted!")
except Exception as e:
    print("Error with bool:", e)

# Test OpenAPI 3.1 / Draft 6 style
schema_dict_num = {
    "type": "object",
    "properties": {
        "amount": {
            "type": "number",
            "exclusiveMinimum": 0.0
        }
    }
}

try:
    config2 = types.GenerateContentConfig(response_mime_type="application/json", response_schema=schema_dict_num)
    print("OpenAPI 3.1 exclusiveMinimum (number) accepted!")
except Exception as e:
    print("Error with number:", e)
