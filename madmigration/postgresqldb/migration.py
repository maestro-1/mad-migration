from madmigration.config.config_schema import MigrationTablesSchema
from madmigration.config.config_schema import ColumnParametersSchema
from madmigration.config.config_schema import TablesInfo
from sqlalchemy import Column, Table, MetaData, ForeignKey, ForeignKeyConstraint
from sqlalchemy.engine import reflection
from madmigration.errors import TableExists
from sqlalchemy.ext.mutable import MutableDict
from collections import defaultdict
from sqlalchemy.dialects.postgresql import (
    ARRAY,
    BIGINT,
    BIT,
    BOOLEAN,
    BYTEA,
    CHAR,
    DATE,
    # DOUBLE_PRECISION,
    # ENUM,
    FLOAT,
    INET,
    INTEGER,
    # INTERVAL,
    JSON,
    JSONB,
    MACADDR,
    MONEY,
    NUMERIC,
    OID,
    REAL,
    SMALLINT,
    TEXT,
    TIME,
    TIMESTAMP,
    VARCHAR,
)
from sqlalchemy import DateTime
from sqlalchemy_utils import UUIDType
from madmigration.config.conf import Config
from madmigration.db_operations.operations import DbOperations
from pprint import pprint


class Migrate: 
    def __init__(self, config: Config,destination_db):
        self.global_config = config
        self.migration_tables = config.migrationTables
        self.engine = destination_db.engine
        self.connection = destination_db
        self.metadata = MetaData()
        self.table_list = set()
        self.table_create = defaultdict(list)
        self.table_update = defaultdict(list)
        self.alter_col = defaultdict(list)
        self.fk_constraints = []
        self.dest_fk = []
        self.db_operations = DbOperations(self.engine)
        self.collect_table_names()
        self.collect_drop_fk()
    
    def __enter__(self):
        return self

    def __exit__(self, type, value, traceback):
        self.engine.session.close()

    def collect_table_names(self):
        """ collects all tables that the program should create """
        try:
            for migrate_table in self.migration_tables:
                # pprint(migrate_table.dict().keys())
                
                tabel_name = migrate_table.migrationTable.DestinationTable.name
                self.table_list.add(tabel_name)
        except Exception as err:
            print("err -> ",err)

    def collect_drop_fk(self):
        """ 
        Collect foreign key constraints for tables so 
        that if something goes wrong, delete everything
        """
        try:
            conn = self.engine.connect()
            transactional = conn.begin()
            inspector = reflection.Inspector.from_engine(self.engine)

            for table_name in inspector.get_table_names():
                if table_name in self.table_list:
                    for fk in inspector.get_foreign_keys(table_name):
                        if not fk["name"]:
                            continue
                        self.dest_fk.append(ForeignKeyConstraint((), (), name=fk["name"]))
            transactional.commit()
        except Exception as err:
            print("err -> ",err)
            return False
        finally:
            conn.close()
    

    def parse_migration_tables(self,tabels_schema:MigrationTablesSchema):
        """
        This function parses migrationTables from yaml file
        """
        try:
            self.source_table = tabels_schema.migrationTable.SourceTable.dict()
            self.destination_table = tabels_schema.migrationTable.DestinationTable.dict()
            self.columns = tabels_schema.migrationTable.MigrationColumns
        except Exception as err:
            print("err -> ",err)


    def parse_migration_columns(
        self, tablename: str, migration_columns: ColumnParametersSchema
    ):
        """
        This function parses migrationColumns schema and prepare column
        """
        try:
            # table_name, column_name,type_=col_type, **options
            update = self.check_table(tablename)
                
            for col in migration_columns:
                self.source_column = col.sourceColumn
                self.destination_column = col.destinationColumn
                self.dest_options = col.destinationColumn.options.dict()

                self._parse_fk(tablename, self.dest_options.pop("foreign_key"))
                column_type = self._parse_column_type()

                col = Column(self.destination_column.name, column_type, **self.dest_options)
                if update:
                    if not self.check_column(tablename, self.destination_column.name):
                    #     self.add_alter_column(tablename, {"column_name": self.destination_column.name,"type":column_type,"options":{**self.dest_options}})
                    # else:
                        self.add_updated_table(tablename,col)
                else:
                    self.add_created_table(tablename,col)
        except Exception as err:
            print("parse_migration_columns err -> ",err)


    def add_updated_table(self,table_name: str, col: Column):
        self.table_update[table_name].append(col)

    def add_created_table(self,table_name: str, col: Column):
        self.table_create[table_name].append(col)

    def add_alter_column(self,table_name: str, col: Column):
        self.alter_col[table_name].append(col)

    def prepare_tables(self):
        try:
            for migrate_table in self.migration_tables:
                if migrate_table.migrationTable.DestinationTable.create:
                    self.parse_migration_tables(migrate_table)
                    self.parse_migration_columns(self.destination_table.get("name"),self.columns)
        except Exception as err:
            print("prepare_tables -> ",err)

    def update_table(self):
        
        for tab,col in self.table_update.items():
            self.db_operations.add_column(tab,*col)
        return True
    
    def alter_columns(self):
        for tab, val in self.alter_col.items():
            for i in val:
                self.db_operations.update_column(tab,i.pop("column_name"),i.pop("type"), **i.pop("options"))
        return True
    
    def create_tables(self):
        for tab, col in self.table_create.items():
            self.db_operations.create_table(tab,*col)
        return True

    def process(self):
        """
        Create and check existing tables. 
        Collect foreign key constraints
        """
        try:
            # self.alter_columns()
            self.update_table()
            self.create_tables()
            self.db_operations.create_fk_constraint(self.fk_constraints)
            return True
        except Exception as err:
            print("create_tables err -> ", err)

    def _parse_column_type(self) -> object:
        """ Parse column type and options (length,type and etc.) """
        
        try:
            column_type = Migrate.get_column_type(self.dest_options.pop("type_cast"))
            print(self.dest_options.get("length"))
            type_length = self.dest_options.pop("length")
            if type_length:
                column_type = column_type(type_length)
            return column_type
        except Exception as err:
            print(err)
        
        # print(self.dest_options.get("length"))
        type_length = self.dest_options.pop("length")
        if type_length:
            column_type = column_type(type_length)
        return column_type

    def _parse_fk(self, tablename, fk_options):
        """ Parse foreignkey and options (use_alter,colum and etc.) """
        try:
            if fk_options:
                fk_options["source_table"] = tablename
                fk_options["dest_column"] = self.destination_column.name
                self.fk_constraints.append(fk_options)
        except Exception as err:
            print("_parse_fk err -> ", err)


    def check_table(self, table_name: str) -> bool:
        """ Check table exist or not, and wait user input """
        try:
            if self.engine.dialect.has_table(self.engine.connect(), table_name):
                while True:
                    answ = input(
                        f"Table with name '{table_name}' already exist, recreate table?(y/n)"
                    )
                    if answ.lower() == "y":
                        msg = f"The table '{table_name}' will be dropped and recreated,your table data will be lost,process?(yes/no)"
                        rcv = input(msg)
                        if rcv.lower() == "yes":
                            self.db_operations.drop_fk(self.dest_fk)
                            self.db_operations.drop_table(table_name)
                            return False
                        elif rcv.lower() == "no":
                            return True
                    elif answ.lower() == "n":
                        return True
                    else:
                        continue
            return False
        except Exception as err:
            print(err)
            return False

        
    def get_table_attribute_from_base_class(self, source_table_name: str):
        """
        This function gets table name attribute from sourceDB.base.classes. Example sourceDB.base.class.(table name)
        Using this attribute we can query table using sourceDB.session
        :return table attribute
        """
        return getattr(self.connection.base.classes, source_table_name)

    def get_data_from_source_table(self, source_table_name: str, source_columns: list):

        table = self.get_table_attribute_from_base_class(source_table_name.name)
        rows = self.connection.session.query(table).yield_per(1)

        for row in rows:
            data = {}
            for column in source_columns:
                data[column] = getattr(row, column)
            yield data


    def check_column(self, table_name: str, column_name: str) -> bool:
        """
            Check column exist in destination table or not
            param:: column_name -> is destination column name
        """
        try:
            insp = reflection.Inspector.from_engine(self.engine)
            has_column = False
            for col in insp.get_columns(table_name):
                if column_name not in col["name"]:
                    continue
                return True
            return has_column
        except Exception as err:
            print("check_column err -> ",err)
            return False

    @staticmethod
    def get_column_type(type_name: str) -> object:
        """Get class of db type
        :param type_name: str
        :return: object class
        """
        return {
            "varchar": VARCHAR,
            "char": CHAR,
            "string": VARCHAR,
            "text": TEXT,
            "integer": INTEGER,
            "smallint": SMALLINT,
            "bigint": BIGINT,
            "binary": BYTEA,
            "boolean": BOOLEAN,
            "bool": BOOLEAN,
            "date": DATE,
            "datetime": DateTime,
            "timestamp": TIMESTAMP,
            "time": TIME,
            # "enum": ENUM,
            "float": FLOAT,
            "real": REAL,
            "json": MutableDict.as_mutable(JSON),
            "jsonb": MutableDict.as_mutable(JSONB),
            # "array": ARRAY, #FIXME column with array include array elemet type argument
            "numeric": NUMERIC,
            "money": MONEY,
            "macaddr": MACADDR,
            "inet": INET,
            "oid": OID,
            "uuid": UUIDType(binary=False),
        }.get(type_name.lower())


