from __future__ import annotations

from typing import Annotated, Any, Callable, List, Literal, Sequence, TypedDict

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
        "success. If a tool errors, acknowledge the failure and explain what to do next. "
        "Do not expose raw tool payloads or JSON blobs to the user unless they explicitly "
        "ask for raw output."
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
StreamMode = Literal["values", "updates", "custom", "messages", "debug"]
StreamHandler = Callable[[str, Any], None]
DEFAULT_STREAM_MODES: tuple[StreamMode, StreamMode] = ("messages", "updates")

_SUPPORTED_STREAM_MODES: set[str] = {
    "values",
    "updates",
    "custom",
    "messages",
    "debug",
}


def _normalize_stream_modes(
    stream_mode: StreamMode | Sequence[StreamMode],
) -> List[StreamMode]:
    if isinstance(stream_mode, str):
        normalized: List[StreamMode] = [stream_mode]
    else:
        normalized = list(stream_mode)

    if not normalized:
        raise ValueError("stream_mode must contain at least one mode.")

    unsupported = [mode for mode in normalized if mode not in _SUPPORTED_STREAM_MODES]
    if unsupported:
        accepted = ", ".join(sorted(_SUPPORTED_STREAM_MODES))
        raise ValueError(
            f"Unsupported stream_mode value(s): {', '.join(unsupported)}. "
            f"Supported values: {accepted}"
        )

    if "updates" not in normalized and "values" not in normalized:
        normalized.append("updates")

    deduplicated: List[StreamMode] = []
    for mode in normalized:
        if mode not in deduplicated:
            deduplicated.append(mode)

    return deduplicated


def resolve_stream_modes(
    configured_modes: str | None,
    *,
    default: Sequence[StreamMode] = DEFAULT_STREAM_MODES,
) -> List[StreamMode]:
    """Resolve stream modes from a comma-separated environment value."""

    if configured_modes is None:
        return _normalize_stream_modes(default)

    raw_modes = configured_modes.strip()
    if not raw_modes:
        raise ValueError(
            "STREAM_MODES is set but empty. Provide a comma-separated list like "
            "'messages,updates'."
        )

    parsed_modes = [mode.strip() for mode in raw_modes.split(",") if mode.strip()]
    if not parsed_modes:
        raise ValueError(
            "STREAM_MODES did not include any valid mode names. "
            "Provide a comma-separated list like 'messages,updates'."
        )

    return _normalize_stream_modes(parsed_modes)


def _resolve_stream_item_mode(
    stream_item: Any, stream_modes: Sequence[StreamMode]
) -> tuple[StreamMode, Any]:
    if len(stream_modes) == 1:
        return stream_modes[0], stream_item

    if (
        isinstance(stream_item, tuple)
        and len(stream_item) == 2
        and isinstance(stream_item[0], str)
        and stream_item[0] in _SUPPORTED_STREAM_MODES
    ):
        return stream_item[0], stream_item[1]

    if isinstance(stream_item, dict):
        if "updates" in stream_modes:
            return "updates", stream_item
        if "values" in stream_modes:
            return "values", stream_item

    return stream_modes[0], stream_item


def _strip_namespace(chunk: Any) -> Any:
    if (
        isinstance(chunk, tuple)
        and len(chunk) == 2
        and isinstance(chunk[0], tuple)
        and isinstance(chunk[1], dict)
    ):
        return chunk[1]
    return chunk


def _extract_messages_from_updates(chunk: Any) -> Sequence[BaseMessage] | None:
    payload = _strip_namespace(chunk)
    if not isinstance(payload, dict):
        return None

    for node_update in payload.values():
        if not isinstance(node_update, dict):
            continue
        messages = node_update.get("messages")
        if isinstance(messages, Sequence):
            return messages

    return None


def _extract_messages_from_values(chunk: Any) -> Sequence[BaseMessage] | None:
    payload = _strip_namespace(chunk)
    if not isinstance(payload, dict):
        return None

    messages = payload.get("messages")
    if isinstance(messages, Sequence):
        return messages
    return None


def _extract_message_chunk_text(message_chunk: Any) -> str:
    content = getattr(message_chunk, "content", "")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: List[str] = []
        for part in content:
            if isinstance(part, str):
                parts.append(part)
            elif isinstance(part, dict):
                text = part.get("text")
                if isinstance(text, str):
                    parts.append(text)
        return "".join(parts)
    return ""


def _passes_stream_filters(
    metadata: dict[str, Any], token_node: str | None, token_tags: Sequence[str] | None
) -> bool:
    if token_node and metadata.get("langgraph_node") != token_node:
        return False

    if token_tags:
        metadata_tags = metadata.get("tags")
        if not isinstance(metadata_tags, list):
            return False
        if not set(token_tags).issubset(set(metadata_tags)):
            return False

    return True


def stream_agent_response(
    app,
    conversation_history: Sequence[BaseMessage],
    on_chunk: ChunkHandler,
    *,
    stream_mode: StreamMode | Sequence[StreamMode] = DEFAULT_STREAM_MODES,
    token_node: str | None = None,
    token_tags: Sequence[str] | None = None,
    on_stream: StreamHandler | None = None,
    subgraphs: bool = False,
) -> List[BaseMessage]:
    """Stream the agent response and return the updated conversation history.

    By default, this streams message tokens and state updates together.
    """

    last_content = ""
    final_messages: Sequence[BaseMessage] = conversation_history
    stream_modes = _normalize_stream_modes(stream_mode)
    uses_message_mode = "messages" in stream_modes
    request_stream_mode: StreamMode | List[StreamMode]
    request_stream_mode = stream_modes[0] if len(stream_modes) == 1 else stream_modes

    for stream_item in app.stream(
        {"messages": conversation_history},
        stream_mode=request_stream_mode,
        subgraphs=subgraphs,
    ):
        mode, chunk = _resolve_stream_item_mode(stream_item, stream_modes)
        if on_stream:
            on_stream(mode, chunk)

        if mode == "messages":
            if not (
                isinstance(chunk, tuple)
                and len(chunk) == 2
                and isinstance(chunk[1], dict)
            ):
                continue
            message_chunk, metadata = chunk
            if not _passes_stream_filters(metadata, token_node, token_tags):
                continue
            text = _extract_message_chunk_text(message_chunk)
            if text:
                on_chunk(text)
            continue

        if mode == "updates":
            messages = _extract_messages_from_updates(chunk)
        elif mode == "values":
            messages = _extract_messages_from_values(chunk)
        else:
            continue

        if not messages:
            continue

        final_messages = messages
        if uses_message_mode:
            continue

        content = get_last_ai_text(final_messages)
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
