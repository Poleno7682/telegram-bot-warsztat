"""Regression tests for item 2.3 in docs/REFACTORING_PLAN_2026-07.md: the
Service create/update parameter list (name_pl, name_ru, duration_minutes,
price, description_pl, description_ru) used to be duplicated verbatim
across ServiceRepository, ServiceManagementService and the calling admin
handler. ServiceCreateData/ServiceUpdateData (app/dto.py) replace all three
copies with one shared definition.
"""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.dto import ServiceCreateData, ServiceUpdateData
from app.repositories.service import ServiceRepository
from app.services.service_management_service import ServiceManagementService


@pytest.fixture
def service_mgmt(db_session: AsyncSession) -> ServiceManagementService:
    return ServiceManagementService(db_session)


class TestCreateServiceWithDto:
    async def test_creates_service_with_all_fields(self, service_mgmt):
        service = await service_mgmt.create_service(
            ServiceCreateData(
                name_pl="Wymiana oleju",
                name_ru="Замена масла",
                duration_minutes=30,
                price=150.0,
                description_pl="Opis PL",
                description_ru="Опис RU",
            )
        )

        assert service.id is not None
        assert service.name_pl == "Wymiana oleju"
        assert service.name_ru == "Замена масла"
        assert service.duration_minutes == 30
        assert service.price == 150.0
        assert service.description_pl == "Opis PL"
        assert service.description_ru == "Опис RU"
        assert service.is_active is True

    async def test_creates_service_with_only_required_fields(self, service_mgmt):
        service = await service_mgmt.create_service(
            ServiceCreateData(name_pl="Diagnostyka", name_ru="Диагностика", duration_minutes=15)
        )

        assert service.price is None
        assert service.description_pl is None
        assert service.is_active is True


class TestUpdateServiceWithDto:
    async def test_partial_update_only_changes_given_fields(self, service_mgmt):
        service = await service_mgmt.create_service(
            ServiceCreateData(
                name_pl="Wymiana oleju",
                name_ru="Замена масла",
                duration_minutes=30,
                price=100.0,
            )
        )

        updated = await service_mgmt.update_service(
            service.id,
            ServiceUpdateData(duration_minutes=45),
        )

        assert updated is not None
        assert updated.duration_minutes == 45
        # Untouched fields must survive the partial update.
        assert updated.name_pl == "Wymiana oleju"
        assert updated.name_ru == "Замена масла"
        assert updated.price == 100.0

    async def test_update_missing_service_returns_none(self, service_mgmt):
        result = await service_mgmt.update_service(999999, ServiceUpdateData(duration_minutes=10))
        assert result is None


class TestServiceRepositoryDtoDirectly:
    async def test_repository_create_service_uses_dto(self, db_session: AsyncSession):
        repo = ServiceRepository(db_session)

        service = await repo.create_service(
            ServiceCreateData(name_pl="Test", name_ru="Тест", duration_minutes=20)
        )

        assert service.name_pl == "Test"
        assert service.duration_minutes == 20
