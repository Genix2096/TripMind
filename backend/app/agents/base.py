import json
from collections.abc import Callable, Coroutine
from typing import Any

from app.core.authorization import SearchAuthorizer
from app.providers.groq.client import GroqLLMClient, ToolCallRequest


class Agent:
    """Base class for specialist agents."""

    def __init__(self, llm: GroqLLMClient):
        self.llm = llm

    @property
    def system_prompt(self) -> str:
        return "You are an agent."

    @property
    def tools(self) -> list[dict[str, Any]]:
        return []

    async def run(
        self,
        user_message: str,
        authorizer: SearchAuthorizer,
        tool_executor: Callable[[ToolCallRequest], Coroutine[Any, Any, str]],
        max_iterations: int = 5,
    ) -> str:
        messages = [{"role": "system", "content": self.system_prompt}]
        if user_message:
            messages.append({"role": "user", "content": user_message})

        for _ in range(max_iterations):
            response = await self.llm.chat(
                messages,
                authorizer=authorizer,
                tools=self.tools if self.tools else None,
                max_tokens=512,
            )

            if response.content:
                messages.append({"role": "assistant", "content": response.content})

            if not response.tool_calls:
                return response.content or ""

            # The model called tools. We append the tool call request to the history.
            messages.append(
                {
                    "role": "assistant",
                    "content": response.content,
                    "tool_calls": [
                        {
                            "id": call.id,
                            "type": "function",
                            "function": {"name": call.name, "arguments": json.dumps(call.arguments)},
                        }
                        for call in response.tool_calls
                    ],
                }
            )

            # Let the coordinator execute them.
            results = []
            has_error = False
            for call in response.tool_calls:
                try:
                    result = await tool_executor(call)
                except Exception as e:  # noqa: BLE001
                    result = f"Error executing {call.name}: {e}"
                
                if result.startswith("Error"):
                    has_error = True
                    
                results.append(result)
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": call.id,
                        "name": call.name,
                        "content": result,
                    }
                )
                
            if not has_error:
                # Avoid redundant LLM summarization of JSON tool outputs. 
                return "\n".join(results)
                
            # If a strict quota limit was hit, stop immediately
            if any("Limit of" in r and "call(s) per planning run reached" in r for r in results):
                return "\n".join(results)

        return "Agent stopped after reaching maximum iterations."
