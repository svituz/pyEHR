from abc import ABCMeta, abstractmethod
from voluptuous import Schema, Required, MultipleInvalid, Coerce
import time
from uuid import uuid4

from pyehr.ehr.services.dbmanager.errors import InvalidJsonStructureError
from pyehr.utils import cleanup_json, decode_dict


class Record(object):
    """
    Generic record abstract class containing record's base fields.

    :ivar record_id: record's unique identifier
    :ivar creation_time: timestamp of record's creation
    :ivar last_update: timestamp of the last update occurred on the record
    :ivar active: boolean representing if the record is active or not
    """

    __metaclass__ = ABCMeta

    def __eq__(self, other):
        if type(self) == type(other):
            return (self.record_id == other.record_id) and \
                   (not self.record_id is None and not other.record_id is None)
        else:
            return False

    def __ne__(self, other):
        return not self.__eq__(other)

    @abstractmethod
    def __init__(self, creation_time, last_update=None, active=True, record_id=None):
        self.creation_time = creation_time
        self.last_update = last_update or creation_time
        self.active = active
        if record_id:
            self.record_id = str(record_id)
        else:
            self.record_id = uuid4().hex
            
    @abstractmethod
    def new_record_id(self):
        self.record_id = uuid4().hex

    @abstractmethod
    def to_json(self):
        pass

    @staticmethod
    @abstractmethod
    def from_json(json_data):
        pass


class PatientRecord(Record):
    """
    Class representing a patient's record

    :ivar ehr_records: the list of clinical records related to this patient
    """

    def __init__(self, record_id, ehr_records=None, creation_time=None,
                 last_update=None, active=True):
        super(PatientRecord, self).__init__(creation_time or time.time(),
                                            last_update, active, record_id)
        self.ehr_records = ehr_records or []
        
    def new_record_id(self):
        pass

    def get_clinical_record_by_id(self, clinical_record_id):
        """
        Get a :class:`ClinicalRecord` related to the current :class:`PatientRecord`
        by specifying its ID

        :param clinical_record_id: the ID of the :class:`ClinicalRecord` that is going
        to be retrieved
        :type clinical_record_id: the ID as a String
        :return: the :class:`ClinicalRecord` if the ID was matched or None
        :rtype: :class:`ClinicalRecord` or None

        """
        for e in self.ehr_records:
            if str(e.record_id) == str(clinical_record_id):
                return e
        return None

    def to_json(self):
        """
        Encode current record into a JSON dictionary

        :return: a JSON dictionary
        :rtype: dictionary
        """
        attrs = ['record_id', 'creation_time', 'last_update', 'active']
        json = dict()
        for a in attrs:
            json[a] = getattr(self, a)
        json['ehr_records'] = []
        for e in self.ehr_records:
            json['ehr_records'].append(e.to_json())
        return json

    @staticmethod
    def from_json(json_data):
        """
        Create a :class:`PatientRecord` object from the given JSON dictionary, if one or more :class:`ClinicalRecord`
        objects in JSON format are encoded in ehr_records field, create these objects as well

        :param json_data: the JSON corresponding to the :class:`PatientRecord` object
        :type json_data: dictionary
        :return: a :class:`PatientRecord` object
        :rtype: :class:`PatientRecord`
        """
        schema = Schema({
            'creation_time': float,
            'last_update': float,
            'record_id': str,
            'active': bool,
            Required('ehr_records'): list
        })
        try:
            json_data = cleanup_json(decode_dict(json_data))
            schema(json_data)
            ehr_records = [ClinicalRecord.from_json(ehr) for ehr in json_data['ehr_records']]
            json_data['ehr_records'] = ehr_records
            return PatientRecord(**json_data)
        except MultipleInvalid:
            raise InvalidJsonStructureError('JSON record\'s structure is not compatible with PatientRecord object')


class ClinicalRecord(Record):
    """
    Class representing a clinical record

    :ivar archetype: the OpenEHR archetype class related to this clinical record
    :ivar ehr_data: clinical data in OpenEHR syntax
    """

    def __init__(self, ehr_data, creation_time=None, last_update=None,
                 active=True, record_id=None):
        super(ClinicalRecord, self).__init__(creation_time or time.time(),
                                             last_update, active, record_id)
        self.ehr_data = ehr_data
        
    def new_record_id(self):
        super(ClinicalRecord, self).new_record_id()

    def to_json(self):
        """
        Encode current record into a JSON dictionary

        :return: a JSON dictionary
        :rtype: dictionary
        """
        attrs = ['creation_time', 'last_update', 'active']
        json = dict()
        for a in attrs:
            json[a] = getattr(self, a)
        if self.record_id:
            json['record_id'] = str(self.record_id)
        json['ehr_data'] = self.ehr_data.to_json()
        return json

    @staticmethod
    def from_json(json_data):
        """
        Create a :class:`ClinicalRecord` object from the given JSON dictionary

        :param json_data: the JSON corresponding to the :class:`ClinicalRecord` object
        :type json_data: dictionary
        :return: a :class:`ClinicalRecord` object
        :rtype: :class:`ClinicalRecord`
        """
        schema = Schema({
            Required('ehr_data'): dict,
            'creation_time': float,
            'last_update': float,
            'active': bool,
            'record_id': str,
        })
        try:
            json_data = cleanup_json(decode_dict(json_data))
            schema(json_data)
            json_data['ehr_data'] = ArchetypeInstance.from_json(json_data['ehr_data'])
            return ClinicalRecord(**json_data)
        except MultipleInvalid:
            raise InvalidJsonStructureError('JSON record\'s structure is not compatible with ClinicalRecord object')


class ArchetypeInstance(object):
    """
    Class representing an openEHR Archetype instance

    :ivar archetype: the openEHR Archetype class related to this instance
    :ivar data: clinical data related to this instance represented as a dictionary.
                Values of the dictionary can be :class:`ArchetypeInstance` objects.
    """

    def __init__(self, archetype_class, data):
        self.archetype_class = archetype_class
        self.data = data

    def to_json(self):
        """
        Encode current record into a JSON dictionary

        :return: a JSON dictionary
        :rtype: dictionary
        """
        def encode_dict_data(record_data):
            data = dict()
            for k, v in record_data.iteritems():
                if isinstance(v, ArchetypeInstance):
                    data[k] = v.to_json()
                elif isinstance(v, dict):
                    data[k] = encode_dict_data(v)
                elif isinstance(v, list):
                    data[k] = encode_list_data(v)
                else:
                    data[k] = v
            return data

        def encode_list_data(record_data):
            data = list()
            for x in record_data:
                if isinstance(x, ArchetypeInstance):
                    data.append(v.to_json)
                elif isinstance(x, dict):
                    data.append(encode_dict_data(x))
                elif isinstance(x, list):
                    data.append(encode_list_data(x))
                else:
                    data.append(x)
            return data

        json = {
            'archetype': self.archetype_class,
            'data': dict()
        }
        for k, v in self.data.iteritems():
            if isinstance(v, ArchetypeInstance):
                json['data'][k] = v.to_json()
            elif isinstance(v, dict):
                json['data'][k] = encode_dict_data(v)
            elif isinstance(v, list):
                json['data'][k] = encode_list_data(v)
            else:
                json['data'][k] = v
        return json

    @staticmethod
    def from_json(json_data):
        """
        Create an :class:`ArchetypeInstance` object from a given JSON dictionary

        :param json_data: the JSON corresponding to the :class:`ArchetypeInstance` object
        :type json_data: dictionary
        :return: an :class:`ArchetypeInstance` object
        :rtype: :class:`ArchetypeInstance`
        """
        def is_archetype(dict):
            return ('archetype' in dict) and ('data' in dict)

        def decode_dict_data(dict_data):
            data = dict()
            for k, v in dict_data.iteritems():
                if isinstance(v, dict):
                    if is_archetype(v):
                        data[k] = ArchetypeInstance.from_json(v)
                    else:
                        data[k] = decode_dict_data(v)
                elif isinstance(v, list):
                    data[k] = decode_list_data(v)
                else:
                    data[k] = v
            return data

        def decode_list_data(dict_data):
            data = list()
            for x in dict_data:
                if isinstance(x, dict):
                    if is_archetype(x):
                        data.append(ArchetypeInstance.from_json(x))
                    else:
                        data.append(decode_dict_data(x))
                elif isinstance(x, list):
                    data.append(decode_list_data(x))
                else:
                    data.append(x)
            return data

        schema = Schema({
            Required('archetype'): str,
            Required('data'): dict,
        })
        try:
            json_data = cleanup_json(decode_dict(json_data))
            schema(json_data)
            archetype_data = dict()
            for k, v in json_data['data'].iteritems():
                if isinstance(v, dict):
                    if is_archetype(v):
                        archetype_data[k] = ArchetypeInstance.from_json(v)
                    else:
                        archetype_data[k] = decode_dict_data(v)
                elif isinstance(v, list):
                    archetype_data[k] = decode_list_data(v)
                else:
                    archetype_data[k] = v
            return ArchetypeInstance(json_data['archetype'], archetype_data)
        except MultipleInvalid:
            raise InvalidJsonStructureError('JSON record\'s structure is not compatible with ArchetypeInstance object')