#!/usr/bin/env python3
"""
ETL 数据清洗与入库管道
依赖: pip install pandas sqlalchemy psycopg2-binary openpyxl pyarrow python-dotenv
"""
import hashlib
import json
import logging
import os
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Optional
from uuid import uuid4

import numpy as np
import pandas as pd
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("ETL")

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres:***@localhost:5432/etl_db")
BATCH_SIZE = int(os.getenv("BATCH_SIZE", 5000))
engine = create_engine(DATABASE_URL, pool_size=5, max_overflow=10)


class SourceType(Enum):
    CSV = "csv"
    EXCEL = "excel"
    JSON = "json"
    PARQUET = "parquet"
    API = "api"
    DATABASE = "database"


@dataclass
class DataSource:
    name: str
    source_type: SourceType
    path_or_url: str
    delimiter: str = ","
    sheet_name: Optional[str] = None
    encoding: str = "utf-8"
    method: str = "GET"
    headers: dict = field(default_factory=dict)
    column_mapping: dict[str, str] = field(default_factory=dict)
    dtypes: dict[str, str] = field(default_factory=dict)


@dataclass
class TransformStep:
    name: str
    func: Callable[[pd.DataFrame], pd.DataFrame]
    description: str = ""


class PipelineContext:
    def __init__(self, pipeline_name: str):
        self.pipeline_name = pipeline_name
        self.run_id = str(uuid4())
        self.start_time = datetime.now(timezone.utc)
        self.stats: dict[str, Any] = {}
        self.lineage: list[dict] = []

    def log_step(self, step_name: str, rows_before: int, rows_after: int, description: str = ""):
        self.lineage.append({
            "run_id": self.run_id, "step": step_name,
            "rows_before": rows_before, "rows_after": rows_after,
            "rows_changed": rows_before - rows_after,
            "description": description,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })


class DataExtractor:
    @staticmethod
    def extract(source: DataSource) -> pd.DataFrame:
        logger.info(f"抽取数据: {source.name} ({source.source_type.value})")
        if source.source_type == SourceType.CSV:
            df = pd.read_csv(source.path_or_url, delimiter=source.delimiter,
                             encoding=source.encoding, low_memory=False)
        elif source.source_type == SourceType.EXCEL:
            df = pd.read_excel(source.path_or_url, sheet_name=source.sheet_name or 0)
        elif source.source_type == SourceType.JSON:
            if source.path_or_url.startswith(("http://", "https://")):
                import requests
                resp = requests.get(source.path_or_url, headers=source.headers)
                resp.raise_for_status()
                data = resp.json()
            else:
                with open(source.path_or_url, encoding=source.encoding) as f:
                    data = json.load(f)
            df = pd.json_normalize(data)
        elif source.source_type == SourceType.PARQUET:
            df = pd.read_parquet(source.path_or_url)
        elif source.source_type == SourceType.DATABASE:
            df = pd.read_sql(source.path_or_url, engine)
        else:
            raise ValueError(f"不支持的源类型: {source.source_type}")
        logger.info(f"  抽取完成: {len(df)} 行, {len(df.columns)} 列")
        return df

    @staticmethod
    def apply_column_mapping(df: pd.DataFrame, mapping: dict[str, str]) -> pd.DataFrame:
        actual_mapping = {k: v for k, v in mapping.items() if k in df.columns}
        if actual_mapping:
            df = df.rename(columns=actual_mapping)
        return df

    @staticmethod
    def apply_dtypes(df: pd.DataFrame, dtypes: dict[str, str]) -> pd.DataFrame:
        for col, dtype in dtypes.items():
            if col not in df.columns:
                continue
            try:
                if dtype == "datetime":
                    df[col] = pd.to_datetime(df[col], errors="coerce")
                elif dtype == "int":
                    df[col] = pd.to_numeric(df[col], errors="coerce").astype("Int64")
                elif dtype == "float":
                    df[col] = pd.to_numeric(df[col], errors="coerce")
                elif dtype == "str":
                    df[col] = df[col].astype(str)
                elif dtype == "category":
                    df[col] = df[col].astype("category")
            except Exception as e:
                logger.warning(f"  类型转换失败 {col} -> {dtype}: {e}")
        return df


class DataCleaner:
    @staticmethod
    def strip_strings(df: pd.DataFrame) -> pd.DataFrame:
        str_cols = df.select_dtypes(include=["object"]).columns
        for col in str_cols:
            df[col] = df[col].astype(str).str.strip()
        return df

    @staticmethod
    def normalize_column_names(df: pd.DataFrame) -> pd.DataFrame:
        def normalize(name: str) -> str:
            name = re.sub(r"([A-Z]+)([A-Z][a-z])", r"\1_\2", name)
            name = re.sub(r"([a-z\d])([A-Z])", r"\1_\2", name)
            name = re.sub(r"[-\s]+", "_", name)
            name = re.sub(r"[^\w]", "", name)
            return name.lower().strip("_")
        df.columns = [normalize(c) for c in df.columns]
        return df

    @staticmethod
    def drop_duplicates(df: pd.DataFrame, subset: Optional[list[str]] = None) -> pd.DataFrame:
        before = len(df)
        df = df.drop_duplicates(subset=subset, keep="first")
        after = len(df)
        if before != after:
            logger.info(f"  去重: {before} -> {after} ({before - after} 行移除)")
        return df

    @staticmethod
    def drop_empty_rows(df: pd.DataFrame, subset: Optional[list[str]] = None) -> pd.DataFrame:
        before = len(df)
        if subset:
            df = df.dropna(subset=subset, how="all")
        else:
            df = df.dropna(how="all")
        after = len(df)
        if before != after:
            logger.info(f"  删除空行: {before} -> {after}")
        return df

    @staticmethod
    def fill_defaults(df: pd.DataFrame, defaults: dict[str, Any]) -> pd.DataFrame:
        for col, val in defaults.items():
            if col in df.columns:
                df[col] = df[col].fillna(val)
        return df

    @staticmethod
    def validate_email(df: pd.DataFrame, email_col: str) -> pd.DataFrame:
        if email_col not in df.columns:
            return df
        pattern = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
        mask = df[email_col].astype(str).str.match(pattern)
        invalid_count = (~mask).sum()
        if invalid_count > 0:
            logger.warning(f"  无效邮箱: {invalid_count} 行")
            df["_email_valid"] = mask
        return df

    @staticmethod
    def standardize_phone(df: pd.DataFrame, phone_col: str) -> pd.DataFrame:
        if phone_col not in df.columns:
            return df
        df[phone_col] = df[phone_col].astype(str).str.replace(r"[\s\-()（）]", "", regex=True)
        pattern = r"^(\+86)?1[3-9]\d{9}$"
        df["_phone_valid"] = df[phone_col].str.match(pattern)
        return df


class DataLoader:
    @staticmethod
    def to_postgres(df: pd.DataFrame, table_name: str, if_exists: str = "append", chunksize: int = BATCH_SIZE):
        logger.info(f"写入数据库: {table_name} ({len(df)} 行)")
        df["_etl_loaded_at"] = datetime.now(timezone.utc)
        df.to_sql(table_name, engine, if_exists=if_exists, index=False, method="multi", chunksize=chunksize)
        logger.info(f"  写入完成: {table_name}")


class ETLPipeline:
    def __init__(self, name: str):
        self.name = name
        self.ctx = PipelineContext(name)
        self.sources: list[DataSource] = []
        self.steps: list[TransformStep] = []

    def add_source(self, source: DataSource) -> "ETLPipeline":
        self.sources.append(source)
        return self

    def add_step(self, step: TransformStep) -> "ETLPipeline":
        self.steps.append(step)
        return self

    def run(self, target_table: Optional[str] = None) -> pd.DataFrame:
        logger.info(f"═══ 管道启动: {self.name} (run_id={self.ctx.run_id}) ═══")
        dfs = []
        for source in self.sources:
            df = DataExtractor.extract(source)
            df = DataExtractor.apply_column_mapping(df, source.column_mapping)
            df = DataExtractor.apply_dtypes(df, source.dtypes)
            dfs.append(df)
        if len(dfs) == 1:
            df = dfs[0]
        elif len(dfs) > 1:
            df = pd.concat(dfs, ignore_index=True)
        else:
            raise ValueError("至少需要一个数据源")
        self.ctx.stats["extract_rows"] = len(df)
        for step in self.steps:
            before = len(df)
            df = step.func(df)
            after = len(df)
            self.ctx.log_step(step.name, before, after, step.description)
            logger.info(f"转换步骤 [{step.name}]: {before} -> {after} 行")
        self.ctx.stats["transform_rows"] = len(df)
        self.ctx.stats["elapsed"] = (datetime.now(timezone.utc) - self.ctx.start_time).total_seconds()
        if target_table:
            DataLoader.to_postgres(df, target_table)
        logger.info(f"═══ 管道完成: {self.ctx.stats} ═══")
        return df

    def lineage_report(self) -> str:
        lines = [f"管道血缘: {self.name} (run_id={self.ctx.run_id})"]
        for entry in self.ctx.lineage:
            lines.append(
                f"  [{entry['step']}] {entry['rows_before']} → {entry['rows_after']} "
                f"({entry['rows_changed']:+d}) — {entry['description']}"
            )
        return "\n".join(lines)


class TransformFactory:
    @staticmethod
    def clean_all() -> list[TransformStep]:
        return [
            TransformStep("normalize_columns", DataCleaner.normalize_column_names, "标准化列名"),
            TransformStep("strip_strings", DataCleaner.strip_strings, "去除空白"),
            TransformStep("drop_duplicates", lambda df: DataCleaner.drop_duplicates(df), "去重"),
            TransformStep("drop_empty", lambda df: DataCleaner.drop_empty_rows(df), "删除空行"),
        ]


def ecommerce_order_pipeline():
    orders_source = DataSource(
        name="orders_csv", source_type=SourceType.CSV,
        path_or_url="./data/orders_2024.csv",
        column_mapping={
            "Order ID": "order_id", "Customer Name": "customer_name",
            "Email": "email", "Phone": "phone", "Product": "product_name",
            "Quantity": "quantity", "Price": "unit_price",
            "Order Date": "order_date", "Status": "status",
        },
        dtypes={"order_date": "datetime", "quantity": "int", "unit_price": "float"},
    )
    pipeline = ETLPipeline("电商订单数据处理")
    pipeline.add_source(orders_source)
    for step in TransformFactory.clean_all():
        pipeline.add_step(step)
    pipeline.add_step(TransformStep(
        "calculate_total",
        lambda df: df.assign(total_amount=df["quantity"] * df["unit_price"]),
        "计算订单总额",
    ))
    pipeline.add_step(TransformStep(
        "categorize_order_size",
        lambda df: df.assign(order_size=pd.cut(
            df["total_amount"], bins=[0, 100, 500, 2000, float("inf")],
            labels=["小额", "中额", "大额", "巨额"],
        )),
        "订单金额分级",
    ))
    df = pipeline.run(target_table="processed_orders")
    print(pipeline.lineage_report())
    return df


if __name__ == "__main__":
    df = ecommerce_order_pipeline()
    print(f"\n最终数据: {len(df)} 行, {len(df.columns)} 列")
    print(df.head().to_string())
