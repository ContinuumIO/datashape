import pickle
import sys

import numpy as np
import pytest

import datetime
from datashape.coretypes import (Record, real, String, CType, DataShape, int32,
                                 Fixed, Option, _units, _unit_aliases, Date,
                                 DateTime, TimeDelta, Type, int64, TypeVar,
                                 Ellipsis, null, Time, Map, PrimaryKey)
from datashape import (dshape, to_numpy_dtype, from_numpy, error, Units,
                       uint32, Bytes, var, timedelta_, datetime_, date_,
                       float64, Tuple, to_numpy)
from datashape.py2help import unicode, OrderedDict


@pytest.fixture
def a():
    return Record([('x', int), ('y', int)])


@pytest.fixture
def b():
    return Record([('y', int), ('x', int)])


def test_respects_order(a, b):
    assert a != b


def test_strings():
    assert Record([('x', 'real')]) == Record([('x', real)])


def test_integers():
    assert Record([(0, 'real')]) == Record([('0', real)])


def test_error_on_datashape_with_string_argument():
    with pytest.raises(TypeError):
        DataShape('5 * int32')


class TestToNumpyDtype(object):

    def test_simple(self):
        assert to_numpy_dtype(dshape('2 * int32')) == np.int32
        assert (to_numpy_dtype(dshape('2 * {x: int32, y: int32}')) ==
                np.dtype([('x', '<i4'), ('y', '<i4')]))

    def test_datetime(self):
        assert to_numpy_dtype(dshape('2 * datetime')) == np.dtype('M8[us]')

    def test_date(self):
        assert to_numpy_dtype(dshape('2 * date')) == np.dtype('M8[D]')

    def test_string(self):
        assert to_numpy_dtype(dshape('2 * string')) == np.dtype('O')

    def test_dimensions(self):
        return to_numpy_dtype(dshape('var * int32')) == np.int32

    def test_timedelta(self):
        assert to_numpy_dtype(dshape('2 * timedelta')) == np.dtype('m8[us]')
        assert to_numpy_dtype(dshape("2 * timedelta[unit='s']")) == \
            np.dtype('m8[s]')


def test_timedelta_repr():
    assert eval(repr(dshape('timedelta'))) == dshape('timedelta')
    assert eval(repr(dshape('timedelta[unit="ms"]'))) == \
        dshape('timedelta[unit="ms"]')


def test_timedelta_bad_unit():
    with pytest.raises(ValueError):
        dshape('timedelta[unit="foo"]')


def test_timedelta_nano():
    dshape('timedelta[unit="ns"]').measure.unit == 'ns'


def test_timedelta_aliases():
    for alias in _unit_aliases:
        a = alias + 's'
        assert (dshape('timedelta[unit=%r]' % a) ==
                dshape('timedelta[unit=%r]' % _unit_aliases[alias]))


class TestFromNumPyDtype(object):

    def test_int32(self):
        assert from_numpy((2,), 'int32') == dshape('2 * int32')
        assert from_numpy((2,), 'i4') == dshape('2 * int32')

    def test_struct(self):
        dtype = np.dtype([('x', '<i4'), ('y', '<i4')])
        result = from_numpy((2,), dtype)
        assert result == dshape('2 * {x: int32, y: int32}')

    def test_datetime(self):
        keys = 'h', 'm', 's', 'ms', 'us', 'ns', 'ps', 'fs', 'as'
        for k in keys:
            assert from_numpy((2,),
                              np.dtype('M8[%s]' % k)) == dshape('2 * datetime')

    def test_date(self):
        for d in ('D', 'M', 'Y', 'W'):
            assert from_numpy((2,),
                              np.dtype('M8[%s]' % d)) == dshape('2 * date')

    def test_timedelta(self):
        for d in _units:
            assert from_numpy((2,),
                              np.dtype('m8[%s]' % d)) == \
                dshape('2 * timedelta[unit=%r]' % d)

    def test_ascii_string(self):
        assert (from_numpy((2,), np.dtype('S7')) ==
                dshape('2 * string[7, "ascii"]'))

    def test_string(self):
        assert (from_numpy((2,), np.dtype('U7')) ==
                dshape('2 * string[7, "utf32"]'))

    def test_string_from_CType_classmethod(self):
        assert CType.from_numpy_dtype(np.dtype('S7')) == String(7, 'A')


def test_eq():
    assert dshape('int') == dshape('int')
    assert dshape('int') != 'apple'


def test_serializable():
    ds = dshape('''{id: int64,
                    name: string,
                    amount: float32,
                    arr: 3 * (int32, string)}''')
    ds2 = pickle.loads(pickle.dumps(ds))

    assert str(ds) == str(ds2)


def test_subshape():
    ds = dshape('5 * 3 * float32')
    assert ds.subshape[2:] == dshape('3 * 3 * float32')

    ds = dshape('5 * 3 * float32')
    assert ds.subshape[::2] == dshape('3 * 3 * float32')


def test_negative_slicing():
    ds = dshape('10 * int')
    assert ds.subshape[-3:] == dshape('3 * int')


def test_newaxis_slicing():
    ds = dshape('10 * int')
    assert ds.subshape[None, :] == dshape('1 * 10 * int')
    assert ds.subshape[:, None] == dshape('10 * 1 * int')


def test_datashape_coerces_ints():
    assert DataShape(5, 'int32')[0] == Fixed(5)
    assert DataShape(5, 'int32')[1] == int32


def test_shape():
    assert dshape('5 * 3 * float32').shape == (5, 3)
    assert dshape('float32').shape == ()
    assert dshape('float32').measure.shape == ()
    assert dshape('?float32').measure.shape == ()


def test_option_sanitizes_strings():
    assert Option('float32').ty == dshape('float32').measure


def test_option_passes_itemsize():
    assert (dshape('?float32').measure.itemsize ==
            dshape('float32').measure.itemsize)


class TestComplexFieldNames(object):

    """
    The tests in this class should verify that the datashape parser can handle
    field names that contain strange characters like spaces, quotes, and
    backslashes

    The idea is that any given input datashape should be recoverable once we
    have created the actual dshape object.

    This test suite is by no means complete, but it does handle some of the
    more common special cases (common special? oxymoron?)
    """

    def test_spaces_01(self):
        space_dshape = "{'Unique Key': ?int64}"
        assert space_dshape == str(dshape(space_dshape))

    def test_spaces_02(self):
        big_space_dshape = """{ 'Unique Key' : ?int64, 'Created Date' : string,
'Closed Date' : string, Agency : string, 'Agency Name' : string,
'Complaint Type' : string, Descriptor : string, 'Location Type' : string,
'Incident Zip' : ?int64, 'Incident Address' : ?string, 'Street Name' : ?string,
'Cross Street 1' : ?string, 'Cross Street 2' : ?string,
'Intersection Street 1' : ?string, 'Intersection Street 2' : ?string,
'Address Type' : string, City : string, Landmark : string,
'Facility Type' : string, Status : string, 'Due Date' : string,
'Resolution Action Updated Date' : string, 'Community Board' : string,
Borough : string, 'X Coordinate (State Plane)' : ?int64,
'Y Coordinate (State Plane)' : ?int64, 'Park Facility Name' : string,
'Park Borough' : string, 'School Name' : string, 'School Number' : string,
'School Region' : string, 'School Code' : string,
'School Phone Number' : string, 'School Address' : string,
'School City' : string, 'School State' : string, 'School Zip' : string,
'School Not Found' : string, 'School or Citywide Complaint' : string,
'Vehicle Type' : string, 'Taxi Company Borough' : string,
'Taxi Pick Up Location' : string, 'Bridge Highway Name' : string,
'Bridge Highway Direction' : string, 'Road Ramp' : string,
'Bridge Highway Segment' : string, 'Garage Lot Name' : string,
'Ferry Direction' : string, 'Ferry Terminal Name' : string,
Latitude : ?float64, Longitude : ?float64, Location : string }"""

        ds1 = dshape(big_space_dshape)
        ds2 = dshape(str(ds1))

        assert str(ds1) == str(ds2)

    def test_single_quotes_01(self):

        quotes_dshape = """{ 'field \\' with \\' quotes' : string }"""

        ds1 = dshape(quotes_dshape)
        ds2 = dshape(str(ds1))

        assert str(ds1) == str(ds2)

    def test_double_quotes_01(self):
        quotes_dshape = """{ 'doublequote \" field \"' : int64 }"""
        ds1 = dshape(quotes_dshape)
        ds2 = dshape(str(ds1))

        assert str(ds1) == str(ds2)

    def test_multi_quotes_01(self):
        quotes_dshape = """{ 'field \\' with \\' quotes' : string, 'doublequote \" field \"' : int64 }"""

        ds1 = dshape(quotes_dshape)
        ds2 = dshape(str(ds1))

        assert str(ds1) == str(ds2)

    def test_mixed_quotes_01(self):
        quotes_dshape = """{ 'field \" with \\' quotes' : string, 'doublequote \" field \\'' : int64 }"""

        ds1 = dshape(quotes_dshape)
        ds2 = dshape(str(ds1))

        assert str(ds1) == str(ds2)

    def test_bad_02(self):
        bad_dshape = """{ Unique Key : int64}"""
        with pytest.raises(error.DataShapeSyntaxError):
            dshape(bad_dshape)

    def test_bad_backslashes_01(self):
        """backslashes aren't allowed in datashapes according to the definitions
        in lexer.py as of 2014-10-02. This is probably an oversight that should
        be fixed.
        """
        backslash_dshape = """{ 'field with \\\\   backslashes' : int64 }"""

        with pytest.raises(error.DataShapeSyntaxError):
            dshape(backslash_dshape)


def test_record_string():
    s = '{name_with_underscores: int32}'
    assert s.replace(' ', '') == str(dshape(s)).replace(' ', '')


def test_record_with_unicode_name_as_numpy_dtype():
    r = Record([(unicode('a'), 'int32')])
    assert r.to_numpy_dtype() == np.dtype([('a', 'i4')])


@pytest.mark.xfail(
    sys.version_info < (2, 7),
    reason='OrderedDict not supported before 2.7',
)
def test_record_from_OrderedDict():
    r = Record(OrderedDict([('a', 'int32'), ('b', 'float64')]))
    assert r.to_numpy_dtype() == np.dtype([('a', 'i4'), ('b', 'f8')])


def test_tuple_datashape_to_numpy_dtype():
    ds = dshape('5 * (int32, float32)')
    assert to_numpy_dtype(ds) == [('f0', 'i4'), ('f1', 'f4')]


def test_option_date_to_numpy():
    assert Option(Date()).to_numpy_dtype() == np.dtype('datetime64[D]')


def test_option_datetime_to_numpy():
    assert Option(DateTime()).to_numpy_dtype() == np.dtype('datetime64[us]')


@pytest.mark.parametrize('unit',
                         ['Y', 'M', 'D', 'h', 'm', 's', 'ms', 'us', 'ns'])
def test_option_timedelta_to_numpy(unit):
    assert (Option(TimeDelta(unit=unit)).to_numpy_dtype() ==
            np.dtype('timedelta64[%s]' % unit))


def test_duplicate_field_names_fails():
    fields = [('a', 'int32'), ('b', 'string'), ('a', 'float32')]
    with pytest.raises(ValueError):
        Record(fields)


@pytest.mark.parametrize('ds',
                         ['int64',
                          'var * float64',
                          '10 * var * int16',
                          '{a: int32, b: ?string}',
                          'var * {a: int32, b: ?string}',
                          '10 * {a: ?int32, b: var * {c: string[30]}}',
                          '{"weird name": 3 * var * 2 * ?{a: int8, b: ?uint8}}',
                          'var * {"func-y": (A) -> var * {a: 10 * float64}}'])
def test_repr_of_eval_is_dshape(ds):
    assert eval(repr(dshape(ds))) == dshape(ds)


def test_complex_with_real_component_fails():
    with pytest.raises(TypeError):
        dshape('complex[int64]')


def test_already_registered_type():
    with pytest.raises(TypeError):
        Type.register('int64', int64)


def test_multiplication_of_dshapes():
    with pytest.raises(TypeError):
        int32 * 10


def test_ellipsis_with_typevar_repr():
    assert str(Ellipsis(typevar=TypeVar('T'))) == 'T...'
    assert repr(Ellipsis(typevar=TypeVar('T'))) == 'Ellipsis(\'T...\')'


def test_null_datashape_string():
    assert str(null) == 'null'


@pytest.mark.xfail(raises=TypeError, reason="Not yet implemented")
def test_time_with_tz_not_a_string():
    assert Time(tz=datetime.tzinfo())


@pytest.mark.xfail(raises=TypeError, reason="Not yet implemented")
def test_datetime_with_tz_not_a_string():
    assert DateTime(tz=datetime.tzinfo())


@pytest.mark.parametrize('unit', _units)
def test_timedelta_repr(unit):
    assert repr(TimeDelta(unit=unit)) == 'TimeDelta(unit=%r)' % unit


@pytest.mark.parametrize('unit', _units)
def test_timedelta_str(unit):
    assert str(TimeDelta(unit=unit)) == 'timedelta[unit=%r]' % unit


def test_unit_construction():
    with pytest.raises(TypeError):
        Units(1)
    with pytest.raises(TypeError):
        Units('kg', 1)


def test_unit_str():
    assert str(Units('kg')) == "units['kg']"
    assert (str(Units('counts/time', DataShape(uint32))) ==
            "units['counts/time', uint32]")


def test_bytes_str():
    assert str(Bytes()) == 'bytes'


def test_unsupported_string_encoding():
    with pytest.raises(ValueError):
        String(1, 'asdfasdf')


def test_all_dims_before_last():
    with pytest.raises(TypeError):
        DataShape(uint32, var, uint32)


def test_datashape_parameter_count():
    with pytest.raises(ValueError):
        DataShape()


def test_named_datashape():
    assert str(DataShape(uint32, name='myuint')) == 'myuint'


def test_subarray_invalid_index():
    with pytest.raises(IndexError):
        dshape('1 * 2 * 3 * int32').subarray(42)


def test_record_subshape_integer_index():
    ds = DataShape(Record([('a', 'int32')]))
    assert ds.subshape[0] == int32


def test_slice_subshape_negative_step():
    ds = 30 * Record([('a', 'int32')])
    assert ds.subshape[:-1] == 29 * Record([('a', 'int32')])


def test_slice_subshape_negative_start():
    ds = var * Record([('a', 'int32')])
    assert ds.subshape[-1:] == var * Record([('a', 'int32')])


def test_slice_subshape_bad_types():
    ds = var * Record([('a', 'int32')])
    with pytest.raises(TypeError):
        assert ds.subshape[1.0]


@pytest.mark.parametrize(['base', 'expected'],
                         zip([timedelta_, date_, datetime_],
                             ['timedelta64[us]', 'datetime64[D]',
                              'datetime64[us]']))
def test_option_to_numpy_dtype(base, expected):
    assert Option(base).to_numpy_dtype() == np.dtype(expected)


@pytest.mark.xfail(raises=TypeError,
                   reason=('NumPy has no notion of missing for types other '
                           'than timedelta, datetime, and date'))
@pytest.mark.parametrize('base', [int32, float64, Record([('a', uint32)])])
def test_option_to_numpy_dtype_fails(base):
    Option(base).to_numpy_dtype()


@pytest.mark.xfail(raises=NotImplementedError,
                   reason='DataShape does not know about void types (yet?)')
def test_from_numpy_dtype_fails():
    x = np.zeros(2, np.dtype([('a', 'int32')]))
    CType.from_numpy_dtype(x[0].dtype)


def test_ctype_alignment():
    assert int32.alignment == 4


def test_fixed_dimensions_must_be_positive():
    with pytest.raises(ValueError):
        Fixed(-1)


def test_fixed_comparison():
    assert Fixed(1) != 'a'


def test_typevar_must_be_upper_case():
    with pytest.raises(ValueError):
        TypeVar('t')


def test_typevar_repr():
    assert repr(TypeVar('T')) == "TypeVar('T')"


def test_funcproto_attrs():
    f = dshape('(int32, ?float64) -> {a: ?string}').measure
    assert f.restype == DataShape(Record([('a', Option(String()))]))
    assert f.argtypes == (DataShape(int32), DataShape(Option(float64)))


def test_tuple_str():
    assert str(Tuple([Option(int32), float64])) == '(?int32, float64)'


def test_to_numpy_fails():
    ds = var * int32
    with pytest.raises(TypeError):
        to_numpy(ds)
    with pytest.raises(TypeError):
        to_numpy(Option(int32))


def test_map():
    fk = Map(int32, Record([('a', int32)]))
    assert fk.key == int32
    assert fk.value == Record([('a', int32)])
    assert fk.value.dict == {'a': int32}
    assert fk.value.fields == (('a', int32),)
    with pytest.raises(TypeError):
        fk.to_numpy_dtype()


def test_map_parse():
    result = dshape("var * {b: map[int32, {a: int64}]}")
    recmeasure = Map(dshape(int32), DataShape(Record([('a', int64)])))
    assert result == DataShape(var, Record([('b', recmeasure)]))


def test_parse_primary_key():
    assert dshape("!int32") == DataShape(PrimaryKey(int32))


def test_primary_key():
    assert PrimaryKey(int32).ty == int32


def test_multiple_primary_keys():
    assert (dshape('var * {a: !int32, b: !int64}') ==
            DataShape(var,
                      Record([('a', PrimaryKey(int32)),
                              ('b', PrimaryKey(int64))])))


def test_primary_key_of_map():
    result = dshape('var * {part: !map[int32, U], supp: !map[int64, T]}')
    assert isinstance(result.measure['part'], PrimaryKey)
    assert isinstance(result.measure['part'].ty, Map)
    assert isinstance(result.measure['supp'], PrimaryKey)
    assert isinstance(result.measure['supp'].ty, Map)
