# -*- coding: utf-8 -*-

"""Settings."""

#------------------------------------------------------------------------------
# Imports
#------------------------------------------------------------------------------

import logging
import os
import os.path as op

from six import string_types
from traitlets.config import Config, PyFileConfigLoader

from ._misc import _load_json, _save_json, _read_python

logger = logging.getLogger(__name__)


#------------------------------------------------------------------------------
# Config
#------------------------------------------------------------------------------

def phy_user_dir():
    """Return the absolute path to the phy user directory."""
    return op.expanduser('~/.phy/')


def _ensure_dir_exists(path):
    if not op.exists(path):
        os.makedirs(path)


def _load_config(path):
    if not op.exists(path):
        return {}
    path = op.realpath(path)
    dirpath, filename = op.split(path)
    config = PyFileConfigLoader(filename, dirpath).load_config()
    return config


def load_master_config(user_dir=None):
    """Load a master Config file from `~/.phy/phy_config.py`."""
    user_dir = user_dir or phy_user_dir()
    c = Config()
    paths = [op.join(user_dir, 'phy_config.py')]
    for path in paths:
        c.update(_load_config(path))
    return c
