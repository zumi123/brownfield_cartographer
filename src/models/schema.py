"""Pydantic schemas for nodes, edges, and graph types."""

from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field, field_validator


# --- Node types (per challenge spec) ---


class ModuleNode(BaseModel):
    """Structural module/file node."""

    path: str
    language: str
    purpose_statement: Optional[str] = None
    domain_cluster: Optional[str] = None
    complexity_score: Optional[float] = None
    change_velocity_30d: Optional[int] = None
    is_dead_code_candidate: bool = False
    last_modified: Optional[str] = None

    @field_validator("path")
    @classmethod
    def path_non_empty(cls, v: str) -> str:
        if not (v and v.strip()):
            raise ValueError("path must be non-empty")
        return v


class StorageType(str, Enum):
    TABLE = "table"
    FILE = "file"
    STREAM = "stream"
    API = "api"


class DatasetNode(BaseModel):
    """Dataset/table/file used in data flow."""

    name: str
    storage_type: StorageType = StorageType.TABLE
    schema_snapshot: Optional[dict[str, Any]] = None
    freshness_sla: Optional[str] = None
    owner: Optional[str] = None
    is_source_of_truth: bool = False


class FunctionNode(BaseModel):
    """Function/symbol within a module."""

    qualified_name: str
    parent_module: str
    signature: Optional[str] = None
    purpose_statement: Optional[str] = None
    call_count_within_repo: int = 0
    is_public_api: bool = True


class TransformationNode(BaseModel):
    """Transformation step (code or config) that consumes/produces datasets."""

    id: str  # unique key, e.g. file:line_range
    source_datasets: list[str] = Field(default_factory=list)
    target_datasets: list[str] = Field(default_factory=list)
    transformation_type: str = "sql"  # sql | python | config
    source_file: str = ""
    line_range: Optional[tuple[int, int]] = None
    sql_query_if_applicable: Optional[str] = None

    @field_validator("id")
    @classmethod
    def id_non_empty(cls, v: str) -> str:
        if not (v and v.strip()):
            raise ValueError("id must be non-empty")
        return v


# --- Edge types ---


class EdgeTypes(str, Enum):
    IMPORTS = "IMPORTS"
    PRODUCES = "PRODUCES"
    CONSUMES = "CONSUMES"
    CALLS = "CALLS"
    CONFIGURES = "CONFIGURES"


# --- Serialization helpers ---


def module_node_to_dict(n: ModuleNode) -> dict:
    return n.model_dump()


def dataset_node_to_dict(n: DatasetNode) -> dict:
    d = n.model_dump()
    d["storage_type"] = d["storage_type"].value if hasattr(d["storage_type"], "value") else d["storage_type"]
    return d


def transformation_node_to_dict(n: TransformationNode) -> dict:
    d = n.model_dump()
    if d.get("line_range"):
        d["line_range"] = list(d["line_range"])
    return d
