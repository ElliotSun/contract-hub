import os
import json
from abc import ABC, abstractmethod

class BaseLLMProvider(ABC):
    @abstractmethod
    def generate_json(self, system_prompt: str, user_prompt: str, temperature: float = 0.0) -> dict:
        """
        Generates a JSON response from the LLM.
        """
        pass

class OpenAILLMProvider(BaseLLMProvider):
    def __init__(self):
        # Only import openai when instantiated so we don't hard fail if missing
        import openai

        self.api_key = os.environ.get("LLM_API_KEY", "")
        self.base_url = os.environ.get("LLM_BASE_URL", None)
        self.model_name = os.environ.get("LLM_MODEL_NAME", "gpt-4-turbo")

        self.client = openai.Client(
            api_key=self.api_key,
            base_url=self.base_url
        )

    def generate_json(self, system_prompt: str, user_prompt: str, temperature: float = 0.0) -> dict:
        response = self.client.chat.completions.create(
            model=self.model_name,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=temperature
        )
        content = response.choices[0].message.content
        if not content:
            return {}
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            return {}
