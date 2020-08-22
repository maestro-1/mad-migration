from madmigration.db_init.connection_engine import SourceDB
from madmigration.db_init.connection_engine import DestinationDB
from madmigration.mysqldb.migration import Migrate
from madmigration.utils.helpers import detect_driver, get_cast_type, get_column_type
from sqlalchemy import Column, MetaData, Table
from madmigration.config.conf import Config
from sqlalchemy import (
    Integer,
    String,
    DateTime,
    Date,
    BigInteger,
    VARCHAR,
    Float,
    TIMESTAMP
)


class Controller:
    def __init__(self, migration_config: Config):
        self.config = migration_config

        # Source and Destination DB Initialization with session
        self.sourceDB = SourceDB(self.config)
        self.destinationDB = DestinationDB(self.config)
        self.metadata = MetaData()

        # Source and Destination Database - all tables (NOT MIGRATION TABLES!!!)
        self.sourceDB_all_tables_names = self.sourceDB.engine.table_names()
        self.destinationDB_all_tables_names = self.destinationDB.engine.table_names()

        # All migration tables (Yaml file migrationTables)
        self.migration_tables = self.config.migrationTables

        # Destination DB Driver and name
        self.destinationDB_driver = self.destinationDB.engine.driver
        self.destinationDB_name = self.destinationDB.engine.name

    def prepare_tables(self):
        # detect migration class
        migrate = detect_driver(self.destinationDB_driver)
        for migrate_table in self.migration_tables:
            mig = migrate(migrate_table.migrationTable)
            mig.create_tables(self.destinationDB.engine)

    def get_column_type_from_source_table(self, table_name, column_name):
        """
        Get type of column in source table from Source Database
        :param table_name: Table name
        :param column_name: Column name
        :return: Column type (Integer, Varchar, Float, Double, etc...)
        """
        tables = self.sourceDB.base.metadata.tables
        table = tables.get(table_name)
        for column in table.columns:
            if column.name == column_name:
                return column.type

    def run(self):
        for mt in self.migration_tables:
            migrate = Migrate(mt.migrationTable, self.sourceDB)

            # This columns list and table name is going to be sent to function
            # Based on this get_data_from_source_table function will yield data
            columns = []
            for column in migrate.columns:
                columns.append(column.sourceColumn.get("name"))

            data = migrate.get_data_from_source_table(mt.migrationTable.SourceTable, columns)

            # for i in data:
            #     print(i)











