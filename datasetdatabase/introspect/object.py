#!/usr/bin/env python

# installed
from typing import Dict, List, Union
from datetime import datetime
import pickle
import orator
import types
import uuid

# self
from .introspector import Introspector
from ..utils import checks, tools


class ObjectIntrospector(Introspector):
    """
    General object introspector. Using a single all attribute validation map,
    you can ingest, validate, and deconstruct, an object. There is limited
    functionality due to how generalizable this Introspector needs to be.
    """

    def __init__(self, obj: object):
        self._obj = obj
        self._validated = False


    @property
    def obj(self):
        return self._obj


    @property
    def validated(self):
        return self._validated


    def validate(self,
        item_validation_map: Union[None,
            Dict[str, Union[types.ModuleType, types.FunctionType]]] = None):

        # enforce types
        checks.check_types(item_validation_map, [dict, type(None)])

        # validate
        if item_validation_map is not None:
            for i, f in item_validation_map.items():
                if not self.validate_attribute(i, f):
                    raise ValueError("Attribute failed validation: {a}"
                                    .format(a=i))

            self._validated = True


    def deconstruct(self, db: orator.DatabaseManager, ds_info: dict):
        # all iota are created at the same time
        created = datetime.now()

        # create group
        group = {"Label": str(uuid.uuid4()),
                 "Created": created}

        # insert group
        group = tools.insert_to_db_table(db, "Group", group)

        # create group_dataset
        group_dataset = {"GroupId": group["GroupId"],
                         "DatasetId": ds_info.id,
                         "Created": created}

        # insert group_dataset
        group_dataset = tools.insert_to_db_table(
            db, "GroupDataset", group_dataset)

        # create iota
        iota = {"Key": "obj",
                "Value": pickle.dumps(self.obj),
                "Created": created}

        # insert iota
        iota = tools.insert_to_db_table(db, "Iota", iota)

        # create iota_group
        iota_group = {"IotaId": iota["IotaId"],
                      "GroupId": group["GroupId"],
                      "Created": created}

        # insert iota_group
        iota_group = tools.insert_to_db_table(db, "IotaGroup", iota_group)


    def package(self):
        package = {}
        package["data"] = self.obj
        package["files"] = None
        return package


    def validate_attribute(self,
        item: str,
        func: Union[types.ModuleType, types.FunctionType]) -> bool:

        return func(getattr(self.obj, item))


def reconstruct(items: Dict[str, Dict[str, object]]) -> object:
    obj = pickle.loads(items["Iota"][0]["Value"])
    return obj
