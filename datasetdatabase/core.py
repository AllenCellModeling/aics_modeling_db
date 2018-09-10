#!/usr/bin/env python

# installed
from pandas import read_csv as pd_read_csv
from typing import Union, Dict, List
from datetime import datetime
import subprocess
import importlib
import inspect
import pathlib
import hashlib
import orator
import pickle
import types
import json
import uuid
import os

# self
from .introspect import ObjectIntrospector
from .introspect import RECONSTRUCTOR_MAP
from .introspect import INTROSPECTOR_MAP
from .introspect import Introspector

from .schema import FMSInterface
from .schema import SchemaVersion
from .utils import checks, tools

from .version import VERSION

# globals
REQUIRED_CONFIG_ITEMS = ("driver", "database")
MISSING_REQUIRED_ITEMS = "Config must have {i}.".format(i=REQUIRED_CONFIG_ITEMS)
MALFORMED_LOCAL_LINK = "Local databases must have suffix '.db'"

INVALID_DS_INFO = "This set of attributes could not be found in the linked db."
NO_DS_INFO = "There is no dataset info attached to this dataset object."
DATETIME_PARSE = "%Y-%m-%d %H:%M:%S.%f"

MISSING_PARAMETER = "Must provide at least one of the following parameters: {p}"
VERSION_LOOKUP = ["__version__", "__VERSION__", "VERSION", "version"]
UNKNOWN_DATASET_HASH = "Dataset hash changed.\n\tOriginal: {o}\n\tCurrent: {c}"

GENERIC_TYPES = Union[bytes, str, int, float, None, datetime]
MISSING_INIT = "Must provide either an object or a DatasetInfo object."
TOO_MANY_RETURN_VALUES = "Too many values returned from query expecting {n}."
DATASET_NOT_FOUND = "Dataset not found using keyword arguments:\n\t{kw}"

EXTENSION_MAP = {".csv": pd_read_csv,
                 ".dataset": tools.read_pickle}
UNKNOWN_EXTENSION = "Unsure how to read dataset from the passed path.\n\t{p}"


class DatabaseConfig(object):
    def __init__(self,
        config: Union[str, pathlib.Path, Dict[str, str]],
        name: Union[str, None] = None):
        # enforce types
        checks.check_types(name, [str, type(None)])
        checks.check_types(config, [str, pathlib.Path, dict])

        # convert types
        if isinstance(config, str):
            config = pathlib.Path(config)
        if isinstance(config, pathlib.Path):
            with open(config, "r") as read_in:
                config = json.load(read_in)

        # enforce config minimum attributes
        valid_config = all(k in config for k in REQUIRED_CONFIG_ITEMS)
        assert valid_config, MISSING_REQUIRED_ITEMS

        # passed enforcement
        self._config = config

        # assign name
        if name is None:
                self.name = pathlib.Path(self.config["database"])\
                            .with_suffix("")\
                            .name


    def __iter__(self):
        yield self.name, self.config


    @property
    def config(self):
        return self._config


    def __str__(self):
        return str(dict(self))


    def __repr__(self):
        return str(self)


class DatabaseConstructor(object):
    def __init__(self,
        config: Union[DatabaseConfig, None],
        schema: Union[SchemaVersion, None] = None,
        fms: Union[FMSInterface, None] = None):

        # enforce types
        checks.check_types(config, [DatabaseConfig, type(None)])
        checks.check_types(schema, [SchemaVersion, type(None)])
        checks.check_types(fms, [FMSInterface, type(None)])

        if config is None:
            config = LOCAL

        # store attributes
        self._config = config
        self._schema = schema
        self._fms = fms
        self._tables = []
        self._db = orator.DatabaseManager(dict(self.config))


    @property
    def config(self):
        return self._config


    @property
    def schema(self):
        # None passed, load default
        if self._schema is None:
            from .schema.minimal import MINIMAL
            self._schema = MINIMAL

        return self._schema


    @property
    def fms(self):
        # None passed, load default
        if self._fms is None:
            from .schema.filemanagers.quiltfms import QuiltFMS
            self._fms = QuiltFMS()

        return self._fms


    @property
    def tables(self):
        return self._tables


    @property
    def db(self):
        return self._db

    @property
    def orator_schema(self):
        return self._orator_schema


    def prepare_connection(self):
        # convert database link and enforce exists
        if self.config.config["driver"] == "sqlite":
            link = self.config.config["database"]
            link = pathlib.Path(link)
            assert link.suffix == ".db", MALFORMED_LOCAL_LINK
            if not link.exists():
                link.parent.mkdir(parents=True, exist_ok=True)


    def create_schema(self):
        # create all tables in version
        for tbl, func in self.schema.tables.items():
            func(self.orator_schema)
            if tbl not in self.tables:
                self._tables.append(tbl)

        # create file table from fms module
        if self.fms.table_name not in self.tables:
            self.fms.create_File(self.orator_schema)
            self._tables.append(self.fms.table_name)


    def build(self):
        # run preparation steps
        self.prepare_connection()

        # connect
        self._orator_schema = orator.Schema(self.db)

        # create schema
        self.create_schema()

        return self.db


    def drop_schema(self):
        # get drop order
        drop_order = list(self.schema.tables)
        drop_order.reverse()

        # drop
        for tbl in drop_order:
            self.schema.drop_if_exists()


    def get_tables(self):
        # run preparation steps
        self.prepare_connection()

        if self.config.config["driver"] == "sqlite":
            names = self.db.table("sqlite_master") \
                           .select("name") \
                           .where("type", "=", "table").get()
            names = [t["name"] for t in names if t["name"] != "sqlite_sequence"]
        else:
            names = self.db.table("pg_catalog.pg_tables") \
                           .select("tablename") \
                           .where("schemaname", "=", "public").get()

            names = [t.tablename for t in names]

        if "migrations" in names:
            names.remove("migrations")

        self._tables = names
        return self.db


class DatasetDatabase(object):
    def __init__(self,
        config: Union[DatabaseConfig, str, pathlib.Path, None] = None,
        user: Union[str, None] = None,
        constructor: Union[DatabaseConstructor, None] = None,
        build: bool = False,
        recent_size: int = 5):

        # enforce types
        checks.check_types(config,
                           [DatabaseConfig, str, pathlib.Path, type(None)])
        checks.check_types(user, [str, type(None)])
        checks.check_types(constructor, [DatabaseConstructor, type(None)])
        checks.check_types(recent_size, int)

        # assume local
        if config is None:
            config = LOCAL

        # read config
        if isinstance(config, (str, pathlib.Path)):
            config = DatabaseConfig(config)

        # state basic items
        self._config = config
        self._user = checks.check_user(user)
        self.recent_size = recent_size

        # create constructor
        if constructor is None:
            self._constructor = DatabaseConstructor(self.config)

        # connect
        if build:
            self._db = self.constructor.build()
        else:
            self._db = self.constructor.get_tables()

        # upload basic items
        self._user_info = self.get_or_create_user(self.user)


    @property
    def config(self):
        return self._config


    @property
    def user(self):
        return self._user

    @property
    def user_info(self):
        return self._user_info


    @property
    def constructor(self):
        return self._constructor


    @property
    def db(self):
        return self._db


    def get_or_create_user(self,
        user: Union[str, None] = None,
        description: Union[str, None] = None) -> Dict[str, GENERIC_TYPES]:

        # enforce types
        checks.check_types(user, [str, type(None)])
        checks.check_types(description, [str, type(None)])

        # get default
        if user is None:
            user = self._user

        # check the os user
        user = checks.check_user(user)
        # if valid set user
        self._user = user

        # attempt get
        user_info = self.get_items_from_table("User", ["Name", "=", user])

        # not found
        if len(user_info) == 0:
            return self._insert_to_table("User",
                {"Name": user,
                 "Description": description,
                 "Created": datetime.now()})

        # found
        if len(user_info) == 1:
            return user_info[0]

        # database structure error
        raise ValueError(TOO_MANY_RETURN_VALUES.format(n=1))


    def get_or_create_algorithm(self,
        algorithm: Union[types.MethodType, types.FunctionType],
        name: Union[str, None] = None,
        description: Union[str, None] = None,
        version: Union[str, None] = None) -> Dict[str, GENERIC_TYPES]:

        # enforce types
        checks.check_types(algorithm, [types.MethodType, types.FunctionType])
        checks.check_types(name, [str, type(None)])
        checks.check_types(description, [str, type(None)])
        checks.check_types(version, [str, type(None)])

        # get name
        if name is None:
            name = str(algorithm)
            method = "<bound method "
            function = "<function "
            end_at = " at "
            end_of = " of "
            try:
                end_index = name.index(end_at)
            except ValueError:
                end_index = name.index(end_of)
            if method in name:
                name = name[len(method): end_index]
            else:
                name = name[len(function): end_index]

        # get description
        if description is None:
            description = "Originally created by {u}".format(u=self.user)

        # get version
        if version is None:
            # naive module version lookup
            module = inspect.getmodule(algorithm)
            attrs = dir(module)
            for v_lookup in VERSION_LOOKUP:
                if v_lookup in attrs:
                    version = getattr(module, v_lookup)
                    break

            # naive git repo version lookup
            if version is None:
                version = ""
                try:
                    git_dir = os.path.dirname(os.path.abspath(__file__))
                    version = subprocess.check_output(
                        ["git", "rev-list", "-1", "HEAD", "./"], cwd=git_dir)
                    version = version.strip()
                    version = version.decode("utf-8")
                except subprocess.CalledProcessError:
                    pass

            if version == "":
                raise ValueError("Could not determine version of algorithm.")

        # enforce version string
        version = str(version)

        # get or create alg
        alg_info = self.get_items_from_table("Algorithm", [
            ["Name", "=", name], ["Version", "=", version]])

        # found
        if len(alg_info) == 1:
            return alg_info[0]
        # new
        elif len(alg_info) == 0:
            alg_info = self._insert_to_table("Algorithm",
                {"Name": name,
                 "Description": description,
                 "Version": version,
                 "Created": datetime.now()})
            return alg_info

        # database structure error
        else:
            raise ValueError(TOO_MANY_RETURN_VALUES.format(n=1))


    def process(self,
        algorithm: Union[types.MethodType, types.FunctionType],
        input_dataset: Union["Dataset", None] = None,
        input_dataset_info: Union["DatasetInfo", None] = None,
        input_dataset_id: Union[int, None] = None,
        input_dataset_name: Union[str, None] = None,
        algorithm_name: Union[str, None] = None,
        algorithm_description: Union[str, None] = None,
        algorithm_version: Union[str, None] = None,
        run_name: Union[str, None] = None,
        run_description: Union[str, None] = None,
        algorithm_parameters: dict = {},
        output_dataset_name: Union[str, None] = None,
        output_dataset_description: Union[str, None] = None) -> "Dataset":

        # enforce types
        checks.check_types(algorithm, [types.MethodType, types.FunctionType])
        checks.check_types(input_dataset, [Dataset, type(None)])
        checks.check_types(input_dataset_info, [DatasetInfo, type(None)])
        checks.check_types(input_dataset_id, [int, type(None)])
        checks.check_types(input_dataset_name, [str, type(None)])
        checks.check_types(algorithm_name, [str, type(None)])
        checks.check_types(algorithm_description, [str, type(None)])
        checks.check_types(algorithm_version, [str, type(None)])
        checks.check_types(run_name, [str, type(None)])
        checks.check_types(run_description, [str, type(None)])
        checks.check_types(algorithm_parameters, dict)
        checks.check_types(output_dataset_name, [str, type(None)])
        checks.check_types(output_dataset_description, [str, type(None)])

        # must provide input dataset info
        dataset_lookups = [input_dataset, input_dataset_info,
                           input_dataset_id, input_dataset_name]
        assert any(i is not None for i in dataset_lookups), \
            MISSING_PARAMETER.format(p=dataset_lookups)

        # convert dataset to workable type
        if input_dataset is not None:
            # check hash
            found_ds = self.get_items_from_table(
                "Dataset", ["MD5", "=", input_dataset.md5])

            # found
            if len(found_ds) == 1:
                ds_info = found_ds[0]
                ds_info["OriginDb"] = self
                input_dataset._info = DatasetInfo(**ds_info)
                input = input_dataset

            # not found
            elif len(found_ds) == 0:
                input = input_dataset

            # database structure error
            else:
                raise ValueError(TOO_MANY_RETURN_VALUES.format(n=1))

        elif input_dataset_info is not None:
            input = input_dataset_info.origin.get_dataset(input_dataset_info.id)
        elif input_dataset_id is not None:
            input = self.get_dataset(id=input_dataset_id)
        else:
            input = self.get_dataset(name=input_dataset_name)

        # create algorithm info before run
        alg_info = self.get_or_create_algorithm(algorithm,
                                                algorithm_name,
                                                algorithm_description,
                                                algorithm_version)

        # check parameters for dsdb parameters
        if algorithm_name == "dsdb.Dataset.store_files":
            db = algorithm_parameters.pop("db", None)
            fms = algorithm_parameters.pop("fms", None)

            alg_params_ds = self._create_dataset(algorithm_parameters,
                description="algorithm parameters")

            algorithm_parameters["db"] = db
            algorithm_parameters["fms"] = fms

        # store params used
        else:
            alg_params_ds = self._create_dataset(algorithm_parameters,
                description="algorithm parameters")

        # begin
        print("Dataset processing has begun...")
        begin = datetime.now()

        # run
        output = algorithm(input, **algorithm_parameters)

        # end
        end = datetime.now()
        print("Dataset processing has ended...")

        # ingest output
        output = self._create_dataset(output,
             name=output_dataset_name,
             description=output_dataset_description)

        # update run table
        run_info = self._insert_to_table("Run",
            {"AlgorithmId": alg_info["AlgorithmId"],
             "UserId": self.user_info["UserId"],
             "Name": run_name,
             "Description": run_description,
             "AlgorithmParameters": alg_params_ds.info.id,
             "Begin": begin,
             "End": end})

        # update run input table
        if input.info is not None:
            self._insert_to_table("RunInput",
                {"RunId": run_info["RunId"],
                 "DatasetId": input.info.id,
                 "Created": end})

        # update run output table
        self._insert_to_table("RunOutput",
            {"RunId": run_info["RunId"],
             "DatasetId": output.info.id,
             "Created": end})

        return output


    def _create_dataset(self,
        dataset: Union["Dataset", object],
        **kwargs) -> "DatasetInfo":

        # enforce types
        checks.check_types(dataset, [Dataset, object])

        # convert dataset
        if not isinstance(dataset, Dataset):
            dataset = Dataset(dataset, **kwargs)

        # check hash
        found_ds = self.get_items_from_table(
            "Dataset", ["MD5", "=", dataset.md5])

        # found
        if len(found_ds) == 1:
            ds_info = found_ds[0]
            ds_info["OriginDb"] = self
            ds_info = DatasetInfo(**ds_info)

            return Dataset(dataset=dataset.ds, ds_info=ds_info)

        # not found
        elif len(found_ds) == 0:
            introspector_module = str(type(dataset.introspector))
            begin = len("<class '")
            end = introspector_module.index("'>")
            introspector_module = introspector_module[begin: end]
            ds_info = {"Name": dataset.name,
                       "Description": dataset.description,
                       "Introspector": introspector_module,
                       "MD5": dataset.md5,
                       "SHA256": dataset.sha256,
                       "Created": dataset.created}
            ds_info["DatasetId"] = self.db.table("Dataset")\
                .insert_get_id(ds_info, sequence=("DatasetId"))
            ds_info["OriginDb"] = self

            ds_info = DatasetInfo(**ds_info)

        # database structure error
        else:
            raise ValueError(TOO_MANY_RETURN_VALUES.format(n=1))

        # deconstruct
        storage = dataset.introspector.deconstruct()

        iota_ids = []
        # insert iota
        for i, iota in enumerate(storage["Iota"]):
            match = {"list_index": i,
                     "db_id": self._insert_to_table("Iota", iota)["IotaId"]}
            iota_ids.append(match)

        # insert groups
        group_ids = []
        for i, group in enumerate(storage["Group"]):
            match = {"list_index": i,
                     "db_id": self._insert_to_table("Group", group)["GroupId"]}
            group_ids.append(match)

        # insert iota group joins
        iota_group_ids = []
        for i, iota_group in enumerate(storage["IotaGroup"]):
            iota_match = list(filter(lambda iota_id:
                iota_id["list_index"] == iota_group["IotaId"], iota_ids))[0]
            group_match = list(filter(lambda group_id:
                group_id["list_index"] == iota_group["GroupId"], group_ids))[0]
            db_iota_group = {"IotaId": iota_match["db_id"],
                             "GroupId": group_match["db_id"],
                             "Created": iota_group["Created"]}
            iota_group_ids.append(self._insert_to_table(
                "IotaGroup", db_iota_group)["IotaGroupId"])

        # insert group dataset joins
        for group_id_match in group_ids:
            group_dataset = {"GroupId": group_id_match["db_id"],
                             "DatasetId": ds_info.id,
                             "Created": datetime.now()}
            self._insert_to_table("GroupDataset", group_dataset)

        # attach info to a dataset
        return Dataset(dataset = dataset.ds, ds_info = ds_info)


    def _upload_dataset(self, dataset, **params):
        return dataset


    def upload_dataset(self, dataset: "Dataset", **kwargs) -> "DatasetInfo":
        # enforce types
        checks.check_types(dataset, Dataset)

        # enforce no change
        current_hash = tools.get_object_hash(dataset.ds)
        assert current_hash == dataset.md5, UNKNOWN_DATASET_HASH.format(
            o=dataset.md5, c=current_hash)

        create_params = {}
        create_params["algorithm"] = self._upload_dataset
        create_params["input_dataset"] = dataset
        create_params["algorithm_name"] = "upload_dataset"
        create_params["algorithm_description"] = "DSDB ingest dataset function"
        create_params["algorithm_version"] = VERSION
        create_params["output_dataset_name"] = dataset.name
        create_params["output_dataset_description"] = dataset.description

        return self.process(**create_params)


    def get_dataset(self,
        id: Union[int, None] = None,
        name: Union[str, None] = None,
        md5: Union[str, None] = None,
        sha256: Union[str, None] = None) -> "Dataset":

        # enforce types
        checks.check_types(id, [int, type(None)])
        checks.check_types(name, [str, type(None)])
        checks.check_types(md5, [str, type(None)])
        checks.check_types(sha256, [str, type(None)])

        # must pass parameter
        assert any(i is not None for i in [id, name, md5, sha256]), \
            MISSING_PARAMETER.format(p=[id, name, md5, sha256])

        # get ds_info
        if id is not None:
            found_ds = self.get_items_from_table(
                "Dataset", ["DatasetId", "=", id])
        elif name is not None:
            found_ds = self.get_items_from_table(
                "Dataset", ["Name", "=", name])
        elif md5 is not None:
            found_ds = self.get_items_from_table(
                "Dataset", ["MD5", "=", md5])
        else:
            found_ds = self.get_items_from_table(
                "Dataset", ["SHA256", "=", sha256])

        # found
        if len(found_ds) == 1:
            ds_info = found_ds[0]
            ds_info["OriginDb"] = self
            ds_info = DatasetInfo(**ds_info)

        # not found
        elif len(found_ds) == 0:
            raise ValueError(DATASET_NOT_FOUND.format(kw=locals()))

        # database structure error
        else:
            raise ValueError(TOO_MANY_RETURN_VALUES.format(n=1))

        # create items map
        items = {}

        # get group dataset joins
        group_dataset = self.get_items_from_table(
            "GroupDataset", ["DatasetId", "=", ds_info.id])

        # get groups
        group = []
        for gd in group_dataset:
            group += self.get_items_from_table(
                "Group", ["GroupId", "=", gd["GroupId"]])
        items["Group"] = group

        # get iota group joins
        iota_group = []
        for g in group:
            iota_group += self.get_items_from_table(
                "IotaGroup", ["GroupId", "=", g["GroupId"]])
        items["IotaGroup"] = iota_group

        # get iota
        iota = []
        for ig in iota_group:
            iota += self.get_items_from_table(
                "Iota", ["IotaId", "=", ig["IotaId"]])
        items["Iota"] = iota

        obj = RECONSTRUCTOR_MAP[ds_info.introspector](items)

        return Dataset(dataset=obj, ds_info=ds_info)


    def get_items_from_table(self,
        table: str,
        conditions: List[Union[List[GENERIC_TYPES], GENERIC_TYPES]] = []) \
        -> List[Dict[str, GENERIC_TYPES]]:

        # enforce types
        checks.check_types(table, str)
        checks.check_types(conditions, list)

        # construct orator table
        table = self.db.table(table)

        # expand multiple conditions
        if all(isinstance(cond, list) for cond in conditions):
            for cond in conditions:
                table = table.where(*cond)
        # expand single condition
        else:
            table = table.where(*conditions)

        # get table
        table = table.get()

        # format
        return [dict(item) for item in table]


    def _insert_to_table(self,
        table: str,
        items: Dict[str, GENERIC_TYPES]) -> Dict[str, GENERIC_TYPES]:

        # enforce types
        checks.check_types(table, str)
        checks.check_types(items, dict)

        # create conditions
        conditions = [[k, "=", v] for k, v in items.items() if k != "Created"]

        # check exists
        found_items = self.get_items_from_table(table, conditions)

        # not found
        if len(found_items) == 0:
            id = self.db.table(table)\
                .insert_get_id(items, sequence=(table + "Id"))
            id_condition = [table + "Id", "=", id]
            return self.get_items_from_table(table, id_condition)[0]

        # found
        if len(found_items) == 1:
            return found_items[0]

        # database structure error
        raise ValueError(TOO_MANY_RETURN_VALUES.format(n=1))


    @property
    def recent(self):
        print(("-" * 31) + " DATASET DATABASE " + ("-" * 31))

        for name in self.constructor.tables:
            print("-" * 80)
            print("Recent " + name + ":")
            try:
                table = self.db.table(name)
                if name == "Run":
                    recent = table.order_by("End", "desc")\
                                  .limit(self.recent_size)\
                                  .get()
                else:
                    recent = table.order_by("Created", "desc")\
                                  .limit(self.recent_size)\
                                  .get()

                for item in recent:
                    print(dict(item))

            except (orator.exceptions.query.QueryException, KeyError) as e:
                print("!package or schema not up to date!")


    def __str__(self):
        # basic print
        disp = "Recent Datasets:"
        disp += ("\n" + ("-" * 80))

        # collect datasets
        recent = self.db.table("Dataset")\
                     .order_by("Created", "desc")\
                     .limit(self.recent_size)\
                     .get()

        # format print
        for item in recent:
            disp += ("\n" + str(dict(item)))

        return disp


    def __repr__(self):
        return str(self)


class DatasetInfo(object):
    def __init__(self,
        DatasetId: int,
        Name: Union[str, None],
        Introspector: str,
        MD5: str,
        SHA256: str,
        Created: Union[datetime, str],
        OriginDb: DatasetDatabase,
        Description: Union[str, None] = None):

        # enforce types
        checks.check_types(DatasetId, int)
        checks.check_types(Name, [str, type(None)])
        checks.check_types(Description, [str, type(None)])
        checks.check_types(Introspector, str)
        checks.check_types(MD5, str)
        checks.check_types(SHA256, str)
        checks.check_types(Created, [datetime, str])
        checks.check_types(OriginDb, DatasetDatabase)

        # convert types
        if isinstance(Created, str):
            Created = datetime.strptime(Created, DATETIME_PARSE)

        # set attributes
        self._id = DatasetId
        self._name = Name
        self._description = Description
        self._introspector = Introspector
        self._md5 = MD5
        self._sha256 = SHA256
        self._created = Created
        self._origin = OriginDb

        # validate attributes
        self._validate_info()


    @property
    def id(self):
        return self._id


    @property
    def name(self):
        return self._name


    @property
    def description(self):
        return self._description


    @property
    def introspector(self):
        return self._introspector


    @property
    def md5(self):
        return self._md5


    @property
    def sha256(self):
        return self._sha256


    @property
    def created(self):
        return self._created


    @property
    def origin(self):
        return self._origin


    def _validate_info(self):
        found = self.origin.get_items_from_table("Dataset",
            ["MD5", "=", self.md5])

        assert len(found) == 1, INVALID_DS_INFO


    def __str__(self):
        return str({"id": self.id,
                    "name": self.name,
                    "description": self.description,
                    "introspector": self.introspector,
                    "md5": self.md5,
                    "sha256": self.sha256,
                    "created": self.created})


    def __repr__(self):
        return str(self)


class Dataset(object):
    def __init__(self,
        dataset: Union[object, None] = None,
        ds_info: Union[DatasetInfo, None] = None,
        name: Union[str, None] = None,
        description: Union[str, None] = None,
        introspector: Union[Introspector, str, None] = None):

        # enforce types
        checks.check_types(dataset, [object, type(None)])
        checks.check_types(ds_info, [DatasetInfo, type(None)])
        checks.check_types(name, [str, type(None)])
        checks.check_types(description, [str, type(None)])
        checks.check_types(introspector, [Introspector, str, type(None)])

        # must provide dataset or ds_info
        assert dataset is not None or ds_info is not None, MISSING_INIT

        # read dataset
        if isinstance(dataset, (str, pathlib.Path)):
            return read_dataset(dataset)

        # info
        self._info = ds_info

        # introspector
        if self.info is None:
            if introspector is None:
                t_ds = type(dataset)
                if t_ds in INTROSPECTOR_MAP:
                    self._introspector = INTROSPECTOR_MAP[t_ds](dataset)
                else:
                    self._introspector = ObjectIntrospector(dataset)
            else:
                self._introspector = introspector
        else:
            self._introspector = self.info.introspector

        # read introspector
        if isinstance(self.introspector, str):
            self._introspector = INTROSPECTOR_MAP[self.introspector](dataset)

        # update hashes
        self._md5 = tools.get_object_hash(self.ds)
        self._sha256 = tools.get_object_hash(self.ds, hashlib.sha256)

        # unpack based on info
        # name
        if name is None:
            name = str(uuid.uuid4())
        if self.info is None:
            self.name = name
        else:
            self.name = self.info.name

        # description
        if self.info is None:
            self.description = description
        else:
            self.description = self.info.description

        # annotations
        if self.info is None:
            self._annotations = []
        else:
            annotation_dataset = self.info.origin.get_items_from_table(
                "AnnotationDataset", ["DatasetId", "=", self.info.id])
            annotations = []
            for ad in annotation_dataset:
                annotations += self.info.origin.get_items_from_table(
                    "Annotation", ["AnnotationId", "=", ad["AnnotationId"]])
            self._annotations = annotations

        # created
        if self.info is None:
            self.created = datetime.now()
        else:
            self.created = self.info.created


    @property
    def info(self):
        return self._info


    @property
    def ds(self):
        # get dataset if not in memory
        if self.introspector.obj is None:
            ds = self.info.origin.get_dataset(self.info.id)
            self._introspector._obj = ds

        return self.introspector.obj


    @property
    def validated(self):
        if self.info is None:
            return self.introspector.validated

        return True


    @property
    def introspector(self):
        return self._introspector


    @property
    def md5(self):
        return self._md5


    @property
    def sha256(self):
        return self._sha256


    @property
    def annotations(self):
        return self._annotations


    @property
    def state(self):
        ds_ready = self.ds is not None
        state = {"info": self.info,
                 "ds": ds_ready,
                 "name": self.name,
                 "description": self.description,
                 "introspector": type(self.introspector),
                 "validated": self.validated,
                 "md5": self.md5,
                 "sha256": self.sha256,
                 "annotations": self.annotations}

        return state


    def validate(self, **kwargs):
        # validate obj
        self.introspector.validate(**kwargs)


    def store_files(self,
        db: Union[orator.DatabaseManager, None] = None,
        fms: Union[FMSInterface, None] = None, **kwargs):
        # enforce types
        checks.check_types(db, [orator.DatabaseManager, type(None)])
        checks.check_types(fms, [FMSInterface, type(None)])

        # route db
        if db is None:
            if self.info is None:
                raise ValueError(MISSING_PARAMETER.format(p="ds"))
            else:
                db = self.info.origin.constructor.db

        # route fms
        if fms is None:
            if self.info is None:
                raise ValueError(MISSING_PARAMETER.format(p="fms"))
            else:
                fms = self.info.origin.constructor.fms

        # update dataset
        if self.info is not None:
            self.apply(self.introspector.store_files,
            algorithm_name = "dsdb.Dataset.store_files",
            output_dataset_name = self.name + " with fms stored files",
            output_dataset_description = self.description,
            algorithm_parameters = {"db": db, "fms": fms, **kwargs})


    def upload_to(self, database: DatasetDatabase) -> DatasetInfo:
        # enforce types
        checks.check_types(database, DatasetDatabase)

        # run upload
        ds = database.upload_dataset(self)

        # reassign self
        self._reassign_self(ds)


    def apply(self,
        algorithm: Union[types.MethodType, types.FunctionType],
        database: Union[DatasetDatabase, None] = None,
        algorithm_name: Union[str, None] = None,
        algorithm_description: Union[str, None] = None,
        algorithm_version: Union[str, None] = None,
        run_name: Union[str, None] = None,
        run_description: Union[str, None] = None,
        algorithm_parameters: dict = {},
        output_dataset_name: Union[str, None] = None,
        output_dataset_description: Union[str, None] = None) -> "Dataset":

        # enforce types
        checks.check_types(algorithm, [types.MethodType, types.FunctionType])
        checks.check_types(database, [DatasetDatabase, type(None)])
        checks.check_types(algorithm_name, [str, type(None)])
        checks.check_types(algorithm_description, [str, type(None)])
        checks.check_types(algorithm_version, [str, type(None)])
        checks.check_types(run_name, [str, type(None)])
        checks.check_types(run_description, [str, type(None)])
        checks.check_types(algorithm_parameters, dict)
        checks.check_types(output_dataset_name, [str, type(None)])
        checks.check_types(output_dataset_description, [str, type(None)])

        # database already in info
        if database is None:
            if self.info is None:
                raise KeyError(MISSING_PARAMETER.format(p="database"))
            else:
                database = self.info.origin

        # ensure dataset is in database
        found_ds = database.get_items_from_table(
            "Dataset", ["MD5", "=", self.md5])

        # not found
        if len(found_ds) == 0:
            ds = database.upload_dataset(self)
            self._reassign_self(ds)

        # database structure error
        elif len(found_ds) >= 2:
            raise ValueError(TOO_MANY_RETURN_VALUES.format(n=1))

        # apply to self
        ds = database.process(
            algorithm=algorithm,
            input_dataset=self,
            algorithm_name=algorithm_name,
            algorithm_description=algorithm_description,
            algorithm_version=algorithm_version,
            run_name=run_name,
            run_description=run_description,
            algorithm_parameters=algorithm_parameters,
            output_dataset_name=output_dataset_name,
            output_dataset_description=output_dataset_description)

        # reassign self
        self._reassign_self(ds)


    def _reassign_self(self, ds: "Dataset"):
        # enforce types
        checks.check_types(ds, Dataset)

        # reassign self
        self._info = ds._info
        self._introspector = ds._introspector
        self.name = ds.name
        self.description = ds.description
        self._annotations = ds._annotations
        self._md5 = ds._md5
        self._sha256 = ds._sha256


    @property
    def graph(self):
        if self.info is not None:
            self.info.origin.display_dataset_graph(self.info.id)
        else:
            return NO_DS_INFO


    @property
    def connections(self):
        if self.info is not None:
            return self.info.origin.get_dataset_connections(self.info.id)
        else:
            return NO_DS_INFO


    def add_annotation(self, annotation: str):
        # enforce types
        checks.check_types(annotation, str)

        self._annotations += {"Value": annotation, "Created": datetime.now()}


    def _update_annotations(self, database: DatasetDatabase):
        # enforce types
        checks.check_types(database, DatasetDatabase)

        for annotation in self.annotations:
            if "AnnotationId" not in annotation:
                return


    def save(self, path: Union[str, pathlib.Path]) -> pathlib.Path:
        # enforce types
        checks.check_types(path, [str, pathlib.Path])

        # convert types
        path = pathlib.Path(path)

        # dump dataset
        path = path.with_suffix(".dataset")
        to_save = Dataset(self.ds,
                          self.info,
                          self.name,
                          self.description,
                          self.introspector)
        tools.write_pickle(to_save, path)

        return path


    def __str__(self):
        return str(self.state)


    def __repr__(self):
        state_str = ""
        for key, value in self.state.items():
            state_str += key
            state_str += ": "
            state_str += str(value)
            state_str += "\n"

        return state_str


def _return_dataset_obj(dataset):
    return dataset.ds


def read_dataset(path: Union[str, pathlib.Path]):
    # enforce types
    checks.check_types(path, [str, pathlib.Path])

    # convert types
    path = pathlib.Path(path)

    # attempt read
    try:
        if path.suffix in EXTENSION_MAP:
            ds = EXTENSION_MAP[path.suffix](path)
        else:
            ds = tools.read_pickle(path)
    except pickle.UnpicklingError:
        UNKNOWN_EXTENSION.format(p=path)

    # return
    return Dataset(ds)


# delayed globals
LOCAL = {"driver": "sqlite",
         "database": str(pathlib.Path("./local.db").resolve())}
LOCAL = DatabaseConfig(LOCAL)
