from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

from langchain_core.messages import AIMessage, HumanMessage

import src.agent.app as agent_app


class FakeApp:
    def __init__(self, updates):
        self._updates = updates
        self.calls = []

    def stream(self, payload, *, stream_mode: str):
        self.calls.append((payload, stream_mode))
        for update in self._updates:
            yield update


def test_build_model_call_invokes_llm_with_system_prompt() -> None:
    llm = MagicMock()
    llm.invoke.return_value = AIMessage(content="Hello")
    model_call = agent_app.build_model_call(llm)

    human = HumanMessage(content="Hi")
    result = model_call({"messages": [human]})

    assert result == {"messages": [llm.invoke.return_value]}
    invoke_args = llm.invoke.call_args.args[0]
    assert invoke_args[0] is agent_app.SYSTEM_PROMPT
    assert invoke_args[1] == human


def test_should_continue_states() -> None:
    assert agent_app.should_continue({"messages": []}) == "end"
    assert (
        agent_app.should_continue(
            {
                "messages": [
                    AIMessage(
                        content="",
                        tool_calls=[{"id": "call-1", "name": "add", "args": {}}],
                    )
                ]
            }
        )
        == "continue"
    )
    assert agent_app.should_continue({"messages": [AIMessage(content="done")]}) == "end"


def test_stream_agent_response_streams_incremental_ai_chunks() -> None:
    history = [HumanMessage(content="hello")]
    app = FakeApp(
        [
            {"noop": {}},
            {"agent": {"messages": []}},
            {"agent": {"messages": [HumanMessage(content="not ai")]}},
            {"agent": {"messages": [AIMessage(content="Hello")]}},
            {"agent": {"messages": [AIMessage(content="Hello there")]}},
        ]
    )

    chunks: list[str] = []
    final_messages = agent_app.stream_agent_response(app, history, chunks.append)

    assert app.calls == [({"messages": history}, "updates")]
    assert chunks == ["Hello", " there"]
    assert isinstance(final_messages[-1], AIMessage)
    assert final_messages[-1].content == "Hello there"


def test_get_last_ai_text_returns_latest_ai_content() -> None:
    messages = [
        HumanMessage(content="q"),
        AIMessage(content="first"),
        AIMessage(content=[{"text": "second"}]),
    ]

    assert agent_app.get_last_ai_text(messages) == "[{'text': 'second'}]"
    assert agent_app.get_last_ai_text([HumanMessage(content="only user")]) == ""


def test_build_app_wires_graph_and_tool_node(monkeypatch) -> None:
    fake_llm = object()
    build_chat_model_mock = MagicMock(return_value=fake_llm)
    monkeypatch.setattr(agent_app, "build_chat_model", build_chat_model_mock)

    class FakeStateGraph:
        instance = None

        def __init__(self, state_type):
            self.state_type = state_type
            self.nodes = []
            self.entry = None
            self.conditional_edges = None
            self.edges = []
            FakeStateGraph.instance = self

        def add_node(self, name, node):
            self.nodes.append((name, node))

        def set_entry_point(self, name):
            self.entry = name

        def add_conditional_edges(self, node_name, condition, mapping):
            self.conditional_edges = (node_name, condition, mapping)

        def add_edge(self, start, end):
            self.edges.append((start, end))

        def compile(self):
            return "compiled-app"

    tool_node_mock = MagicMock(return_value=SimpleNamespace(name="tool-node"))
    monkeypatch.setattr(agent_app, "StateGraph", FakeStateGraph)
    monkeypatch.setattr(agent_app, "ToolNode", tool_node_mock)

    built = agent_app.build_app(prompt_on_multiple=False)

    assert built == "compiled-app"
    build_chat_model_mock.assert_called_once_with(
        agent_app.tools,
        prompt_on_multiple=False,
    )

    graph = FakeStateGraph.instance
    assert graph.entry == "agent"
    assert [name for name, _ in graph.nodes] == ["agent", "tools"]
    assert graph.edges == [("tools", "agent")]

    node_name, condition, mapping = graph.conditional_edges
    assert node_name == "agent"
    assert condition is agent_app.should_continue
    assert mapping == {"continue": "tools", "end": agent_app.END}

    tool_node_mock.assert_called_once_with(
        tools=agent_app.tools,
        handle_tool_errors=True,
    )
