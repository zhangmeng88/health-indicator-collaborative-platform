"""把《卫生统计指标》主表（.xlsx）全量导入后端数据库。

用法：
    cd backend
    python scripts/import_xlsx.py /path/to/2018卫生统计指标.xlsx
    python scripts/import_xlsx.py data.xlsx --update   # 已存在的标识符也更新

特性：
- 按表头名定位列，列序变化也能正确读取；
- 来源标准/部分、一级/二级/三级分类自动去重（get_or_create）；
- 指标按「标识符」去重，默认跳过已存在项，加 --update 则覆盖更新；
- 可在已播种的库上重复运行（幂等）。
"""
import argparse
import os
import sys

import openpyxl

# 允许从 backend 根目录导入 app 包
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import Base, engine, SessionLocal          # noqa: E402
from app.models import (SourceStandard, Classification, Indicator,            # noqa: E402
                        IndicatorStatus)

COLS = {
    "source": "来源标准/部分", "l1": "一级分类", "l2": "二级分类", "l3": "三级分类",
    "identifier": "标识符", "name_cn": "中文名称", "name_en": "英文名称", "unit": "计量单位",
    "definition": "定义", "method": "计算方法", "description": "指标说明",
    "survey_method": "调查方法", "data_source": "数据来源", "frequency": "发布频率",
}


def norm(v):
    return ("" if v is None else str(v)).strip()


def get_or_create_source(db, cache, title):
    title = norm(title)
    if not title:
        return None
    if title in cache:
        return cache[title]
    obj = db.query(SourceStandard).filter(SourceStandard.title == title).first()
    if not obj:
        obj = SourceStandard(title=title); db.add(obj); db.flush()
    cache[title] = obj
    return obj


def get_or_create_class(db, cache, name, parent_id, level):
    name = norm(name)
    if not name:
        return None
    key = (parent_id, name)
    if key in cache:
        return cache[key]
    obj = (db.query(Classification)
           .filter(Classification.name == name, Classification.parent_id == parent_id,
                   Classification.level == level).first())
    if not obj:
        obj = Classification(name=name, parent_id=parent_id, level=level, sort_order=0)
        db.add(obj); db.flush()
    cache[key] = obj
    return obj


def resolve_class_id(db, ccache, l1, l2, l3):
    """逐级 get_or_create，返回最深一级非空分类的 id。"""
    node = None
    for level, name in enumerate([l1, l2, l3], start=1):
        if not norm(name):
            break
        node = get_or_create_class(db, ccache, name, node.id if node else None, level)
    return node.id if node else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("xlsx", help="主表 .xlsx 路径")
    ap.add_argument("--sheet", default=None, help="工作表名（默认第一个）")
    ap.add_argument("--update", action="store_true", help="已存在标识符则更新而非跳过")
    args = ap.parse_args()

    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    scache, ccache = {}, {}
    inserted = updated = skipped = 0

    try:
        wb = openpyxl.load_workbook(args.xlsx, read_only=True, data_only=True)
        ws = wb[args.sheet] if args.sheet else wb.active
        rows = ws.iter_rows(values_only=True)
        header = [norm(h) for h in next(rows)]
        idx = {}
        for key, label in COLS.items():
            if label not in header:
                sys.exit(f"错误：主表缺少列「{label}」")
            idx[key] = header.index(label)

        for raw in rows:
            if not raw or not norm(raw[idx["name_cn"]]):
                continue
            g = lambda k: norm(raw[idx[k]])
            identifier = g("identifier")
            class_id = resolve_class_id(db, ccache, g("l1"), g("l2"), g("l3"))
            source = get_or_create_source(db, scache, g("source"))
            fields = dict(
                identifier=identifier, name_cn=g("name_cn"), name_en=g("name_en"),
                unit=g("unit"), definition=g("definition"), method=g("method"),
                description=g("description"), survey_method=g("survey_method"),
                data_source=g("data_source"), frequency=g("frequency"),
                classification_id=class_id,
                source_standard_id=source.id if source else None,
            )

            existing = None
            if identifier:
                existing = db.query(Indicator).filter(Indicator.identifier == identifier).first()
            if existing:
                if args.update:
                    for k, v in fields.items():
                        setattr(existing, k, v)
                    existing.version += 1
                    updated += 1
                else:
                    skipped += 1
            else:
                db.add(Indicator(status=IndicatorStatus.active, **fields))
                inserted += 1

        db.commit()
    finally:
        db.close()

    print("导入完成：")
    print(f"  新增指标 : {inserted}")
    print(f"  更新指标 : {updated}")
    print(f"  跳过(已存在): {skipped}")
    print(f"  来源标准 : {len(scache)} 项   分类节点(本次涉及): {len(ccache)} 个")


if __name__ == "__main__":
    main()
