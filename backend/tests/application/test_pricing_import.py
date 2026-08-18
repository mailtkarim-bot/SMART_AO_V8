from dataclasses import replace
from io import BytesIO
from uuid import uuid4

import pytest
from app.modules.pricing.application.import_preview import PricingImportPreviewService
from app.platform.security.authorization import AuthorizationPolicy
from app.platform.security.capabilities import capabilities_for
from app.platform.security.context import ActorKind
from openpyxl import Workbook

from tests.application.test_financial_report_draft_lines import _seed_draft


def _xlsx(rows: list[list[object]]) -> bytes:
    workbook = Workbook()
    sheet = workbook.active
    for row in rows:
        sheet.append(row)
    output = BytesIO()
    workbook.save(output)
    return output.getvalue()


def test_pricing_import_preview_parses_dpgf_rows_without_persisting_raw_file(session_factory):
    actor, case_id, _, _ = _seed_draft(session_factory)
    payload = _xlsx(
        [
            ["Code", "Désignation", "Unité", "Quantité", "Prix unitaire"],
            ["A-01", "Terrassement", "m2", 10, 12.5],
            ["A-02", "Fondations", "m3", 2, 100],
        ]
    )
    preview = PricingImportPreviewService(policy=AuthorizationPolicy()).preview(
        actor=actor,
        case_id=case_id,
        document_kind="DPGF",
        filename="bordereau.xlsx",
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        payload=payload,
    )
    assert preview.row_count == 2
    assert preview.valid_row_count == 2
    assert preview.error_count == 0
    assert preview.total_minor == 32_500
    assert preview.rows[0].total_minor == 12_500


def test_pricing_import_preview_reports_missing_designation_and_refuses_non_xlsx(session_factory):
    actor, case_id, _, _ = _seed_draft(session_factory)
    payload = _xlsx([["Code", "Quantité", "Prix unitaire"], ["A-01", 1, 10]])
    with pytest.raises(ValueError, match="IMPORT_DESIGNATION_COLUMN_REQUIRED"):
        PricingImportPreviewService(policy=AuthorizationPolicy()).preview(
            actor=actor,
            case_id=case_id,
            document_kind="BPU",
            filename="bordereau.xlsx",
            content_type=None,
            payload=payload,
        )
    with pytest.raises(ValueError, match="IMPORT_XLSX_REQUIRED"):
        PricingImportPreviewService(policy=AuthorizationPolicy()).preview(
            actor=actor,
            case_id=case_id,
            document_kind="EXCEL",
            filename="bordereau.xlsm",
            content_type=None,
            payload=payload,
        )


def test_pricing_import_preview_refuses_collaborator_before_reading_financial_rows(session_factory):
    actor, case_id, _, _ = _seed_draft(session_factory)
    collaborator = replace(
        actor,
        actor_id=uuid4(),
        identity_id=uuid4(),
        membership_id=uuid4(),
        actor_kind=ActorKind.COLLABORATEUR,
        capabilities=capabilities_for(ActorKind.COLLABORATEUR),
    )
    with pytest.raises(PermissionError, match="PATRON_REQUIRED"):
        PricingImportPreviewService(policy=AuthorizationPolicy()).preview(
            actor=collaborator,
            case_id=case_id,
            document_kind="EXCEL",
            filename="bordereau.xlsx",
            content_type=None,
            payload=b"not-read",
        )


def test_pricing_import_preview_rejects_size_and_content_type_before_parsing(session_factory):
    actor, case_id, _, _ = _seed_draft(session_factory)
    service = PricingImportPreviewService(policy=AuthorizationPolicy())
    with pytest.raises(ValueError, match="IMPORT_FILE_TOO_LARGE"):
        service.preview(
            actor=actor,
            case_id=case_id,
            document_kind="EXCEL",
            filename="bordereau.xlsx",
            content_type=None,
            payload=b"x" * (10 * 1024 * 1024 + 1),
        )
    with pytest.raises(ValueError, match="IMPORT_CONTENT_TYPE_REJECTED"):
        service.preview(
            actor=actor,
            case_id=case_id,
            document_kind="EXCEL",
            filename="bordereau.xlsx",
            content_type="text/plain",
            payload=b"x",
        )


def test_pricing_import_preview_rejects_invalid_empty_and_macro_workbooks(session_factory):
    actor, case_id, _, _ = _seed_draft(session_factory)
    service = PricingImportPreviewService(policy=AuthorizationPolicy())
    with pytest.raises(ValueError, match="IMPORT_WORKBOOK_INVALID"):
        service.preview(
            actor=actor,
            case_id=case_id,
            document_kind="EXCEL",
            filename="bordereau.xlsx",
            content_type=None,
            payload=b"not-an-xlsx",
        )
    empty_payload = _xlsx([])
    with pytest.raises(ValueError, match="IMPORT_EMPTY_WORKBOOK"):
        service.preview(
            actor=actor,
            case_id=case_id,
            document_kind="EXCEL",
            filename="empty.xlsx",
            content_type=None,
            payload=empty_payload,
        )
    import zipfile

    macro_payload = BytesIO()
    with zipfile.ZipFile(macro_payload, "w") as archive:
        archive.writestr("xl/vbaProject.bin", b"macro")
    with pytest.raises(ValueError, match="IMPORT_MACROS_REJECTED"):
        service.preview(
            actor=actor,
            case_id=case_id,
            document_kind="EXCEL",
            filename="macro.xlsx",
            content_type=None,
            payload=macro_payload.getvalue(),
        )


def test_pricing_import_preview_reports_invalid_row_values(session_factory):
    actor, case_id, _, _ = _seed_draft(session_factory)
    preview = PricingImportPreviewService(policy=AuthorizationPolicy()).preview(
        actor=actor,
        case_id=case_id,
        document_kind="BPU",
        filename="bordereau.xlsx",
        content_type=None,
        payload=_xlsx(
            [
                ["Désignation", "Quantité", "Prix unitaire"],
                ["Ligne invalide", "abc", None],
                ["Ligne négative", -2, -10],
            ]
        ),
    )
    assert preview.valid_row_count == 0
    assert preview.error_count >= 3
    assert {"QUANTITY_INVALID", "PRICE_REQUIRED"}.issubset(preview.rows[0].errors)
