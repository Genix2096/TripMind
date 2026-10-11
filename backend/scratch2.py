from google.genai import types

schema_dict_anyof = {
    "type": "object",
    "properties": {
        "amount": {
            "anyOf": [
                {
                    "type": "number",
                    "exclusiveMinimum": 0.0
                },
                {
                    "type": "string"
                }
            ]
        }
    }
}

try:
    config = types.GenerateContentConfig(response_mime_type="application/json", response_schema=schema_dict_anyof)
    print("Schema accepted!")
except Exception as e:
    print("Error:", e)
