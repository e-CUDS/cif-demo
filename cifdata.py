"""
Simple example script that reads CIF data into an abstract syntax tree
using PyCifRW and populates an cifdata instance with this data.

If the _atom_site_type_symbol is not defined in the CIF data, it is
derived from _atom_site_label.

Todo
----
Convert this to a proper SOFT storage plugin.
"""
import os
import re

import yaml
from CifFile import ReadCif

import softpy

import softcuds


# Directory holding this file
thisdir = os.path.dirname(__file__)

# Load SOFT metadata database
softpy.register_metadb(softpy.JSONDirMetaDB(
    os.path.join(thisdir, 'metadata')))

# Load CUDS metadata database (created by softcuds.py)
softpy.register_metadb(softpy.JSONDirMetaDB(
    os.path.join(thisdir, 'metadata', 'cuds_entities')))



# Read cif data
cf = ReadCif('VO2_rutile.cif')
rut = cf['VO2_rut_ini']


# Create a Python class representation of cifdata-0.1
CifData = softpy.entity('cifdata', '0.1', 'http://emmc.info/meta')

# Create uninitialised CifData instance
cifdata = CifData()

# Initialise the instance from the cif file
cifkeys = [k.lower() for k in rut.keys()]  # newer versions of PyCifRW
                                           # changed all keys to lower-case
for name in cifdata.soft_get_property_names():
    tag = '_' + name.lower()
    if tag in cifkeys:
        value = rut[tag]
    elif name == 'atom_site_type_symbol':
        value = [re.match('[A-Z][a-z]{0,2}', l).group()
                 for l in rut['_atom_site_label']]
    else:
        raise KeyError('cannot derive "%s" from cif data' % name)
    cifdata.soft_set_property(name, value)


# Define converter from CifData to CUDS
def cif2cuds_converter(cifdata):
    """Returns a list of instances of CUDS element entities representing
    the data in `cifdata`."""
    uuid = softpy.uuid_from_entity('CUDS', '1.0', 'http://emmc.info/meta')




#----------------
# Some testing...
#----------------

# Print content of cifdata
print()
for name in cifdata.soft_get_property_names():
    print('%38s = %-r' % (name, getattr(cifdata, name)))
print('-' * 60)


uuid = softpy.uuid_from_entity('CUDS', '1.0', 'http://emmc.info/meta')
c = softpy.Collection(uuid=uuid, driver='hdf5', uri='softcuds.h5')
