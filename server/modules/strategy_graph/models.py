from __future__ import annotations
from typing import List, Literal, Optional, Union, Dict, Any
from pydantic import BaseModel, Field, validator


NodeType = Literal["single_order", "bracket_exit", "sequence"]


class BaseNode(BaseModel):
    id: str = Field(..., description="unique id within the graph")
    type: NodeType


class SingleOrderNode(BaseNode):
    type: Literal["single_order"] = "single_order"
    side: Literal["BUY", "SELL"]
    order_type: Literal["MKT", "LMT"] = "MKT"
    quantity: int = Field(..., gt=0)
    tif: str = "DAY"
    limit_price: Optional[float] = Field(None, gt=0)

    @validator("limit_price")
    def _need_limit_for_lmt(cls, v, values):
        if values.get("order_type") == "LMT" and (v is None or v <= 0):
            raise ValueError("limit_price required for LMT")
        return v


class BracketExitNode(BaseNode):
    type: Literal["bracket_exit"] = "bracket_exit"
    side: Literal["BUY", "SELL"]  # richting van parent
    quantity: int = Field(..., gt=0)
    target_price: float = Field(..., gt=0)
    stop_price: float = Field(..., gt=0)
    tif: str = "DAY"


class SequenceNode(BaseNode):
    type: Literal["sequence"] = "sequence"
    children: List["Node"] = Field(default_factory=list)


Node = Union[SingleOrderNode, BracketExitNode, SequenceNode]


class StrategyGraph(BaseModel):
    id: str
    name: str
    description: Optional[str] = None
    # root node
    root: Node

    @validator("root")
    def _root_valid(cls, v: Node):
        if not isinstance(v, (SingleOrderNode, BracketExitNode, SequenceNode)):
            raise ValueError("root must be a valid Node")
        return v


# needed because of forward refs in SequenceNode
StrategyGraph.update_forward_refs()
SequenceNode.update_forward_refs()
