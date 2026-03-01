from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

import sqlglot
from open_data_contract_standard.model import CustomProperty, OpenDataContractStandard, SchemaObject, SchemaProperty
from sqlglot import expressions as exp

from contracthub.importers.base import BaseImporter


class SQLFolderImporter(BaseImporter):
    def __init__(self, folder_path: str, logger: Optional[logging.Logger] = None) -> None:
        super().__init__(logger=logger)
        self.folder_path = Path(folder_path).expanduser().resolve()

    def _build_imported_contract(self) -> Dict[str, Any]:
        if not self.folder_path.is_dir():
            raise ValueError(f"Folder does not exist: {self.folder_path}")

        sql_files = sorted(self.folder_path.glob("*.sql"))
        if not sql_files:
            raise ValueError(f"No .sql files found under folder: {self.folder_path}")

        dataset_name = self.folder_path.name
        contract_id = _to_contract_id(dataset_name)
        schema_objects: List[SchemaObject] = []

        for sql_file in sql_files:
            self.logger.info("Parsing SQL file: %s", sql_file)
            sql_text = sql_file.read_text(encoding="utf-8")
            statements = sqlglot.parse(sql_text, read="spark")
            for statement in statements:
                schema_object = _create_schema_object_from_statement(statement)
                if schema_object is not None:
                    schema_objects.append(schema_object)

        if not schema_objects:
            raise ValueError(f"No CREATE TABLE statements found under folder: {self.folder_path}")

        contract_model = OpenDataContractStandard(
            apiVersion="v3.1.0",
            kind="DataContract",
            id=contract_id,
            name=dataset_name,
            version="1.0.0",
            status="draft",
            schema=schema_objects,
            customProperties=[CustomProperty(property="contracthub.source", value="sql-folder")],
        )
        return contract_model.model_dump(by_alias=True, exclude_none=True)

    def _set_source(self, source: str) -> None:
        self.folder_path = Path(source).expanduser().resolve()


def _to_contract_id(dataset_name: str) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9._-]+", "-", dataset_name).strip("-")
    return cleaned.lower() or "sql-dataset"


def _create_schema_object_from_statement(statement: exp.Expression) -> Optional[SchemaObject]:
    if not isinstance(statement, exp.Create):
        return None
    if str(statement.args.get("kind") or "").upper() != "TABLE":
        return None

    table_expression = statement.find(exp.Table)
    if table_expression is None:
        return None

    table_name, table_physical_name = _get_table_name_info(table_expression)
    if not table_name:
        return None

    table_description, table_physical_type, table_custom_properties, partition_positions = _extract_table_metadata(
        statement
    )
    primary_key_positions, unique_columns = _extract_key_constraints(statement, table_name)
    columns = _extract_columns(
        statement,
        table_name=table_name,
        primary_key_positions=primary_key_positions,
        unique_columns=unique_columns,
        partition_positions=partition_positions,
    )
    if not columns:
        return None

    return SchemaObject(
        id=_to_contract_id(table_physical_name),
        name=table_name,
        physicalName=table_physical_name,
        logicalType="object",
        physicalType=table_physical_type,
        description=table_description,
        customProperties=table_custom_properties or None,
        properties=columns,
    )


def _get_table_name_info(table_expression: exp.Table) -> Tuple[str, str]:
    logical_name = table_expression.name or ""
    physical_name = table_expression.sql(dialect="spark")
    return logical_name, physical_name


def _extract_table_metadata(
    statement: exp.Create,
) -> Tuple[Optional[str], str, List[CustomProperty], Dict[str, int]]:
    description: Optional[str] = None
    physical_type = "table"
    custom_properties: List[CustomProperty] = []
    partition_positions: Dict[str, int] = {}

    properties = statement.args.get("properties")
    if not isinstance(properties, exp.Properties):
        return description, physical_type, custom_properties, partition_positions

    for property_expr in properties.expressions:
        if isinstance(property_expr, exp.ExternalProperty):
            physical_type = "external-table"
            custom_properties.append(CustomProperty(property="contracthub.table.external", value="true"))
        elif isinstance(property_expr, exp.SchemaCommentProperty) and property_expr.this is not None:
            description = str(property_expr.this).strip("'\"")
        elif isinstance(property_expr, exp.LocationProperty) and property_expr.this is not None:
            custom_properties.append(
                CustomProperty(
                    property="contracthub.table.location",
                    value=str(property_expr.this).strip("'\""),
                )
            )
        elif isinstance(property_expr, exp.FileFormatProperty) and property_expr.this is not None:
            custom_properties.append(
                CustomProperty(
                    property="contracthub.table.format",
                    value=str(property_expr.this).strip("'\""),
                )
            )
        elif isinstance(property_expr, exp.PartitionedByProperty):
            partition_columns = _extract_partition_columns(property_expr)
            for idx, column_name in enumerate(partition_columns, start=1):
                partition_positions[column_name.lower()] = idx

    return description, physical_type, custom_properties, partition_positions


def _extract_partition_columns(partition_property: exp.PartitionedByProperty) -> List[str]:
    partition_columns: List[str] = []
    partition_schema = partition_property.args.get("this")
    if not isinstance(partition_schema, exp.Schema):
        return partition_columns

    for item in partition_schema.expressions:
        if isinstance(item, exp.Identifier):
            partition_columns.append(item.name)
    return partition_columns


def _extract_key_constraints(statement: exp.Create, table_name: str) -> Tuple[Dict[str, int], Set[str]]:
    primary_key_positions: Dict[str, int] = {}
    unique_columns: Set[str] = set()

    for constraint in statement.find_all(exp.Constraint):
        expressions = constraint.args.get("expressions") or []
        for constraint_expr in expressions:
            if isinstance(constraint_expr, exp.PrimaryKey):
                for idx, item in enumerate(constraint_expr.expressions or [], start=1):
                    if isinstance(item, exp.Identifier):
                        primary_key_positions[item.name.lower()] = idx
            elif isinstance(constraint_expr, exp.UniqueColumnConstraint):
                schema_expr = constraint_expr.args.get("this")
                if isinstance(schema_expr, exp.Schema):
                    for item in schema_expr.expressions:
                        if isinstance(item, exp.Identifier):
                            unique_columns.add(item.name.lower())

    # Support inline PRIMARY KEY / UNIQUE on top-level columns.
    inline_pk_idx = len(primary_key_positions)
    for column in statement.find_all(exp.ColumnDef):
        parent_table = _get_parent_table_name(column)
        if parent_table and parent_table.lower() != table_name.lower():
            continue
        column_name = column.this.name if column.this is not None else None
        if not column_name:
            continue
        normalized = column_name.lower()
        if normalized not in primary_key_positions and column.find(exp.PrimaryKeyColumnConstraint) is not None:
            inline_pk_idx += 1
            primary_key_positions[normalized] = inline_pk_idx
        if column.find(exp.UniqueColumnConstraint) is not None:
            unique_columns.add(normalized)

    return primary_key_positions, unique_columns


def _extract_columns(
    statement: exp.Create,
    table_name: str,
    primary_key_positions: Dict[str, int],
    unique_columns: Set[str],
    partition_positions: Dict[str, int],
) -> List[SchemaProperty]:
    columns: List[SchemaProperty] = []

    for column in statement.find_all(exp.ColumnDef):
        parent_table = _get_parent_table_name(column)
        if parent_table and parent_table.lower() != table_name.lower():
            continue

        column_name = column.this.name if column.this is not None else None
        if not column_name:
            continue

        kind = column.args.get("kind")
        data_type = _column_type(column)
        nullable = _column_nullable(column)
        comment = _column_comment(column)
        normalized_name = column_name.lower()
        primary_key_position = primary_key_positions.get(normalized_name)
        partition_key_position = partition_positions.get(normalized_name)

        columns.append(
            _schema_property_from_data_type(
                name=column_name,
                kind=kind,
                physical_type=data_type,
                required=not nullable,
                description=comment,
                primary_key_position=primary_key_position,
                unique=normalized_name in unique_columns,
                partition_key_position=partition_key_position,
            )
        )

    return columns


def _get_parent_table_name(column: exp.ColumnDef) -> Optional[str]:
    parent = column.parent
    if isinstance(parent, exp.Schema) and isinstance(parent.this, exp.Table):
        return parent.this.name
    return None


def _column_type(column: exp.ColumnDef) -> str:
    kind = column.args.get("kind")
    if not isinstance(kind, exp.DataType):
        return "string"
    return kind.sql(dialect="spark")


def _column_nullable(column: exp.ColumnDef) -> bool:
    if column.find(exp.NotNullColumnConstraint) is not None:
        return False
    if column.find(exp.PrimaryKeyColumnConstraint) is not None:
        return False
    return True


def _column_comment(column: exp.ColumnDef) -> Optional[str]:
    comments = getattr(column, "comments", None)
    if comments:
        normalized = [c.strip() for c in comments if isinstance(c, str) and c.strip()]
        if normalized:
            return " ".join(normalized)

    for constraint in column.find_all(exp.CommentColumnConstraint):
        if constraint.this:
            return str(constraint.this).strip("'\"")
    return None


def _schema_property_from_data_type(
    *,
    name: Optional[str],
    kind: Any,
    physical_type: str,
    required: bool,
    description: Optional[str],
    primary_key_position: Optional[int],
    unique: bool,
    partition_key_position: Optional[int],
) -> SchemaProperty:
    data_type = kind if isinstance(kind, exp.DataType) else None
    logical_type = _map_sql_type_to_odcs(physical_type)

    logical_type_options: Optional[Dict[str, Any]] = None
    nested_properties: Optional[List[SchemaProperty]] = None
    items: Optional[SchemaProperty] = None

    if data_type is not None:
        logical_type_options = _extract_logical_type_options(data_type)
        nested_properties = _extract_nested_properties(data_type)
        items = _extract_items(data_type)

    return SchemaProperty(
        id=_to_contract_id(name or physical_type),
        name=name,
        physicalName=name,
        logicalType=logical_type,
        physicalType=physical_type,
        logicalTypeOptions=logical_type_options,
        required=required,
        description=description,
        primaryKey=primary_key_position is not None,
        primaryKeyPosition=primary_key_position,
        unique=unique if unique else None,
        partitioned=partition_key_position is not None,
        partitionKeyPosition=partition_key_position,
        properties=nested_properties,
        items=items,
    )


def _extract_logical_type_options(data_type: exp.DataType) -> Optional[Dict[str, Any]]:
    options: Dict[str, Any] = {}
    type_name = _data_type_name(data_type)

    if type_name == "DECIMAL":
        params = [p.this for p in data_type.expressions if isinstance(p, exp.DataTypeParam)]
        if len(params) >= 1 and isinstance(params[0], exp.Literal):
            options["precision"] = int(str(params[0]))
        if len(params) >= 2 and isinstance(params[1], exp.Literal):
            options["scale"] = int(str(params[1]))

    if type_name == "MAP":
        key_type = data_type.expressions[0].sql(dialect="spark") if data_type.expressions else None
        if key_type:
            options["keyType"] = key_type

    return options or None


def _extract_nested_properties(data_type: exp.DataType) -> Optional[List[SchemaProperty]]:
    if _data_type_name(data_type) != "STRUCT":
        return None

    nested_properties: List[SchemaProperty] = []
    for child in data_type.expressions or []:
        if not isinstance(child, exp.ColumnDef):
            continue
        child_name = child.this.name if child.this is not None else None
        child_kind = child.args.get("kind")
        child_physical_type = _column_type(child)
        child_required = not _column_nullable(child)
        child_description = _column_comment(child)
        nested_properties.append(
            _schema_property_from_data_type(
                name=child_name,
                kind=child_kind,
                physical_type=child_physical_type,
                required=child_required,
                description=child_description,
                primary_key_position=None,
                unique=False,
                partition_key_position=None,
            )
        )
    return nested_properties or None


def _extract_items(data_type: exp.DataType) -> Optional[SchemaProperty]:
    type_name = _data_type_name(data_type)
    if type_name == "ARRAY" and data_type.expressions:
        item_type = data_type.expressions[0]
        if isinstance(item_type, exp.DataType):
            return _schema_property_from_data_type(
                name=None,
                kind=item_type,
                physical_type=item_type.sql(dialect="spark"),
                required=False,
                description=None,
                primary_key_position=None,
                unique=False,
                partition_key_position=None,
            )

    if type_name == "MAP" and len(data_type.expressions) >= 2:
        value_type = data_type.expressions[1]
        if isinstance(value_type, exp.DataType):
            return _schema_property_from_data_type(
                name=None,
                kind=value_type,
                physical_type=value_type.sql(dialect="spark"),
                required=False,
                description=None,
                primary_key_position=None,
                unique=False,
                partition_key_position=None,
            )

    return None


def _map_sql_type_to_odcs(sql_type: str) -> str:
    normalized = sql_type.lower()
    if normalized.startswith(("string", "varchar", "char", "text")):
        return "string"
    if normalized.startswith(("int", "bigint", "smallint", "tinyint")):
        return "integer"
    if normalized.startswith(("decimal", "numeric", "double", "float", "real")):
        return "number"
    if normalized.startswith(("boolean", "bool")):
        return "boolean"
    if normalized.startswith("date"):
        return "date"
    if normalized.startswith(("timestamp", "datetime")):
        return "timestamp"
    if normalized.startswith(("binary", "varbinary")):
        return "binary"
    if normalized.startswith("array"):
        return "array"
    if normalized.startswith(("map", "struct")):
        return "object"
    return "string"


def _data_type_name(data_type: exp.DataType) -> str:
    token = data_type.this
    if hasattr(token, "name"):
        return str(token.name).upper()
    return str(token).replace("Type.", "").upper()
