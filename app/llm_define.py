# huggingface_chat_llm.py

from langchain.llms.base import LLM
import ollama
from typing import Optional, List,Any,Dict
import requests
from langchain_core.runnables import Runnable


class HuggingFaceChatLLM(LLM):
    model_name: str
    huggingface_api_token: str

    @property
    def _llm_type(self) -> str:
        return "huggingface-chat-api"

    def _call(self, prompt: str, stop: Optional[List[str]] = None) -> str:
        api_url ="https://router.huggingface.co/v1/chat/completions"

        headers = {
            "Authorization": f"Bearer {self.huggingface_api_token}",
            "Content-Type": "application/json"
        }

        payload = {
            "model": self.model_name,
            "messages": [
                {"role": "system", "content": "You are a helpful assistant who reasons step-by-step and uses tools when needed."},
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.7,
            "max_tokens": 512
        }

        response = requests.post(api_url, headers=headers, json=payload)
        if response.status_code == 200:
            result = response.json()
            return result["choices"][0]["message"]["content"]
        else:
            raise Exception(f"API call failed: {response.status_code}, {response.text}")



class OllamaLLM(Runnable):
    def __init__(self, model_name: str = "deepseek-r1:1.5b", base_url: str = "http://localhost:11434"):
        self.model_name = model_name
        self.base_url = base_url
        self.client = ollama.Client(host=base_url)

    def invoke(self, input: Any, config: Optional[Dict] = None, **kwargs) -> str:
        """Compatible with LangChain AgentExecutor and Ollama."""
        try:
            # Convert input into prompt string
            if isinstance(input, list) and len(input) > 0:
                if hasattr(input[0], 'content'):
                    prompt = input[0].content
                else:
                    prompt = input[0].get('content', str(input[0]))
            else:
                prompt = str(input)

            # Remove unsupported kwargs (like `stop`)
            supported_args = ["temperature", "top_p", "num_predict"]
            filtered_kwargs = {k: v for k, v in kwargs.items() if k in supported_args}

            response = self.client.generate(
                model=self.model_name,
                prompt=prompt,
                stream=False,
                **filtered_kwargs
            )
            return response['response']

        except Exception as e:
            return f"Error: {str(e)}"

    def __call__(self, input: Any, **kwargs) -> str:
        return self.invoke(input, **kwargs)
