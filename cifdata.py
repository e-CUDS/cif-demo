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
    os.path.join(thisdir, 'metadata', 'cuds_entities', '1.0')))



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



def set_attributes(collection, label, **kw):
    """In instance `label` of `collection`, set attributes specified with
    the keyword arguments."""
    instance = collection.get_instance(label)
    for k, v in kw.items():
        instance.soft_set_property(k, v)
    collection.add(label, instance)



# Define converter from CifData to CUDS
def cif2cuds_converter(cifdata):
    """Returns a list of instances of CUDS element entities representing
    the data in `cifdata`."""
    uuid = softpy.uuid_from_entity('CUDS', '1.0', 'http://emmc.info/meta')
    cuds_collection = softcuds.get_cuds_collection()
    nsites = len(cifdata.atom_site_type_symbol)
    ci = softcuds.get_cuds_instance_collection(
        cuds_collection=cuds_collection,
        name='CRYSTAL_STRUCTURE',
        dimensions={
            'CRYSTAL_STRUCTURE.ATOM_SITES.ATOM_SITE': [nsites],
        },
        initial_values={})

    set_attributes(
        ci, 'CRYSTAL_STRUCTURE.SPACEGROUP_NUMBER',
        SPACEGROUP_INTERNATIONAL_TABLES_NUMBER=cifdata.symmetry_Int_Tables_number,
    )
    set_attributes(
        ci, 'CRYSTAL_STRUCTURE.LATTICE_PARAMETERS',
        LATTICE_PARAMETER=[
            cifdata.cell_length_a,
            cifdata.cell_length_b,
            cifdata.cell_length_c,
            cifdata.cell_angle_alpha,
            cifdata.cell_angle_beta,
            cifdata.cell_angle_gamma,
        ])
    occupancy = getattr(cifdata, 'atom_site_occupancy', [1.0] * nsites)
    for i in range(nsites):
        set_attributes(
            ci, 'CRYSTAL_STRUCTURE.ATOM_SITES.ATOM_SITE[%d]' % i,
            OCCUPANCY=occupancy[i],
            CHEMICAL_SPECIE=cifdata.atom_site_type_symbol[i],
        )
        set_attributes(
            ci, 'CRYSTAL_STRUCTURE.ATOM_SITES.ATOM_SITE[%d].ATOM_SCALED_COORDINATES' % i,
            SCALED_POSITION=[
                cifdata.atom_site_fract_x[i],
                cifdata.atom_site_fract_y[i],
                cifdata.atom_site_fract_z[i],
            ])

    return ci




#----------------
# Some testing...
#----------------

# Print content of cifdata
#print()
#for name in cifdata.soft_get_property_names():
#    print('%38s = %-r' % (name, getattr(cifdata, name)))

# Create a collection representing a CUDS crystal structure for the cif data
ci = cif2cuds_converter(cifdata)

# Serialize the CUDS instance
print(softcuds.serialize_cuds_instance_collection(ci))
