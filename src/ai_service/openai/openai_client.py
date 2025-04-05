from openai import OpenAI
from typing import List, Dict, Any, Optional, Union, Tuple

class OpenAIClient:
    """
    A reusable base class for interacting with the OpenAI API.
    """
    
    def __init__(self, api_key: str, default_model: str = "gpt-4o", default_temperature: float = 0.7):
        """
        Initialize the OpenAI client.
        
        Args:
            api_key: OpenAI API key
            default_model: Default model to use for API calls
            default_temperature: Default temperature parameter (0.0 to 1.0)
        """
        self.client = OpenAI(api_key=api_key)
        self.default_model = default_model
        self.default_temperature = default_temperature
    
    def create_chat_completion(
        self,
        user_content: Union[str, List[Dict[str, Any]]],
        system_prompt: Optional[str] = None,
        model: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        top_p: Optional[float] = None,
        frequency_penalty: Optional[float] = None,
        presence_penalty: Optional[float] = None,
        stop: Optional[Union[str, List[str]]] = None,
        assistant_content: Optional[str] = None,
        seed: Optional[int] = None,
        response_format: Optional[Dict[str, str]] = None,
        return_usage: bool = False
    ) -> Union[str, Tuple[str, Dict[str, Any]]]:
        """
        Create a chat completion with the OpenAI API.
        
        Args:
            user_content: User message content (string or list of content parts)
            system_prompt: Optional system prompt
            model: Model to use (defaults to instance default_model)
            temperature: Controls randomness (0.0 to 1.0)
            max_tokens: Maximum number of tokens to generate
            top_p: Controls diversity via nucleus sampling
            frequency_penalty: Penalizes frequent tokens (-2.0 to 2.0)
            presence_penalty: Penalizes tokens already present (-2.0 to 2.0)
            stop: Sequence(s) where the API will stop generating further tokens
            assistant_content: Optional prior assistant message
            seed: Optional seed for deterministic results
            response_format: Optional format specifier (e.g., {"type": "json_object"})
            return_usage: If True, returns token usage information along with the response
            
        Returns:
            If return_usage is False: The generated completion text (str)
            If return_usage is True: A tuple (str, Dict) containing the completion text and token usage info
        """
        messages = []
        
        # Add system message if provided
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        
        # Add assistant message if provided (for continuing conversations)
        if assistant_content:
            messages.append({"role": "assistant", "content": assistant_content})
        
        # Add user message
        messages.append({"role": "user", "content": user_content})
        
        # Prepare parameters, using defaults for None values
        params = {
            "model": model or self.default_model,
            "messages": messages,
            "temperature": temperature if temperature is not None else self.default_temperature,
        }
        
        # Add optional parameters only if they are provided
        if max_tokens is not None:
            params["max_tokens"] = max_tokens
        if top_p is not None:
            params["top_p"] = top_p
        if frequency_penalty is not None:
            params["frequency_penalty"] = frequency_penalty
        if presence_penalty is not None:
            params["presence_penalty"] = presence_penalty
        if stop is not None:
            params["stop"] = stop
        if seed is not None:
            params["seed"] = seed
        if response_format is not None:
            params["response_format"] = response_format
        
        try:
            completion = self.client.chat.completions.create(**params)
            response_content = completion.choices[0].message.content
            
            if return_usage:
                # Extract usage statistics
                usage_data = {
                    "prompt_tokens": completion.usage.prompt_tokens,
                    "completion_tokens": completion.usage.completion_tokens,
                    "total_tokens": completion.usage.total_tokens
                }
                
                # Add detailed token usage if available
                if hasattr(completion.usage, "completion_tokens_details"):
                    usage_data["completion_tokens_details"] = {
                        "accepted_prediction_tokens": completion.usage.completion_tokens_details.accepted_prediction_tokens,
                        "audio_tokens": completion.usage.completion_tokens_details.audio_tokens,
                        "reasoning_tokens": completion.usage.completion_tokens_details.reasoning_tokens,
                        "rejected_prediction_tokens": completion.usage.completion_tokens_details.rejected_prediction_tokens
                    }
                
                if hasattr(completion.usage, "prompt_tokens_details"):
                    usage_data["prompt_tokens_details"] = {
                        "audio_tokens": completion.usage.prompt_tokens_details.audio_tokens,
                        "cached_tokens": completion.usage.prompt_tokens_details.cached_tokens
                    }
                
                return response_content, usage_data
            else:
                return response_content
                
        except Exception as e:
            error_msg = f"Error calling OpenAI API: {e}"
            print(error_msg)
            
            if return_usage:
                return error_msg, {}
            else:
                return error_msg