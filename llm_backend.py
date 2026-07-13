"""
llm_backend.py
FinAudit AI doesn't need embeddings/retrieval -- each transaction is analyzed
directly against its customer's own history, so this only dispatches chat
calls between local Ollama and Gemini API, based on config.py.
"""

import config


def chat(system_prompt, user_prompt):
    if config.LLM_BACKEND == "gemini":
        return _gemini_chat(system_prompt, user_prompt)
    return _ollama_chat(system_prompt, user_prompt)


def _gemini_chat(system_prompt, user_prompt, max_retries=3):
    from google import genai
    from google.genai import types
    from google.genai import errors
    import time

    if not config.GEMINI_API_KEY:
        raise RuntimeError(
            "GEMINI_API_KEY is not set. Get a free key from "
            "https://aistudio.google.com/apikey and set it as an env var."
        )

    client = genai.Client(api_key=config.GEMINI_API_KEY)

    for attempt in range(max_retries):
        try:
            response = client.models.generate_content(
                model=config.GEMINI_MODEL,
                contents=user_prompt,
                config=types.GenerateContentConfig(system_instruction=system_prompt),
            )
            return response.text
        except errors.ServerError as e:
            # 503 (overloaded) / 500 -- Google's side, transient. Retry with
            # backoff. Anything else (auth, bad request) raises immediately.
            if attempt == max_retries - 1:
                raise
            wait = 2 ** attempt  # 1s, 2s, 4s
            print(f"  (Gemini server busy, retrying in {wait}s... "
                  f"attempt {attempt + 1}/{max_retries})")
            time.sleep(wait)


def _ollama_chat(system_prompt, user_prompt):
    import ollama
    response = ollama.chat(
        model=config.OLLAMA_MODEL,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
    )
    return response["message"]["content"]