"""A script that converts CUDS metadata to a set of entities and relations.

Points to discuss
-----------------
  - In the entities for the CUDS elements, how should we specify an arrays
    of another entity?

  - What is the data attribute in CUDS_ITEM?

  - Where are the unit defined?

  - We do some assumptions regarding dimension names, see notes in the
    docstring for get_dims().

  - Default values should be stored as special instances of the
    entities.  Is it a good idea to avoid dependencies on SimPhoNy and
    SOFT in this script?  If so, should we dump these default instances
    in a json file (using the structure of instances stored in hdf5)?
    How to deal with properties with no default value specified in CUDS?
    Should we define a some fill values in a special entity?
"""
import os
import json

import yaml



def generate_cuds_entities(cuds, cuba, namespace='https://emmc.info/metadata'):
    """Convert `cuds` and `cuba` to entities and relations.

    Parameters
    ----------
    cuds : dict
        SimPhoNy Common Universal Data Structures (CUDS) represented as
        a Python dict.
    cuba : dict
        SimPhoNy Common Universal Base Attributes (CUBA) represented as
        a Python dict.
    namespace : string
        Namespace for the generated entities.

    Returns
    -------
    entities : list
        A list of entities represented as dicts.
    relations : list
        A list of relations represented as dicts.

    Notes
    -----
    SimPhoNy does not name the dimensions, so we will assume that all
    dimentions of length 3 corresponds to "n-coords".
    """
    cubadict = cuba['CUBA_KEYS']
    cudsdict = cuds['CUDS_KEYS']

    relations = []
    entities = []

    for key, d in cuds['CUDS_KEYS'].items():
        dim_descr = {}  # maps dimension names to descriptions
        properties = []
        description = d.pop('definition')
        parent = d.pop('parent')
        data = d.pop('data', None)
        models = d.pop('models', [])
        physics_equations = d.pop('physics_equations', [])
        variables = d.pop('variables', [])

        if parent:
            relations.append(dict(
                subject=stripname(parent), predicate='parent-of', object=key))

        if data is not None:
            properties.append(dict(
                name='data',
                type='string',
                description='Generic data storage.',
            ))

        for model in models:
            relations.append(dict(
                subject=key, predicate='submodel-of', object=stripname(model)))

        for eq in physics_equations:
            relations.append(dict(
                subject=key,
                predicate='physics_equation-of',
                object=stripname(eq)))

        for variable in variables:
            name = stripname(variable)
            ba = cubadict[name]
            dims, dd = get_cuba_dims(cuba, name)
            dim_descr.update(dd)
            properties.append(dict(
                name=name,
                type=ba['type'],
                #unit=  # XXX - where is the unit defined???
                dims=dims,
                description=ba['definition'],
            ))

        # Parse remaining items in d
        #
        # XXX - how to parse shape
        # XXX - default should we create a default instance
        for k, v in d.items():
            assert k.startswith('CUBA.') or k == 'data', k
            name = stripname(k)
            if v is None:
                v = {}
            shape = v.get('shape', [])
            default = v.get('default', None)
            if shape == '(:)':
                cuds_dims = ['n-%s' % k.lower().replace('_', '-')]
            else:
                cuds_dims, dd = get_dims(name, shape)
                dim_descr.update(dd)
            if name in cubadict:
                ba = cubadict[name]
                dims, dd = get_cuba_dims(cuba, name)
                dim_descr.update(dd)
                properties.append(dict(
                    name=name,
                    type=ba['type'],
                    #unit=  # XXX - where is the unit defined???
                    dims=cuds_dims + dims,
                    description=ba['definition'],
                ))
            elif name in cudsdict:
                relations.append(dict(
                    subject=key,
                    predicate='has-attribute',
                    object=name))
                for attr, val in v.items():
                    relations.append(dict(
                        subject='%s.%s' % (key, name),
                        predicate='has-' + attr,
                        object=val))
            else:
                raise('Unrecognised CUDS attribute in %r: %r' % (key, name))

        entities.append(dict(
            name=key,
            version=cuds['VERSION'],
            namespace=namespace,
            description=description,
            dimensions=[dict(name=name, description=descr)
                        for name, descr in dim_descr.items()],
            properties=properties,
            ))

    return entities, relations


def stripname(name):
    """Returns name with initial "CUBA." stripped of."""
    return name[5:] if name.startswith('CUBA.') else name


def get_cuba_dims(cuba, key):
    """Returns a list of dimensions of CUBA key `key` and a dict
    describing the dimensions."""
    d = cuba['CUBA_KEYS'][key]
    if 'shape' in d:
        return get_dims(key, d['shape'], from_cuba=True)
    else:
        return [], {}


def get_dims(key, shape, from_cuba=False):
    """Returns a list of dimensions and a dict describing the dimensions
    for `key` and `shape`.

    Notes
    -----
    - CUBA strings are converted to strings of arbitrary length.

    - For CUBA elements, if the last dimension is 3, we assume that it
      is the number of coordinates.

    - For CUBA elements, if the second last dimension is 3, we assume
      that it is the number of lattice vectors.

    - For CUDS elements, if the last dimension is 3, we assume that it
      is the number of lattice vectors.

    - If an element has one dimension of size 9, we assume that it is
      the product of the number of lattice vectors times the number of
      coordinates.
    """
    dim_descr = {}
    dims = []
    ncoords_descr = 'Number of coordinates. Always 3.'
    nlattvecs_descr = 'Number of lattice vectors. Always 3.'
    N = len(shape)
    for i, n in enumerate(shape):
        if n == 3 and i == N - 1:
            if from_cuba:
                name = 'n-coordinates'
                dim_descr[name] = ncoords_descr
            else:
                name = 'n-lattice-vectors'
                dim_descr[name] = nlattvecs_descr
        elif from_cuba and n == 3 and i == N - 2:
            name = 'n-lattice-vectors'
            dim_descr[name] = nlattvecs_descr
        elif n == 9 and N == 1:
            name = 'n-lattice-vectors * n-coordinates'
            dim_descr['n-coordinates'] = ncoords_descr
            dim_descr['n-lattice-vectors'] = nlattvecs_descr
        else:
            plural = 's' if key.lower()[-1] != 's' else ''
            keyname = key.lower().replace('_', '-') + plural
            if N == 1 or (N == 2 and shape[1] == 3):
                name = 'n-%s' % keyname
                descr = 'Number of %s.' % keyname
            else:
                name = 'n-%s_%d' % (keyname, i)
                descr = 'Dimension %d of %s.' % (i, keyname)
            dim_descr[name] = descr
        dims.append(name)
    return dims, dim_descr





if __name__ == '__main__':

    # Directory holding this file
    thisdir = os.path.dirname(__file__)

    # Read CUBA and CUDS definitions
    with open(os.path.join(thisdir, 'metadata', 'cuba.yml')) as f:
        cuba = yaml.load(f.read())
    with open(os.path.join(thisdir, 'metadata', 'simphony_metadata.yml')) as f:
        cuds = yaml.load(f.read())

    # Crate CUDS entities and relations
    entities, relations = generate_cuds_entities(cuds, cuba)

    # Write CUDS entities and relations
    for entity in entities:
        with open(os.path.join(
                thisdir, 'metadata', 'cuds_entities', '%s-%s.json' % (
                    entity['name'], entity['version'])), 'w') as f:
            json.dump(entity, f, indent=4)
    with open(os.path.join(
            thisdir, 'metadata', 'cuds_relations', 'cuds_relations.json'),
              'w') as f:
        json.dump(relations, f, indent=4)
