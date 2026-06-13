"""导出：Excel（.xlsx）与 Word（.docx），按分类层级组织，列序与主表一致。"""
import io

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from ..database import get_db
from ..security import require_admin
from ..models import Classification, Indicator, IndicatorStatus, User

router = APIRouter(prefix="/export", tags=["导出"])

LEVELS = ["一级分类", "二级分类", "三级分类"]
HEADERS = ["来源标准/部分", *LEVELS, "标识符", "中文名称", "英文名称", "计量单位",
           "定义", "计算方法", "指标说明", "调查方法", "数据来源", "发布频率"]


def _walk(db: Session, parent_id=None, path=None):
    """深度优先遍历分类树，产出 (node, [一级,二级,三级名称]) 序列。"""
    path = path or []
    nodes = (db.query(Classification).filter(Classification.parent_id == parent_id)
             .order_by(Classification.sort_order, Classification.id).all())
    for n in nodes:
        p = path + [n.name]
        yield n, p
        yield from _walk(db, n.id, p)


def _indicators(db: Session, class_id: int):
    return (db.query(Indicator)
            .filter(Indicator.classification_id == class_id, Indicator.status == IndicatorStatus.active)
            .order_by(Indicator.identifier).all())


@router.get("/excel", summary="导出 Excel")
def export_excel(admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill, Alignment, Border, Side

    wb = Workbook(); ws = wb.active; ws.title = "卫生统计指标"
    thin = Side(style="thin", color="D0D0D0"); border = Border(thin, thin, thin, thin)
    ws.append(HEADERS)
    for c in range(1, len(HEADERS) + 1):
        cell = ws.cell(1, c)
        cell.font = Font(name="宋体", size=10, bold=True, color="FFFFFF")
        cell.fill = PatternFill("solid", fgColor="1F4E5F")
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        cell.border = border

    for node, path in _walk(db):
        for ind in _indicators(db, node.id):
            levels = (path + ["", "", ""])[:3]
            ws.append([
                ind.source_standard.title if ind.source_standard else "",
                levels[0], levels[1], levels[2],
                ind.identifier, ind.name_cn, ind.name_en, ind.unit,
                ind.definition, ind.method, ind.description,
                ind.survey_method, ind.data_source, ind.frequency,
            ])
            r = ws.max_row
            for c in range(1, len(HEADERS) + 1):
                cc = ws.cell(r, c)
                cc.font = Font(name="宋体", size=10)
                cc.alignment = Alignment(horizontal="left", vertical="top", wrap_text=True)
                cc.border = border

    widths = [28, 12, 12, 12, 14, 22, 30, 8, 40, 32, 40, 10, 16, 10]
    from openpyxl.utils import get_column_letter
    for i, w in enumerate(widths, 1):
        ws.column_dimensions[get_column_letter(i)].width = w
    ws.freeze_panes = "A2"

    buf = io.BytesIO(); wb.save(buf); buf.seek(0)
    return StreamingResponse(buf, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                             headers={"Content-Disposition": "attachment; filename=health_indicators.xlsx"})


@router.get("/word", summary="导出 Word")
def export_word(admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    from docx import Document
    from docx.shared import Pt

    doc = Document()
    doc.add_heading("卫生统计指标（含元数据）", level=0)

    def emit(parent_id=None, depth=1):
        nodes = (db.query(Classification).filter(Classification.parent_id == parent_id)
                 .order_by(Classification.sort_order, Classification.id).all())
        for n in nodes:
            doc.add_heading(n.name, level=min(depth, 4))
            inds = _indicators(db, n.id)
            if inds:
                cols = ["标识符", "中文名称", "英文名称", "单位", "定义", "计算方法", "指标说明", "调查方法", "数据来源", "发布频率"]
                t = doc.add_table(rows=1, cols=len(cols)); t.style = "Light Grid Accent 1"
                for i, h in enumerate(cols):
                    t.rows[0].cells[i].text = h
                for ind in inds:
                    cells = t.add_row().cells
                    vals = [ind.identifier, ind.name_cn, ind.name_en, ind.unit, ind.definition,
                            ind.method, ind.description, ind.survey_method, ind.data_source, ind.frequency]
                    for i, v in enumerate(vals):
                        cells[i].text = v or ""
            emit(n.id, depth + 1)

    emit()
    buf = io.BytesIO(); doc.save(buf); buf.seek(0)
    return StreamingResponse(buf, media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                             headers={"Content-Disposition": "attachment; filename=health_indicators.docx"})
