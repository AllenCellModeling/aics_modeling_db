#!/usr/bin/env python

# self
from ..schemaversion import SchemaVersion
from ...schema import tables

from ...version import VERSION

# globals
# CREATION ORDER OF TABLES MATTERS
TABLES = {"User": tables.create_User,
          "Iota": tables.create_Iota,
          "Group": tables.create_Group,
          "IotaGroup": tables.create_IotaGroup,
          "Dataset": tables.create_Dataset,
          "GroupDataset": tables.create_GroupDataset,
          "Annotation": tables.create_Annotation,
          "AnnotationDataset": tables.create_AnnotationDataset,
          "Algorithm": tables.create_Algorithm,
          "Run": tables.create_Run,
          "RunInput": tables.create_RunInput,
          "RunOutput": tables.create_RunOutput}

MINIMAL = SchemaVersion("MINIMAL", TABLES, VERSION)
