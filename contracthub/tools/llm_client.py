import os
import json
from abc import ABC, abstractmethod


class BaseLLMProvider(ABC):
    @abstractmethod
    def generate_json(
        self, system_prompt: str, user_prompt: str, temperature: float = 0.0
    ) -> dict:
        """
        Generates a JSON response from the LLM.
        """
        pass


class OpenAILLMProvider(BaseLLMProvider):
    def __init__(self):
        # Only import litellm when instantiated so we don't hard fail if missing

        self.api_key = os.environ.get("LLM_API_KEY", "")
        self.base_url = os.environ.get("LLM_BASE_URL", None)
        self.model_name = os.environ.get("LLM_MODEL_NAME", "gpt-4-turbo")

    def generate_json(
        self, system_prompt: str, user_prompt: str, temperature: float = 0.0
    ) -> dict:
        import time
        from litellm import completion

        max_retries = 3
        delay = 2.0

        for attempt in range(max_retries + 1):
            try:
                # Prepare arguments
                kwargs = {
                    "model": self.model_name,
                    "response_format": {"type": "json_object"},
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                    "temperature": temperature,
                }
                if self.api_key:
                    kwargs["api_key"] = self.api_key
                if self.base_url:
                    kwargs["api_base"] = self.base_url

                response = completion(**kwargs)
                content = response.choices[0].message.content
                if not content:
                    return {}
                try:
                    return json.loads(content)
                except json.JSONDecodeError:
                    return {}
            except Exception as e:
                if attempt == max_retries:
                    raise e
                time.sleep(delay)
                delay *= 2
