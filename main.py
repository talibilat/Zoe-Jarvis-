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
from src.tools import add, multiply, subtract

load_dotenv()


SYSTEM_PROMPT = SystemMessage(content="You are my AI assistant. Use tools when needed and answer clearly.")

tools = [add, subtract, multiply]


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
    graph.add_node("tools", ToolNode(tools=tools))
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

    print("Say 'exit' to quit. I'm listening for your question or math problem.")
    while True:
        try:
            print("\nListening...")
            user_input = transcribe_speech()
        except (EOFError, KeyboardInterrupt):
            print()
            break

        if user_input is None:
            print("I didn't catch that. Please try again.")
            continue

        user_input = user_input.strip()
        if not user_input:
            continue

        print(f"You: {user_input}")

        if user_input.lower() == "exit":
            break

        conversation_history.append(HumanMessage(content=user_input))
        result = app.invoke({"messages": conversation_history})
        conversation_history = list(result["messages"])

        ai_message = get_last_ai_message(conversation_history)
        if ai_message:
            content = ai_message.content if isinstance(ai_message.content, str) else str(ai_message.content)
            print(f"\nZoe: {content}\n")
            speak_text(content)
        else:
            print("\nZoe: I was not able to generate a response.\n")

    if conversation_history:
        log_path = log_conversation(conversation_history)
        print(f"Conversation saved to {log_path.name}")
    else:
        print("No conversation to save.")


if __name__ == "__main__":
    main()
