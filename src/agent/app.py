from __future__ import annotations

from typing import Annotated, Callable, List, Sequence, TypedDict

from dotenv import load_dotenv
from langchain_core.messages import AIMessage, BaseMessage, SystemMessage
from langgraph.graph import END, StateGraph
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode

from src.core.clients.llm_client import build_chat_model
from src.tools import AGENT_TOOLS

load_dotenv()

SYSTEM_PROMPT = SystemMessage(
    content=(
        "You are my AI assistant. Use tools when needed and answer clearly. "
        "Never claim an action succeeded unless a tool result explicitly confirms "
        "success. If a tool errors, acknowledge the failure and explain what to do next."
    )
)


class AgentState(TypedDict):
    messages: Annotated[Sequence[BaseMessage], add_messages]


tools = AGENT_TOOLS


def build_model_call(llm):
    def model_call(state: AgentState) -> AgentState:
        response = llm.invoke([SYSTEM_PROMPT] + list(state["messages"]))
        return {"messages": [response]}

    return model_call


def should_continue(state: AgentState) -> str:
    messages = state.get("messages", [])
    if not messages:
        return "end"

    last_message = messages[-1]
    return "continue" if getattr(last_message, "tool_calls", None) else "end"


def build_app(prompt_on_multiple: bool = True):
    llm = build_chat_model(tools, prompt_on_multiple=prompt_on_multiple)
    graph = StateGraph(AgentState)
    graph.add_node("agent", build_model_call(llm))
    graph.add_node("tools", ToolNode(tools=tools, handle_tool_errors=True))
    graph.set_entry_point("agent")
    graph.add_conditional_edges(
        "agent",
        should_continue,
        {
            "continue": "tools",
            "end": END,
        },
    )
    graph.add_edge("tools", "agent")
    return graph.compile()


ChunkHandler = Callable[[str], None]


def stream_agent_response(
    app, conversation_history: Sequence[BaseMessage], on_chunk: ChunkHandler
) -> List[BaseMessage]:
    """Stream the agent response and return the updated conversation history."""

    last_content = ""
    final_messages: Sequence[BaseMessage] = conversation_history

    for update in app.stream({"messages": conversation_history}, stream_mode="updates"):
        agent_update = update.get("agent")
        if not agent_update:
            continue

        final_messages = agent_update["messages"]
        if not final_messages:
            continue

        ai_message = final_messages[-1]
        if not isinstance(ai_message, AIMessage):
            continue

        content = (
            ai_message.content
            if isinstance(ai_message.content, str)
            else str(ai_message.content)
        )
        new_text = content[len(last_content) :]
        last_content = content
        if new_text:
            on_chunk(new_text)

    return list(final_messages)


def get_last_ai_text(messages: Sequence[BaseMessage]) -> str:
    for message in reversed(messages):
        if isinstance(message, AIMessage):
            return (
                message.content
                if isinstance(message.content, str)
                else str(message.content)
            )
    return ""
