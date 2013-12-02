from openehr.ehr.services.dbmanager.drivers.mongo import MongoDriver
from openehr.utils import get_logger
from openehr.ehr.services.dbmanager.dbservices.wrappers import PatientRecord, ClinicalRecord
from openehr.ehr.services.dbmanager.errors import CascadeDeleteError


class DBServices(object):

    def __init__(self, host, database, patients_collection,
                 ehr_collection, port=None, user=None,
                 passwd=None, logger=None):
        self.host = host
        self.database = database
        self.patients_collection = patients_collection
        self.ehr_collection = ehr_collection
        self.port = port
        self.user = user
        self.passwd = passwd
        self.logger = logger or get_logger('db_services')

    def save_patient(self, patient_record):
        """
        >>> dbs = DBServices('localhost', 'test_database', 'test_patients_coll', 'test_ehr_coll')
        >>> pat_rec = PatientRecord()
        >>> pat_rec = dbs.save_patient(pat_rec)
        >>> len(pat_rec.ehr_records) == 0
        True
        >>> pat_rec.record_id is None
        False
        >>> pat_rec.active
        True
        >>> dbs.delete_patient(pat_rec) #cleanup
        """
        with MongoDriver(self.host, self.database, self.patients_collection,
                         self.port, self.user, self.passwd, self.logger) as driver:
            if patient_record.record_id is None:
                patient_record.record_id = driver.add_record(patient_record._to_document())
                return patient_record
            else:
                #TODO update or error?
                pass

    def _get_active_records(self, driver):
        return driver.get_records_by_query({'active': True})

    def get_patients(self, active_records_only=True):
        with MongoDriver(self.host, self.database, self.patients_collection,
                         self.port, self.user, self.passwd, self.logger) as driver:
            if not active_records_only:
                return driver.get_all_records()
            else:
                return self._get_active_records()

    def get_patient(self, patient_id):
        with MongoDriver(self.host, self.database, self.patients_collection,
                         self.port, self.user, self.passwd, self.logger) as driver:
            return driver.get_record_by_id(patient_id)

    def hide_patient(self, patient):
        """
        >>> dbs = DBServices('localhost', 'test_database', 'test_patients_coll', 'test_ehr_coll')
        >>> pat_rec = PatientRecord()
        >>> pat_rec = dbs.save_patient(pat_rec)
        >>> last_update = pat_rec.last_update
        >>> print pat_rec.active
        True
        >>> pat_rec = dbs.hide_patient(pat_rec)
        >>> print pat_rec.active
        False
        >>> last_update < pat_rec.last_update
        True
        >>> dbs.delete_patient(pat_rec) #cleanup
        """
        #TODO: hide EHR records as well
        rec = self._hide_record(patient, self.patients_collection)
        return rec

    def delete_patient(self, patient, cascade_delete=False):
        if cascade_delete and len(patient.ehr_records) > 0:
            raise CascadeDeleteError('Unable to delete patient record with ID %s, %d EHR records still connected',
                                     patient.record_id, len(patient.ehr_records))
        else:
            #TODO: delete EHR records as well
            with MongoDriver(self.host, self.database, self.patients_collection, self.port,
                             self.user, self.passwd, self.logger) as driver:
                driver.delete_record(patient.record_id)
                return None

    def _update_record_timestamp(self, update_condition):
        import time
        update_condition['last_update'] = time.time()
        return update_condition

    def _hide_record(self, record, collection):
        with MongoDriver(self.host, self.database, collection, self.port,
                         self.user, self.passwd, self.logger) as driver:
            update_condition = {'active': False}
            driver.update_record(record.record_id,
                                 {'$set': self._update_record_timestamp(update_condition)})
            record.active = False
            record.last_update = update_condition['last_update']
            return record