from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from io import BytesIO
from zipfile import BadZipFile, ZipFile

from openpyxl import load_workbook

from app.platform.security.authorization import (
    AuthorizationPolicyPort,
    AuthorizationRequest,
    AuthorizationResource,
)
from app.platform.security.capabilities import Capability
from app.platform.security.context import ActorContext, ActorKind, DataClassification

MAX_UPLOAD_BYTES = 10 * 1024 * 1024
MAX_UNCOMPRESSED_BYTES = 50 * 1024 * 1024
MAX_ROWS = 10_000
MAX_ERRORS = 100

_HEADER_ALIASES = {
    "code": {"code", "référence", "reference", "ref", "n°", "no"},
    "designation": {"désignation", "designation", "libellé", "libelle", "description"},
    "unit": {"unité", "unite", "unit", "u"},
    "quantity": {"quantité", "quantite", "quantity", "qty"},
    "unit_price": {"prix unitaire", "pu", "unit price", "unit_price"},
    "total_price": {"montant", "total", "prix total", "total price", "total_price"},
}


@dataclass(frozen=True, slots=True)
class PricingImportRow:
    row_number: int
    code: str | None
    designation: str | None
    unit: str | None
    quantity_decimal: str | None
    unit_price_minor: int | None
    total_minor: int | None
    errors: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class PricingImportPreview:
    case_id: object
    document_kind: str
    filename: str
    row_count: int
    valid_row_count: int
    error_count: int
    total_minor: int
    rows: tuple[PricingImportRow, ...]


class PricingImportPreviewService:
    def __init__(self, *, policy: AuthorizationPolicyPort) -> None:
        self._policy = policy

    def preview(
        self,
        *,
        actor: ActorContext,
        case_id,
        document_kind: str,
        filename: str,
        content_type: str | None,
        payload: bytes,
    ) -> PricingImportPreview:
        self._authorize(actor=actor, case_id=case_id)
        if len(payload) > MAX_UPLOAD_BYTES:
            raise ValueError("IMPORT_FILE_TOO_LARGE")
        normalized_name = filename.casefold().strip()
        if not normalized_name.endswith(".xlsx") or normalized_name.endswith(".xlsm"):
            raise ValueError("IMPORT_XLSX_REQUIRED")
        accepted_content_types = {
            None,
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        }
        if content_type not in accepted_content_types:
            raise ValueError("IMPORT_CONTENT_TYPE_REJECTED")
        try:
            with ZipFile(BytesIO(payload)) as archive:
                if any(name.lower().endswith("vbaproject.bin") for name in archive.namelist()):
                    raise ValueError("IMPORT_MACROS_REJECTED")
                if sum(info.file_size for info in archive.infolist()) > MAX_UNCOMPRESSED_BYTES:
                    raise ValueError("IMPORT_ARCHIVE_TOO_LARGE")
            workbook = load_workbook(BytesIO(payload), read_only=True, data_only=True)
        except (BadZipFile, OSError, ValueError) as error:
            if isinstance(error, ValueError) and str(error).startswith("IMPORT_"):
                raise
            raise ValueError("IMPORT_WORKBOOK_INVALID") from error
        try:
            sheet = workbook.active
            rows = list(sheet.iter_rows(values_only=True))
            if not rows:
                raise ValueError("IMPORT_EMPTY_WORKBOOK")
            header_map = _resolve_headers(rows[0])
            if "designation" not in header_map:
                raise ValueError("IMPORT_DESIGNATION_COLUMN_REQUIRED")
            parsed: list[PricingImportRow] = []
            total_minor = 0
            errors = 0
            for row_number, values in enumerate(rows[1 : MAX_ROWS + 1], start=2):
                if not any(value not in (None, "") for value in values):
                    continue
                item = _parse_row(row_number=row_number, values=values, header_map=header_map)
                parsed.append(item)
                errors += len(item.errors)
                if not item.errors and item.total_minor is not None:
                    total_minor += item.total_minor
                if errors >= MAX_ERRORS:
                    break
            return PricingImportPreview(
                case_id=case_id,
                document_kind=document_kind,
                filename=filename,
                row_count=len(parsed),
                valid_row_count=sum(not item.errors for item in parsed),
                error_count=errors,
                total_minor=total_minor,
                rows=tuple(parsed[:100]),
            )
        finally:
            workbook.close()

    def _authorize(self, *, actor: ActorContext, case_id) -> None:
        if actor.actor_kind is not ActorKind.PATRON_ADMIN or actor.membership_id is None:
            raise PermissionError("PATRON_REQUIRED")
        decision = self._policy.authorize(
            context=actor,
            request=AuthorizationRequest(
                action=Capability.PRICING_WRITE,
                resource=AuthorizationResource(
                    resource_type="PRICING_IMPORT",
                    resource_id=case_id,
                    tenant_id=actor.tenant_id,
                    case_id=case_id,
                    classification=DataClassification.FINANCIAL_PRIVATE,
                ),
                evaluated_at=actor.authenticated_at,
            ),
        )
        if not decision.allowed:
            raise PermissionError(decision.code)


def _normalize_header(value: object) -> str:
    return " ".join(str(value or "").casefold().strip().split())


def _resolve_headers(values: tuple[object, ...]) -> dict[str, int]:
    resolved: dict[str, int] = {}
    aliases = {
        key: {_normalize_header(alias) for alias in names}
        for key, names in _HEADER_ALIASES.items()
    }
    for index, value in enumerate(values):
        normalized = _normalize_header(value)
        for field, field_aliases in aliases.items():
            if normalized in field_aliases and field not in resolved:
                resolved[field] = index
                break
    return resolved


def _value(values: tuple[object, ...], header_map: dict[str, int], field: str) -> object:
    index = header_map.get(field)
    return values[index] if index is not None and index < len(values) else None


def _parse_row(
    *, row_number: int, values: tuple[object, ...], header_map: dict[str, int]
) -> PricingImportRow:
    code = _text(_value(values, header_map, "code"))
    designation = _text(_value(values, header_map, "designation"))
    unit = _text(_value(values, header_map, "unit"))
    quantity = _decimal_text(_value(values, header_map, "quantity"), default="1")
    unit_price = _minor(_value(values, header_map, "unit_price"))
    total = _minor(_value(values, header_map, "total_price"))
    errors: list[str] = []
    if not designation:
        errors.append("DESIGNATION_REQUIRED")
    if quantity is None:
        errors.append("QUANTITY_INVALID")
    if total is None and unit_price is None:
        errors.append("PRICE_REQUIRED")
    if total is None and unit_price is not None and quantity is not None:
        total = int((Decimal(quantity) * Decimal(unit_price)).to_integral_value())
    return PricingImportRow(
        row_number=row_number,
        code=code,
        designation=designation,
        unit=unit,
        quantity_decimal=quantity,
        unit_price_minor=unit_price,
        total_minor=total,
        errors=tuple(errors),
    )


def _text(value: object) -> str | None:
    if value in (None, ""):
        return None
    return str(value).strip()[:500] or None


def _decimal_text(value: object, *, default: str | None = None) -> str | None:
    if value in (None, ""):
        return default
    try:
        decimal = Decimal(str(value).replace(",", "."))
    except (InvalidOperation, ValueError):
        return None
    if decimal < 0:
        return None
    return format(decimal, "f")


def _minor(value: object) -> int | None:
    if value in (None, ""):
        return None
    try:
        decimal = Decimal(str(value).replace(",", "."))
    except (InvalidOperation, ValueError):
        return None
    if decimal < 0:
        return None
    return int((decimal * 100).to_integral_value())
