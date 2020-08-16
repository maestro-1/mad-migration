from pydantic import BaseModel
from typing import Union,List,Any,AnyStr,Dict,Mapping
from datetime import datetime


class OptionsSchema(BaseModel):
    primary_key: bool = False
    nullable: bool = False
    default: bool = None
    index: bool = None
    unique: bool = None
    autoincrement: bool = True
    foreign_keys: bool = False

    type_cast: AnyStr = None


class SourceConfigSchema(BaseModel):
    SourceConfig: Dict[str,str]


class DestinationConfigSchema(BaseModel):
    DestinationConfig: Dict[str,str]


class SourceTableSchema(BaseModel):
    name: Dict[str, str]


class ColumnParameters(BaseModel):
    destinationColumn: Any
    sourceColumn: Any
    options: OptionsSchema = None


class TablesInfo(BaseModel):
    SourceTable: Dict[str, str]
    DestinationTable: Dict[str, str]
    MigrationColumns: List[ColumnParameters]


class MigrationTablesSchema(BaseModel):
    migrationTable: TablesInfo


class ConfigSchema(BaseModel):
    Configs: List[Union[SourceConfigSchema,DestinationConfigSchema]]
    migrationTables: List[MigrationTablesSchema]
    version: float