import base64
import json


def build_gemini_file_payload(*, file_uri, mime_type, text_prompt):
    return {
        "contents": [
            {
                "role": "user",
                "parts": [
                    {"fileData": {"mimeType": mime_type, "fileUri": file_uri}},
                    {"text": text_prompt},
                ],
            }
        ]
    }


def build_gemini_inline_image_payload(*, image_bytes, text_prompt, mime_type="image/png"):
    return {
        "contents": [
            {
                "role": "user",
                "parts": [
                    {
                        "inlineData": {
                            "mimeType": mime_type,
                            "data": base64.b64encode(image_bytes).decode("ascii"),
                        }
                    },
                    {"text": text_prompt},
                ],
            }
        ]
    }


def extract_gemini_text_from_data(data, *, error_prefix):
    data = data or {}
    if "error" in data:
        message = data.get("error", {}).get("message") or data["error"]
        raise RuntimeError(f"{error_prefix}: {message}")
    parts = (
        data.get("candidates", [{}])[0]
        .get("content", {})
        .get("parts", [])
    )
    return "".join(part.get("text", "") for part in parts if isinstance(part, dict))


def extract_gemini_text_from_response_bytes(response_bytes, *, error_prefix):
    data = json.loads(response_bytes.decode("utf-8", errors="replace") or "{}")
    return extract_gemini_text_from_data(data, error_prefix=error_prefix)
