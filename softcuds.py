"""A script that converts CUDS metadata to a set of entities and relations.
"""
from __future__ import print_function

import os
import sys
import json
import ast
from io import StringIO, BytesIO

import yaml


# Directory holding this file
thisdir = os.path.dirname(__file__)


class CUDSError(Exception):
    pass



def generate_cuds_entities(cuds, cuba, namespace='https://emmc.info/metadata',
                           include_parent=True):
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
    include_parent : bool
        Whether to include the attributes of the parents in the generated
        entities.

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

    # Maps CUBA type names to corresponding SOFT type name
    type_mapping = {
        'string': 'string',
        'integer': 'int64' if sys.version_info.major >= 3 else 'int32',
        'double': 'double',
        }

    relations = []
    entities = []

    for key in cuds['CUDS_KEYS'].keys():
        d = get_element_dict(cuds, key, include_parent)
        dim_descr = {}  # maps dimension names to descriptions
        properties = []
        description = d.pop('definition')
        parent = d.pop('parent', None)
        data = d.pop('data', None)
        models = d.pop('models', [])
        physics_equations = d.pop('physics_equations', [])
        variables = d.pop('variables', [])

        if parent:
            relations.append((stripname(parent), 'parent-of', key))

        if data is not None:
            properties.append(dict(
                name='data',
                type='string',
                description='Generic data storage.',
            ))

        for model in models:
            relations.append((key, 'submodel-of', stripname(model)))

        for eq in physics_equations:
            relations.append((key, 'physics_equation-of', stripname(eq)))

        for variable in variables:
            name = stripname(variable)
            ba = cubadict[name]
            dims, dd = get_cuba_dims(cuba, name)
            dim_descr.update(dd)
            properties.append(dict(
                name=name,
                type=type_mapping[ba['type']],
                #unit=  # XXX - where is the unit defined???
                dims=dims,
                description=ba['definition'],
            ))

        # Parse remaining items in d
        for k, v in d.items():
            assert k.startswith('CUBA.') or k == 'data', k
            name = stripname(k)
            if v is None:
                v = {}
            shape = v.get('shape', [])
            default = v.get('default', None)
            if name in cubadict:
                if shape == '(:)':
                    dimname = 'n-%s' % name.lower().replace('_', '-')
                    cuds_dims = [dimname]
                    plural_s = '' if name.lower().endswith('s') else 's'
                    dim_descr[dimname] = 'Number of %s%s.' % (
                        name.lower().replace('_', ' '), plural_s)
                else:
                    cuds_dims, dd = get_dims(name, shape)
                    dim_descr.update(dd)

                ba = cubadict[name]
                dims, dd = get_cuba_dims(cuba, name)
                dim_descr.update(dd)
                properties.append(dict(
                    name=name,
                    type=type_mapping[ba['type']],
                    #unit=  # XXX - where is the unit defined???
                    dims=cuds_dims + dims,
                    description=ba['definition'],
                ))
            elif name in cudsdict:
                relations.append((key, 'has-attribute', name))
                for attr, val in v.items():
                    #print('*** %s.%s: %s = %r' % (key, name, attr, val))
                    if not val:
                        val = ''
                    relations.append(
                        ('%s.%s' % (key, name), 'has-' + attr, str(val)))
            else:
                raise CUDSError('Unrecognised CUDS attribute in %r: %r' % (
                    key, name))

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


def get_element_dict(cuds, key, include_parent):
    """Returns a dict with the content of the CUDS element `key`.  If
    `include_parent` is true, the attributes of parent elements will
    also be included."""
    cudsdict = cuds['CUDS_KEYS']
    element_dict = cudsdict[key].copy()
    if include_parent:
        parent = element_dict.pop('parent')
        while parent:
            parentdict = cudsdict[stripname(parent)]
            for k, v in parentdict.items():
                element_dict.setdefault(k, v)
            parent = element_dict.pop('parent')
    return element_dict


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


def write_cuds_entities(path, include_parent=True):
    """Write all CUDS entities to directory

         `path`/`version`/

    where `path` is the argument and  `version` is the CUDS version.
    The entities are written in JSON format.

    In addition all relations are written to a file named

        `path`/relations-`version`.json

    If `include_parent` is true, the generated CUDS element entities
    will also include attributes of their parent.
    """
    # Read CUBA and CUDS definitions
    with open(os.path.join(thisdir, 'metadata', 'cuba.yml')) as f:
        cuba = yaml.load(f.read())
    with open(os.path.join(thisdir, 'metadata', 'simphony_metadata.yml')) as f:
        cuds = yaml.load(f.read())

    # Crate CUDS entities and relations
    entities, relations = generate_cuds_entities(
        cuds, cuba, include_parent=include_parent)

    # Create directories
    version = cuds['VERSION']
    dirname = os.path.join(path, version)
    if not os.path.exists(dirname):
        os.makedirs(dirname)

    # Write CUDS element entities
    for entity in entities:
        fname = entity['name'] + '.json'
        with open(os.path.join(path, version, fname), 'w') as f:
            json.dump(entity, f, indent=4)

    # Write relations
    fname = 'relations-%s.json' % version
    with open(os.path.join(path, fname), 'w') as f:
        json.dump(relations, f, indent=4)


def get_cuds_collection(include_parent=True):
    """Returns Collection holding the CUDS metadata.

    If `include_parent` is true, the generated CUDS element entities
    will also include attributes of their parent.

    Note, this requires softpy.
    """
    import softpy
    with open(os.path.join(thisdir, 'metadata', 'cuba.yml')) as f:
        cuba = yaml.load(f.read())
    with open(os.path.join(thisdir, 'metadata', 'simphony_metadata.yml')) as f:
        cuds = yaml.load(f.read())
    entities, relations = generate_cuds_entities(cuds, cuba,
                                                 include_parent=include_parent)

    uuid = softpy.uuid_from_entity('CUDS', '1.0', 'http://emmc.info/meta')
    c = softpy.Collection(uuid=uuid)
    c.name = 'CUDS'
    c.version = cuds['VERSION']
    for jsondict in entities:
        entity = softpy.entity(jsondict)
        c.add(entity.name, entity)
    for relation in relations:
        c.add_relation(*relation)

    # Save all metadata in a database
    s = StringIO() if sys.version_info.major >= 3 else BytesIO()
    json.dump(entities, s)
    s.seek(0)
    softpy.register_metadb(softpy.JSONMetaDB(s))
    s.close()

    return c


def get_cuds_instance_collection(cuds_collection, name, dimensions={},
                                 initial_values={}, childs={}):
    """Returns a collection with an instances of the CUDS element `name`
    and all its (nested) attributes.

    Parameters
    ----------
    cuds_collection : Collection
        A CUDS metadata collection as returned by
        get_cuds_collection(include_parent=True).
    name : string
        The name of the CUDS instance to instantiate.
    dimensions : dict
        A dict with the actual size of array attributes. E.g.  for the
        CUDS element CELL the size of its array of POINT attributes
        can be specified with ``dimensions={'CELL.POINT': [10]}``.
    initial_values : dict
        Initial values of the instances.
        Eg: ``initial_values={'CELL.POINT[0]': [0.5, 0.5, 0.0], ...}``.
        Alternatively this could be expressed as
        ``initial_values={'CELL.POINT': [[0.5, 0.5, 0.0], ...]}``.
        NOTE: Not yet implemented.
    childs : dict
        A dict specifying the name of a specific child element you want
        to instansiate instead of a default CUDS element.  Example:
        {'CRYSTAL_STRUCTURE.ATOM_SITES.ATOM_SITE[0].ATOM_COORDINATES':
         'ATOM_SCALED_COORDINATES'}

    Notes
    -----
    The label of the instance of CUDS element `name` is `name`, while
    dot notation is used for attributes and brackets for array indices
    (first index is zero).  E.g. point 4th POINT attribute of CELL
    will be labeled "CELL.POINT[3]".

    The following special relations will be added to the returned collection:
      :has-attribute:  E.g. ('CELL', 'has-attribute', 'CELL.POINT[3]')
      :is-index:       E.g. ('CELL.POINT[3]', 'is-index', '3')

    The UUID of the returned collection is derived from the name, version
    and namespace of the corresponding entity.

    Requires softpy.
    """
    import softpy

    e = cuds_collection.get_instance(name)
    c = softpy.Collection(uuid=e.soft_metadata.get_uuid())  # returned

    def get_shape(base, name, attr):
        """Returns the shape of attribute `attr` of element `name` (under
        `base`)"""
        shapes = cuds_collection.find_relations(name + '.' + attr, 'has-shape')
        if not shapes:
            return ()
        assert len(shapes) == 1
        shape = shapes.pop()
        if ':' in shape:
            ind = base + name + '.' + attr
            if not ind in dimensions:
                raise KeyError('Dimension of "%s" must be provided in '
                               '`dimensions`' % ind)
            return dimensions[ind]
        else:
            return ase.literal_eval(shape)

    def get_attr_element_name(base, name, attr, shape=()):
        """Returns CUDS element name of attribute `attr`.

        If a child of `attr` is specified by the `child` argument or
        via a default value in the definition of CUDS, return the CUDS
        element name of the child.  Otherwise `attr` is returned."""
        label = base + name + '.' + attr
        while True:
            if label in childs:
                return childs[label]
            if not '.' in label:
                break
            label = label[label.index('.') + 1: ]

        defaults = cuds_collection.find_relations(
            name + '.' + attr, 'has-default')
        if defaults:
            assert len(defaults) == 1
            default = defaults.pop()
            if shape:
                return [k[5:] if k.startswith('CUBA.') else attr
                        for kn in ast.literate_eval(default)]
            elif default.startswith('CUBA.'):
                return default[5:]

        return attr

    #def get_value(base, name, attr, shape=(), index=None):
    #    """Returns initial value of `attr` or None."""
    #    label = base + name '.' + attr
    #    ilabel = '%s[%s]' % (label, index) if index else label
    #    while True:
    #        if label in initial_values:
    #            return initial_values[label]
    #        elif ilabel in initial_values:
    #            return initial_values[ilabel]
    #        if not '.' in label:
    #            break
    #        label = label[label.index('.') + 1: ]
    #
    #    defaults = cuds_collection.find_relations(
    #        name + '.' + attr, 'has-default')
    #    if defaults:
    #        assert len(defaults) == 1
    #        default = defaults.pop()
    #        if shape:
    #            return [k[5:] if k.startswith('CUBA.') else attr
    #                    for kn in ast.literate_eval(default)]
    #        elif default.startswith('CUBA.'):
    #            return default[5:]
    #
    #    return None

    def add_cuds_element(base, name, index=None, defaults={}):
        """Create an instance of CUDS element `name` with label base.name or
        base.name[index] depending on whether `index` ig given."""
        label = base + name + repr(list(index)) if index else base + name
        entity = cuds_collection.get_instance(name)
        instance = entity()
        #for k, v in defaults.items():
        #    instance.soft_set_property(k, v)

        # Assign default values to some basic properties
        defaults = dict(data='',
                        UID=instance.soft_get_id(),
                        NAME=label,
                        DESCRIPTION=instance.soft_get_meta_description())
        for k, v in defaults.items():
            if hasattr(instance, k):
                setattr(instance, k, v)

        c.add(label, instance)
        for attr in cuds_collection.find_relations(name, 'has-attribute'):
            shape = get_shape(base, name, attr)
            assert len(shape) < 2, 'only scalar and 1D shapes are supported'
            aname = get_attr_element_name(base, name, attr, shape)
            #value = get_value(base, name, attr)
            if len(shape) == 0:
                add_cuds_element(label + '.', aname)
                c.add_relation(label, 'has-attribute', label + '.' + aname)
            elif len(shape) == 1:
                for i in range(shape[0]):
                    add_cuds_element(label + '.', aname, index=[i])
                    c.add_relation(
                        label, 'has-attribute', '%s.%s[%d]' % (label, aname, i))
            else:
                raise NotImplementedError(
                    'only 0D and 1D attribute shapes are supported')

    add_cuds_element('', name)
    return c


def serialize_cuds_instance_collection(ci):
    """Returns serialized string representation of CUDS instance
    collection `ci`."""
    baselist = []
    root_elements = [l for l in ci.get_labels() if '.' not in l]

    def dictrepr(label):
        """Returns a nested dict representation of given instance."""
        inst = ci.get_instance(label)
        d = {k: str(inst.soft_get_property(k))
             for k in inst.soft_get_property_names()}
        for attr_label in ci.find_relations(label, 'has-attribute'):
            attr = attr_label[attr_label.rindex('.') + 1: ]
            d[attr] = dictrepr(attr_label)
        return d

    for root in root_elements:
        baselist.append(dictrepr(root))
    #return yaml.dump(baselist)
    return json.dumps(baselist, indent=2)





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
    write_cuds_entities(os.path.join(thisdir, 'metadata', 'cuds_entities'))

    import softpy

    # Create a collection with all CUDS entities and relations
    c = get_cuds_collection()
    with softpy.Storage(driver='hdf5',
                        uri='softcuds.h5',
                        #options='append=yes',
    ) as s:
        c.save(s)


    # Create a collection of CUDS instances
    ci = get_cuds_instance_collection(
        cuds_collection=c,
        name='CRYSTAL_STRUCTURE',
        dimensions={'CRYSTAL_STRUCTURE.ATOM_SITES.ATOM_SITE': [2]},
        initial_values={})

    print('labels:\n', ci.get_labels())
    crystal_structure = ci.get_instance('CRYSTAL_STRUCTURE')

    #with softpy.Storage(driver='hdf5',
    #                    uri='instances.h5',
    #                    #options='append=yes',
    #) as s:
    #    ci.save(s)
