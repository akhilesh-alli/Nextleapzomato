"""
src/llm/engine.py
-----------------
Abstracted LLM backend interface supporting:
  - OpenAI (GPT-4o-mini, GPT-4, etc.)
  - Google Gemini (gemini-1.5-flash, gemini-1.5-pro, etc.)
  - Ollama (local open-source models like llama3, mistral)

Implements:
  - EC-301: Fail fast with descriptive error if API key is missing
  - EC-302: Timeout handling (default 30s) + retry logic
  - EC-303: Rate limit (429) exponential backoff retries (max 2 retries)
  - EC-304: Empty response detection
"""

import json
import logging
import os
import time
from typing import Optional

logger = logging.getLogger(__name__)


class LLMError(Exception):
    """Base exception for LLM engine errors."""
    pass


class LLMAuthenticationError(LLMError):
    """Raised when API credentials are missing or invalid (EC-301)."""
    pass


class LLMTimeoutError(LLMError):
    """Raised when LLM call exceeds configured timeout (EC-302)."""
    pass


class LLMRateLimitError(LLMError):
    """Raised when LLM provider rate limits the request (EC-303)."""
    pass


class LLMEmptyResponseError(LLMError):
    """Raised when LLM returns an empty string (EC-304)."""
    pass


class LLMEngine:
    """
    Unified LLM Client providing a single `query(prompt)` interface.

    Configuration defaults are read from `config.settings`, but can be
    overridden per instance.
    """

    def __init__(
        self,
        provider: Optional[str] = None,
        model: Optional[str] = None,
        api_key: Optional[str] = None,
        timeout: Optional[int] = None,
        max_retries: Optional[int] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> None:
        from config.settings import (
            LLM_PROVIDER,
            LLM_MODEL,
            GROQ_API_KEY,
            OPENAI_API_KEY,
            GEMINI_API_KEY,
            LLM_TIMEOUT_SECONDS,
            LLM_MAX_RETRIES,
            LLM_TEMPERATURE,
            LLM_MAX_TOKENS,
        )

        self.provider = (provider or LLM_PROVIDER).lower()
        self.model = model or LLM_MODEL
        self.timeout = timeout if timeout is not None else LLM_TIMEOUT_SECONDS
        self.max_retries = max_retries if max_retries is not None else LLM_MAX_RETRIES
        self.temperature = temperature if temperature is not None else LLM_TEMPERATURE
        self.max_tokens = max_tokens if max_tokens is not None else LLM_MAX_TOKENS

        # Resolve API keys
        if self.provider == "groq":
            self.api_key = api_key if api_key is not None else (os.getenv("GROQ_API_KEY") or GROQ_API_KEY)
        elif self.provider == "openai":
            self.api_key = api_key if api_key is not None else (os.getenv("OPENAI_API_KEY") or OPENAI_API_KEY)
        elif self.provider == "gemini":
            self.api_key = api_key if api_key is not None else (os.getenv("GEMINI_API_KEY") or GEMINI_API_KEY)
        else:
            self.api_key = api_key if api_key is not None else ""

        self._validate_credentials()

    def _validate_credentials(self) -> None:
        """EC-301: Check API key presence before invocation."""
        if self.provider == "groq" and not self.api_key:
            raise LLMAuthenticationError(
                "[EC-301] Groq API key is missing. Set GROQ_API_KEY in your .env file "
                "or pass api_key to LLMEngine."
            )
        if self.provider == "openai" and not self.api_key:
            raise LLMAuthenticationError(
                "[EC-301] OpenAI API key is missing. Set OPENAI_API_KEY in your .env file "
                "or pass api_key to LLMEngine."
            )
        if self.provider == "gemini" and not self.api_key:
            raise LLMAuthenticationError(
                "[EC-301] Gemini API key is missing. Set GEMINI_API_KEY in your .env file "
                "or pass api_key to LLMEngine."
            )

    def query(self, prompt: str, system_prompt: Optional[str] = None) -> str:
        """
        Execute an LLM prompt with automatic retry and backoff.

        Parameters
        ----------
        prompt : str
            The formatted user/data prompt.
        system_prompt : Optional[str]
            Optional system instructions (defaults to recommendation expert persona).

        Returns
        -------
        str
            Raw text output from the model.
        """
        if not prompt or not prompt.strip():
            raise ValueError("Prompt cannot be empty.")

        sys_prompt = system_prompt or (
            "You are a professional restaurant recommendation assistant. "
            "Respond in English only. Follow all formatting constraints strictly."
        )

        attempts = 0
        last_exception = None

        while attempts <= self.max_retries:
            try:
                logger.info(
                    "Querying LLM (provider=%s, model=%s, attempt=%d/%d)...",
                    self.provider,
                    self.model,
                    attempts + 1,
                    self.max_retries + 1,
                )
                if self.provider == "groq":
                    response = self._query_groq(prompt, sys_prompt)
                elif self.provider == "openai":
                    response = self._query_openai(prompt, sys_prompt)
                elif self.provider == "gemini":
                    response = self._query_gemini(prompt, sys_prompt)
                elif self.provider == "ollama":
                    response = self._query_ollama(prompt, sys_prompt)
                else:
                    raise ValueError(f"Unsupported LLM provider: {self.provider}")

                # EC-304: Empty string validation
                if not response or not response.strip():
                    raise LLMEmptyResponseError(
                        "[EC-304] LLM call succeeded but returned an empty or whitespace response."
                    )

                return response.strip()

            except (LLMTimeoutError, LLMRateLimitError) as exc:
                last_exception = exc
                attempts += 1
                if attempts <= self.max_retries:
                    # EC-303: Exponential backoff
                    wait_time = 2 ** attempts
                    logger.warning(
                        "LLM query error: %s. Retrying in %ds (attempt %d/%d)...",
                        exc,
                        wait_time,
                        attempts,
                        self.max_retries,
                    )
                    time.sleep(wait_time)
                else:
                    logger.error("LLM retries exhausted. Last error: %s", exc)
                    raise last_exception

            except Exception as exc:
                # Direct re-raise for non-retryable errors (auth, schema, etc.)
                logger.error("Non-retryable LLM error: %s", exc)
                raise

        raise last_exception or LLMError("LLM query failed after maximum retries.")

    # ── Provider Implementations ─────────────────────────────────────────────

    def _query_groq(self, prompt: str, system_prompt: str) -> str:
        """Call Groq API using groq SDK, openai client, or direct REST API."""
        # Method 1: Try official groq package if installed
        try:
            import groq
            client = groq.Groq(api_key=self.api_key, timeout=self.timeout)
            try:
                response = client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": prompt},
                    ],
                    temperature=self.temperature,
                    max_tokens=self.max_tokens,
                )
                return response.choices[0].message.content or ""
            except groq.APITimeoutError as exc:
                raise LLMTimeoutError(f"[EC-302] Groq request timed out ({self.timeout}s): {exc}") from exc
            except groq.RateLimitError as exc:
                raise LLMRateLimitError(f"[EC-303] Groq rate limit exceeded (429): {exc}") from exc
            except groq.AuthenticationError as exc:
                raise LLMAuthenticationError(f"[EC-301] Invalid Groq credentials: {exc}") from exc
            except Exception as exc:
                raise LLMError(f"Groq API call failed: {exc}") from exc
        except ImportError:
            pass

        # Method 2: Try OpenAI SDK pointed to Groq endpoint
        try:
            import openai
            client = openai.OpenAI(
                api_key=self.api_key,
                base_url="https://api.groq.com/openai/v1",
                timeout=self.timeout,
            )
            try:
                response = client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": prompt},
                    ],
                    temperature=self.temperature,
                    max_tokens=self.max_tokens,
                )
                return response.choices[0].message.content or ""
            except openai.APITimeoutError as exc:
                raise LLMTimeoutError(f"[EC-302] Groq request timed out ({self.timeout}s): {exc}") from exc
            except openai.RateLimitError as exc:
                raise LLMRateLimitError(f"[EC-303] Groq rate limit exceeded (429): {exc}") from exc
            except openai.AuthenticationError as exc:
                raise LLMAuthenticationError(f"[EC-301] Invalid Groq credentials: {exc}") from exc
            except Exception as exc:
                raise LLMError(f"Groq API call via OpenAI client failed: {exc}") from exc
        except ImportError:
            pass

        # Method 3: Standard library urllib HTTP REST request (zero extra dependencies required)
        import urllib.request
        import urllib.error

        url = "https://api.groq.com/openai/v1/chat/completions"
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt},
            ],
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
        }
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=data,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}",
            },
            method="POST",
        )

        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                body = json.loads(resp.read().decode("utf-8"))
                choices = body.get("choices", [])
                if choices:
                    return choices[0].get("message", {}).get("content", "")
                return ""
        except urllib.error.HTTPError as exc:
            if exc.code == 429:
                raise LLMRateLimitError(f"[EC-303] Groq rate limit exceeded (429): {exc}") from exc
            if exc.code == 401:
                raise LLMAuthenticationError(f"[EC-301] Invalid Groq API key: {exc}") from exc
            raise LLMError(f"Groq REST API HTTP {exc.code} error: {exc.reason}") from exc
        except (TimeoutError, urllib.error.URLError) as exc:
            if isinstance(exc, TimeoutError) or "timed out" in str(exc).lower():
                raise LLMTimeoutError(f"[EC-302] Groq request timed out ({self.timeout}s): {exc}") from exc
            raise LLMError(f"Failed to connect to Groq API: {exc}") from exc

    def _query_openai(self, prompt: str, system_prompt: str) -> str:
        """Call OpenAI chat completion API."""
        try:
            import openai
        except ImportError:
            raise ImportError(
                "The 'openai' package is not installed. Run: pip install openai"
            )

        client = openai.OpenAI(api_key=self.api_key, timeout=self.timeout)

        try:
            response = client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": prompt},
                ],
                temperature=self.temperature,
                max_tokens=self.max_tokens,
            )
            return response.choices[0].message.content or ""
        except openai.APITimeoutError as exc:
            raise LLMTimeoutError(f"[EC-302] OpenAI request timed out ({self.timeout}s): {exc}") from exc
        except openai.RateLimitError as exc:
            raise LLMRateLimitError(f"[EC-303] OpenAI rate limit exceeded (429): {exc}") from exc
        except openai.AuthenticationError as exc:
            raise LLMAuthenticationError(f"[EC-301] Invalid OpenAI credentials: {exc}") from exc
        except Exception as exc:
            raise LLMError(f"OpenAI API call failed: {exc}") from exc

    def _query_gemini(self, prompt: str, system_prompt: str) -> str:
        """Call Google Gemini API."""
        try:
            import google.generativeai as genai
        except ImportError:
            raise ImportError(
                "The 'google-generativeai' package is not installed. Run: pip install google-generativeai"
            )

        try:
            genai.configure(api_key=self.api_key)
            model = genai.GenerativeModel(
                model_name=self.model,
                system_instruction=system_prompt,
                generation_config={
                    "temperature": self.temperature,
                    "max_output_tokens": self.max_tokens,
                },
            )
            # Timeout support via request options
            response = model.generate_content(
                prompt,
                request_options={"timeout": self.timeout},
            )
            return response.text or ""
        except Exception as exc:
            msg = str(exc)
            if "timeout" in msg.lower() or "deadline" in msg.lower():
                raise LLMTimeoutError(f"[EC-302] Gemini request timed out: {exc}") from exc
            if "429" in msg or "quota" in msg.lower() or "rate" in msg.lower():
                raise LLMRateLimitError(f"[EC-303] Gemini rate limit exceeded: {exc}") from exc
            if "api key" in msg.lower() or "permission" in msg.lower():
                raise LLMAuthenticationError(f"[EC-301] Invalid Gemini credentials: {exc}") from exc
            raise LLMError(f"Gemini API call failed: {exc}") from exc

    def _query_ollama(self, prompt: str, system_prompt: str) -> str:
        """Call local Ollama server via HTTP REST API."""
        import urllib.request
        import urllib.error

        host = os.getenv("OLLAMA_HOST", "http://localhost:11434")
        url = f"{host}/api/chat"

        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt},
            ],
            "options": {
                "temperature": self.temperature,
                "num_predict": self.max_tokens,
            },
            "stream": False,
        }

        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                body = json.loads(resp.read().decode("utf-8"))
                return body.get("message", {}).get("content", "")
        except urllib.error.HTTPError as exc:
            if exc.code == 429:
                raise LLMRateLimitError(f"[EC-303] Ollama rate limit exceeded: {exc}") from exc
            raise LLMError(f"Ollama server HTTP {exc.code} error: {exc.reason}") from exc
        except (TimeoutError, urllib.error.URLError) as exc:
            if isinstance(exc, TimeoutError) or "timed out" in str(exc).lower():
                raise LLMTimeoutError(f"[EC-302] Ollama request timed out ({self.timeout}s): {exc}") from exc
            raise LLMError(f"Failed to connect to Ollama at {host}. Is Ollama running? Error: {exc}") from exc
