import logging
from typing import Any, List

from botocore.config import Config
from strands import Agent
from strands.agent import SlidingWindowConversationManager
from strands.hooks import (
    HookProvider)
from strands.models import BedrockModel

from settings import Models

logger = logging.getLogger(__name__)


def get_agent(
        system_prompt: str,
        model: str = Models.CLAUDE_45,
        tools: List[Any] = [],
        hooks: List[HookProvider] = [],
        temperature: float = 0.3,
        llm_read_timeout: int = 300,
        llm_connect_timeout: int = 60,
        llm_max_attempts: int = 10,
        maximum_messages_to_keep: int = 30,
        should_truncate_results: bool = True,
        callback_handler: Any = None,

) -> Agent:
    return Agent(
        system_prompt=system_prompt,
        model=BedrockModel(
            model_id=model,
            temperature=temperature,
            boto_client_config=Config(
                read_timeout=llm_read_timeout,
                connect_timeout=llm_connect_timeout,
                retries={'max_attempts': llm_max_attempts}
            )
        ),
        conversation_manager=SlidingWindowConversationManager(
            window_size=maximum_messages_to_keep,
            should_truncate_results=should_truncate_results,
        ),
        tools=tools,
        hooks=hooks,
        callback_handler=callback_handler
    )
