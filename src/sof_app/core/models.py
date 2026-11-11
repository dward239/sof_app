from __future__ import annotations
from pydantic import BaseModel, field_validator
from typing import Optional

class SampleRow(BaseModel):
    nuclide: str
    value: float
    unit: str
    sigma: Optional[float] = None
    note: Optional[str] = None
    batch_id: Optional[str] = None

    @field_validator("nuclide")
    @classmethod
    def strip_nuclide(cls, v: str) -> str:
        return v.strip()

class LimitEntry(BaseModel):
    nuclide: str
    limit_value: float
    limit_unit: str
    category: Optional[str] = None
    rule_name: Optional[str] = None
    rule_rev: Optional[str] = None
    provenance: Optional[str] = None

    @field_validator("nuclide")
    @classmethod
    def strip_nuclide(cls, v: str) -> str:
        return v.strip()

class SofResultRow(BaseModel):
    nuclide: str
    conc_display: str
    limit_display: str
    fraction: float
    fraction_sigma: Optional[float] = None
    note: Optional[str] = None

class SofSummary(BaseModel):
    rule_name: str
    category: Optional[str]
    sof_total: float
    sof_sigma: Optional[float] = None
    pass_limit: bool
    margin_to_1: float

class Assumptions(BaseModel):
    unit_family: str
    rounding_display_sigfigs: int
    treat_missing_as_zero: bool = True
    combine_duplicates: bool = True
