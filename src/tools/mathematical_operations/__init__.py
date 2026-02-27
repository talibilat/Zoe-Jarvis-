"""Mathematical operation tools exposed to the agent."""

from .add_tool import add
from .multiply_tool import multiply
from .subtract_tool import subtract

MATHEMATICAL_TOOLS = [add, subtract, multiply]

__all__ = ["add", "subtract", "multiply", "MATHEMATICAL_TOOLS"]
