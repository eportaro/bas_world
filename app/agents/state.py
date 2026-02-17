"""
Agent state definition for the LangGraph multi-agent system.
The state flows through all agent nodes and accumulates context.
"""

from __future__ import annotations

from typing import Annotated, Optional, Sequence

from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages
from typing_extensions import TypedDict


class AgentState(TypedDict):
    """Shared state that flows through the LangGraph agent pipeline."""

    # Conversation messages (auto-accumulated via add_messages reducer)
    messages: Annotated[Sequence[BaseMessage], add_messages]

    # Current search filters (set by filter_builder, used by search_agent)
    current_filters: Optional[str]  # JSON string of SearchFilters

    # Last search results (vehicle summaries for context)
    last_results: Optional[str]  # JSON string

    # Session identifier
    session_id: str

    # Detected intent for routing
    intent: Optional[str]  # search, refine, compare, advice, greeting, out_of_scope
