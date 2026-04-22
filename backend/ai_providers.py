import asyncio

PROVIDERS = {
    'gemini': {
        'name': 'Google Gemini',
        'models': [
            'gemini-2.5-pro',
            'gemini-2.5-flash',
            'gemini-2.0-flash',
            'gemini-1.5-pro',
            'gemini-1.5-flash',
        ],
    },
    'claude': {
        'name': 'Anthropic Claude',
        'models': [
            'claude-opus-4-7',
            'claude-sonnet-4-6',
            'claude-haiku-4-5-20251001',
        ],
    },
    'openai': {
        'name': 'OpenAI',
        'models': [
            'gpt-4o',
            'gpt-4o-mini',
            'gpt-4-turbo',
            'gpt-3.5-turbo',
        ],
    },
}

# Per-channel model cache: {channel_id: model_instance}
_model_cache: dict = {}


def invalidate_cache(channel_id: str):
    _model_cache.pop(channel_id, None)


def _get_or_create_gemini_model(channel_id: str, api_key: str, model_name: str,
                                 system_prompt: str, temperature: float, max_tokens: int):
    import google.generativeai as genai

    cache_key = f"{channel_id}:panel"
    if cache_key in _model_cache:
        return _model_cache[cache_key]

    genai.configure(api_key=api_key)
    model = genai.GenerativeModel(
        model_name,
        generation_config=genai.GenerationConfig(
            temperature=temperature,
            max_output_tokens=max_tokens,
        ),
        system_instruction=system_prompt,
    )
    _model_cache[cache_key] = model
    return model


async def generate(
    channel_id: str,
    provider: str,
    model_name: str,
    api_key: str,
    system_prompt: str,
    user_message: str,
    temperature: float = 0.7,
    max_tokens: int = 300,
) -> str:
    if provider == 'gemini':
        return await _gemini(channel_id, api_key, model_name, system_prompt,
                             user_message, temperature, max_tokens)
    if provider == 'claude':
        return await _claude(api_key, model_name, system_prompt, user_message,
                             temperature, max_tokens)
    if provider == 'openai':
        return await _openai(api_key, model_name, system_prompt, user_message,
                             temperature, max_tokens)
    raise ValueError(f'Unknown provider: {provider}')


async def _gemini(channel_id, api_key, model_name, system_prompt,
                  user_message, temperature, max_tokens) -> str:
    model = _get_or_create_gemini_model(
        channel_id, api_key, model_name, system_prompt, temperature, max_tokens
    )
    response = await asyncio.to_thread(model.generate_content, user_message)
    return response.text.strip()


async def _claude(api_key, model_name, system_prompt, user_message,
                  temperature, max_tokens) -> str:
    import anthropic
    client = anthropic.Anthropic(api_key=api_key)
    response = await asyncio.to_thread(
        client.messages.create,
        model=model_name,
        max_tokens=max_tokens,
        temperature=temperature,
        system=system_prompt,
        messages=[{'role': 'user', 'content': user_message}],
    )
    return response.content[0].text.strip()


async def _openai(api_key, model_name, system_prompt, user_message,
                  temperature, max_tokens) -> str:
    from openai import OpenAI
    client = OpenAI(api_key=api_key)
    response = await asyncio.to_thread(
        client.chat.completions.create,
        model=model_name,
        max_tokens=max_tokens,
        temperature=temperature,
        messages=[
            {'role': 'system', 'content': system_prompt},
            {'role': 'user', 'content': user_message},
        ],
    )
    return response.choices[0].message.content.strip()
