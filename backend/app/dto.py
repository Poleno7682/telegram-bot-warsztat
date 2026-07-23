"""Data-transfer objects shared across the repository/service/handler layers.

Before ServiceCreateData/ServiceUpdateData existed, the Service
create/update parameter list (name_pl, name_ru, duration_minutes, price,
description_pl, description_ru) was copied verbatim across
ServiceRepository, ServiceManagementService, and the calling admin handler -
three signatures to keep in sync for any new field. See
docs/REFACTORING_PLAN_2026-07.md, item 2.3.

Deliberately at the app package root (not under repositories/ or
services/): both of those layers need to import it, and neither should
import from the other's package.
"""

from dataclasses import dataclass
from decimal import Decimal
from typing import Optional


@dataclass(frozen=True)
class ServiceCreateData:
    """Fields required to create a Service."""
    name_pl: str
    name_ru: str
    duration_minutes: int
    price: Optional[Decimal] = None
    description_pl: Optional[str] = None
    description_ru: Optional[str] = None


@dataclass(frozen=True)
class ServiceUpdateData:
    """Fields to update on an existing Service. Every field is optional -
    unset (None) fields are left unchanged, matching the partial-update
    semantics ServiceRepository.update_service already had."""
    name_pl: Optional[str] = None
    name_ru: Optional[str] = None
    duration_minutes: Optional[int] = None
    price: Optional[Decimal] = None
    description_pl: Optional[str] = None
    description_ru: Optional[str] = None
