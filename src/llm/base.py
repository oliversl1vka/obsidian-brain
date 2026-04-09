from openai import AsyncOpenAI, APITimeoutError
import asyncio
from src.config import settings
from src.utils.logging import log_api_call
import logging

logger = logging.getLogger(__name__)

class LLMBase:
    def __init__(self):
        self.client = AsyncOpenAI(api_key=settings.openai_api_key, timeout=60.0)
        self.model = settings.model_name

    def _load_template(self, template_path: str, context: dict | None = None) -> str:
        try:
            with open(template_path, "r", encoding="utf-8") as f:
                template = f.read()
        except FileNotFoundError:
            logger.error(f"Prompt template not found: {template_path}")
            raise

        if context is None:
            return template
        return template.format(**context)
        
    async def generate_response(
        self,
        prompt_template_path: str,
        context: dict,
        max_tokens: int = 500,
        system_prompt_template_path: str | None = None,
        system_context: dict | None = None,
    ) -> str:
        """Loads prompt templates, formats them, and calls the OpenAI API."""
        prompt = self._load_template(prompt_template_path, context)
        system_prompt = None
        if system_prompt_template_path:
            system_prompt = self._load_template(system_prompt_template_path, system_context or {})
        
        # Truncate prompt if it risks exceeding context window (~100k chars ≈ ~25k tokens)
        max_prompt_chars = 100_000
        if len(prompt) > max_prompt_chars:
            logger.warning(f"Prompt truncated from {len(prompt)} to {max_prompt_chars} chars")
            prompt = prompt[:max_prompt_chars] + "\n\n[Content truncated due to length]"

        if system_prompt and len(system_prompt) > max_prompt_chars:
            logger.warning(f"System prompt truncated from {len(system_prompt)} to {max_prompt_chars} chars")
            system_prompt = system_prompt[:max_prompt_chars] + "\n\n[Content truncated due to length]"
        
        try:
            response = await self._call_openai(prompt, max_tokens, system_prompt)
            
            result_text = response.choices[0].message.content.strip()
            
            # Log the call
            log_api_call(
                model=self.model,
                prompt=((system_prompt + "\n\n---\n\n") if system_prompt else "") + prompt,
                response=result_text,
                prompt_tokens=response.usage.prompt_tokens,
                completion_tokens=response.usage.completion_tokens
            )
            
            return result_text
            
        except Exception as e:
            logger.error(f"OpenAI API Error: {e}")
            raise

    async def _call_openai(self, prompt: str, max_tokens: int, system_prompt: str | None = None):
        """Call OpenAI API with one retry on timeout."""
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})
        for attempt in range(2):
            try:
                return await self.client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    max_completion_tokens=max_tokens
                )
            except APITimeoutError:
                if attempt == 0:
                    logger.warning("OpenAI API timeout, retrying once...")
                    await asyncio.sleep(2)
                else:
                    raise
