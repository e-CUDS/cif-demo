import os
import re

from CifFile import ReadCif

import softpy


# Load SOFT metadata databases
softpy.register_metadb(softpy.JSONDirMetaDB(
    os.path.join(os.path.dirname(__file__), 'metadata')))


# Read cif data
cf = ReadCif('VO2_rutile.cif')
rut = cf['VO2_rut_ini']


# Create a Python class representation of cifdata-0.1
CifData = softpy.entity('cifdata', '0.1', 'http://emmc.info/meta')

# Create uninitialised CifData instance
cifdata = CifData()

# Initialise the instance from the cif file
for name in cifdata.soft_get_property_names():
    tag = '_' + name
    if tag in rut.keys():
        value = rut[tag]
    elif name == 'atom_site_type_symbol':
        value = [re.match('[A-Z][a-z]{0,2}', l).group()
                 for l in rut['_atom_site_label']]
    else:
        raise KeyError('cannot derive "%s" from cif data')
    cifdata.soft_set_property(name, value)

# TODO
# - Define a CUDS
# - Try to generate SOFT metadata corresponding to this CUDS by
#   using the basic metadata schema
# - Map cifdata to corresponding CUDS instance (or the other way around)
# - Try to see formalise this mapping

#---------

# Print content of cifdata
for name in cifdata.soft_get_property_names():
    print('%38s = %-r' % (name, getattr(cifdata, name)))

# Store the cifdata to hdf5 file
with softpy.Storage(driver='hdf5', uri='rutile.h5') as s:
    s.save(cifdata)
