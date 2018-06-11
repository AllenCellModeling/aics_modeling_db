#!/usr/bin/env python

import os
from setuptools import setup, find_packages

exclude_dirs = ["env"]

PACKAGES = find_packages(exclude=exclude_dirs)

# Get version info, stored at legacy_handoff/labkey_upload/version.py
version_file = os.path.join("modelingdbtools", "version.py")
with open(version_file) as f:
    exec(f.read())

opts = dict(name=NAME,
            maintainer=MAINTAINER,
            maintainer_email=MAINTAINER_EMAIL,
            description=DESCRIPTION,
            long_description=LONG_DESCRIPTION,
            license=LICENSE,
            classifiers=CLASSIFIERS,
            author=AUTHOR,
            author_email=AUTHOR_EMAIL,
            platforms=PLATFORMS,
            version=VERSION,
            packages=PACKAGES,
            install_requires=REQUIRES,
            requires=REQUIRES,
            scripts=SCRIPTS)

if __name__ == "__main__":
    setup(**opts)