from __future__ import annotations

from typing import Annotated, List, Sequence, TypedDict

from dotenv import load_dotenv
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage
from langgraph.graph import END, StateGraph
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode

from src.core.clients.llm_client import build_chat_model
from src.core.logs import log_conversation
from src.core.speech_service import speak_text, transcribe_speech
from src.core.terminal_ui import (
    format_assistant_line,
    format_system_line,
    format_user_line,
)
from src.tools import AGENT_TOOLS

load_dotenv()


SYSTEM_PROMPT = SystemMessage(
    content="You are my AI assistant. Use tools when needed and answer clearly."
)

tools = AGENT_TOOLS


class AgentState(TypedDict):
    messages: Annotated[Sequence[BaseMessage], add_messages]


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


def build_app():
    llm = build_chat_model(tools)
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


def get_last_ai_message(messages: Sequence[BaseMessage]) -> AIMessage | None:
    for message in reversed(messages):
        if isinstance(message, AIMessage):
            return message
    return None


def main() -> None:
    app = build_app()
    conversation_history: List[BaseMessage] = []

    print(
        format_system_line(
            "Say 'exit' to quit. I'm listening for your question or math problem.",
            tone="system",
            bold=True,
        )
    )
    while True:
        try:
            print()
            print(format_system_line("Listening...", tone="listening", bold=True))
            user_input = transcribe_speech()
        except (EOFError, KeyboardInterrupt):
            print()
            break

        if user_input is None:
            print(
                format_system_line(
                    "I didn't catch that. Please try again.", tone="warning"
                )
            )
            continue

        user_input = user_input.strip()
        if not user_input:
            continue

        print(format_user_line(user_input))

        if user_input.lower() == "exit":
            break

        conversation_history.append(HumanMessage(content=user_input))
        result = app.invoke({"messages": conversation_history})
        conversation_history = list(result["messages"])

        ai_message = get_last_ai_message(conversation_history)
        if ai_message:
            content = (
                ai_message.content
                if isinstance(ai_message.content, str)
                else str(ai_message.content)
            )
            print()
            print(format_assistant_line(content))
            print()
            speak_text(content)
        else:
            print()
            print(format_assistant_line("I was not able to generate a response."))
            print()

    if conversation_history:
        log_path = log_conversation(conversation_history)
        print(
            format_system_line(
                f"Conversation saved to {log_path.name}", tone="success", bold=True
            )
        )
    else:
        print(format_system_line("No conversation to save.", tone="info"))


if __name__ == "__main__":
    main()
