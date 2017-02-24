#!/usr/bin/env python
# -*- coding: utf-8 -*-
from __future__ import print_function

import ase.io

import softpy
from atoms import SoftAtoms


# Read CIF file into an ASE atoms object
at = ase.io.read('VO2_rutile.cif')

# Softify the ASE object, by associating it with metadata (atoms.json)
# that gives semantics to its attributes and properties.
# The "rutile" object is now a SOFT data object.
rutile = SoftAtoms(at)


# TODO - map rutile to a CUDS instance. Idea:
#
#   1. Describe a CUDS that can hold an atom structure.
#      In Python this would be to define the Python class for the CUDS
#      that we want to end up with.
#
#   2. Identify the metadata and create a SOFT (collection and) entities
#      for it.
#      In Python: we should be able use this metadata to generate a
#      SoftCUDS class in the same way as SoftAtoms is generated from the
#      Atoms metadata.
#
#   3. Express the metadata using the basic metadata schema (i.e. define
#      a metadata schema for the CUDS).
#      Exercise: Can we based on this metadata schema generate the SOFT
#                entities in step 2?
#
#   4. Define a mapping from the atoms metadata to CUDS metadata
#      In Python this corresponds to map the SoftAtoms to the SoftCUDS
#      class.
#
#   5. Apply the mapping in point 5 to map the "rutile" SoftAtoms instance
#      to an instance of SoftCUDS.
#


# Use the hdf5 storage driver to save the CIF data into a hdf5 file
with softpy.Storage(driver='hdf5', uri='rutile.h5') as s:
    s.save(rutile)
