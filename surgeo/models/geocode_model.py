
import atexit
import collections
import decimal
import ftplib
import itertools
import os
import sqlite3
import sys
import zipfile

from surgeo.models.model_base import BaseModel
from surgeo.utilities.result import Result


class GeocodeModel(BaseModel):
    '''Contains data references and methods for running a Geocode model.'''
    
    def __init__(self):
        super().__init__()
    
    def db_check(self):
        '''This checks accuracy of database.
        
           If valid, returns True.
           If invalid, returns False.
        
           Count geocode_logical is 33233
           Count geocode_data is 9541315
        
        '''
        
        connection = sqlite3.connect(self.db_path)
        cursor = connection.cursor()
        try:
            # geocode_logical
            cursor.execute('''SELECT COUNT(*) FROM geocode_logical''')
            geocode_logical_count = int(cursor.fetchone()[0])
            assert(geocode_logical_count == 33233)
            # geocode_data
            cursor.execute('''SELECT COUNT(*) FROM geocode_race''')
            geocode_data_count = int(cursor.fetchone()[0])
            assert(geocode_data_count == 9541315)
            return True
        except (sqlite3.Error, AssertionError) as e:
            self.logger.exception(''.join([e.__class__.__name__,
                                           ': ',
                                           e.__str__()]))
            return False

    def db_create(self):
        '''Creates geocode database based on Census 2000 data.

           This function first downloads a geographic header file for each 
           state. It then downloads file 00002 for each state. These are 
           downloaded in zip format, and then unzipped. It then creates two 
           tables, geocode_logical and logical_race and populates the 
           database. The geocode_logical contains data for geographic areas.
           Logical record from the geocode_race directly correlates with a 
           specific population in the geographic area, which is broken down by 
           race.
           
           Following this, certain redacted data is reformed. For 
           confidentiality purposes, the Census Bureau scrubs certain data on 
           race. This reconstitutes that data. We take the total number of 
           scrubbed items, and then divide it equally between the scrubbed 
           categories. This yields an approximation.
           
        '''
        
######## FTP
        # Remove downloaded files in event of a hangup.
        atexit.register(self.temp_cleanup)
        ftp = ftplib.FTP('ftp.census.gov')
        ftp.login()
        ftp.cwd('census_2000/datasets/Summary_File_1')
        # List files
        state_list = ftp.nlst()
        # Drop all elements prior to states
        state_list = itertools.dropwhile(lambda x: x != 'Alabama', state_list)
        # Make dropwhile object to list
        state_list = list(state_list)
        zip_files_downloaded = []
        for state in state_list:
            ftp.cwd('/')
            ftp.cwd(''.join(['census_2000/datasets/Summary_File_1',
                             '/',
                             state]))
            file_list = ftp.nlst()
            for item in file_list:
                if '00002_uf1.zip' in item or 'geo_uf1.zip' in item:
                    file_path = os.path.join(self.temp_folder_path, item)
                    zip_files_downloaded.append(file_path)
                    ftp.retrbinary('RETR ' + item, open(file_path,
                                                        'wb+').write)
######## unzip files
        for zipfile_path in zip_files_downloaded:
            # Name of XXgeo_uf1.zip --> XXgeo.uf1
            # Name of XX00002_uf1.zip --> XX0000.uf1
            file_component = os.path.basename(zipfile_path).replace('.zip',
                                                                    '')
            file_component = file_component.replace('_', '.')
            dir_component = os.path.dirname(zipfile_path)
            # Zip file is now and iterator to save on ram.
            with zipfile.ZipFile(zipfile_path, 'r') as f:
                with f.open(file_component, 'r') as f2:
                    with open(os.path.join(dir_component,
                              file_component),
                              'w+b') as f3:
                        for line in f2:
                            f3.write(line)
######## Commit to db
        try:
            connection = sqlite3.connect(self.db_path)
            cursor = connection.cursor()
            cursor.execute('''CREATE TABLE IF NOT EXISTS
                              geocode_logical(id INTEGER PRIMARY KEY,
                              state TEXT, summary_level TEXT, 
                              logical_record TEXT, zcta TEXT)''')
            cursor.execute('''CREATE TABLE IF NOT EXISTS geocode_race(id
                              INTEGER PRIMARY KEY, state TEXT, 
                              logical_record TEXT, num_white REAL, 
                              num_black REAL, num_ai REAL, num_api REAL,
                              num_hispanic REAL, num_multi REAL)''')
            # now start loading to db
            list_of_filenames = os.listdir(self.temp_folder_path)
            number_of_filenames = len(list_of_filenames)
            for index, filename in enumerate(list_of_filenames):
                # First the geographic header file
                if 'geo.uf1' in filename:
                    file_path = os.path.join(self.temp_folder_path,
                                             filename)
                    DESIRED_SUMMARY_LEVEL = '871'
                    # Only latin1 appears to work, even thoug site specifies ascii
                    with open(file_path, 'r', encoding='latin-1') as f3:
                        for line in f3:
                            state = line[6:8]
                            summary_level = line[8:11]
                            logical_record = line[18:25]
                            zcta = line[160:165]
                            # Only ZCTA wide numbers considered
                            if not summary_level == DESIRED_SUMMARY_LEVEL:
                                continue
                            # Remove 'XX' large / 'HH' hydrological prefixes
                            if 'XX' or 'HH' in zcta:
                                continue
                            cursor.execute('''INSERT INTO geocode_logical(id,
                                              state, summary_level, 
                                              logical_record, zcta)
                                              VALUES(NULL, ?, ?, ?, ?)''',
                                           (state,
                                            summary_level,
                                            logical_record,
                                            zcta))
            for index, filename in enumerate(list_of_filenames):
                # First the geographic header file
                if '00002.uf1' in filename:
                    file_path = os.path.join(self.temp_folder_path,
                                             filename)
                    with open(file_path, 'r', encoding='latin-1') as f4:
                        for line in f4:
                            state = line[5:7]
                            logical_record = line[15:22]
                            table_p8 = line.split(',')[86:103]
                            # Breaking up table p8
                            total_pop = table_p8[0]
                            total_not_hispanic = table_p8[1]
                            num_white = table_p8[2]
                            num_black = table_p8[3]
                            num_ai = table_p8[4]
                            num_asian = table_p8[5]
                            num_pacisland = table_p8[6]
                            num_api = str(int(num_asian) + int(num_pacisland))
                            num_other = table_p8[7]
                            num_multi = table_p8[8]
                            num_hispanic = table_p8[9]
                            cursor.execute('''INSERT INTO geocode_race(
                                              id, state, logical_record,
                                              num_white, num_black,
                                              num_ai, num_api,
                                              num_hispanic, num_multi) VALUES(
                                              NULL, ?, ?, ?, ?, ?, ?, ?, ?)''',
                                           (state,
                                            logical_record,
                                            num_white,
                                            num_black,
                                            num_ai,
                                            num_api,
                                            num_multi,
                                            num_hispanic))
            cursor.execute('''CREATE INDEX IF NOT EXISTS zcta_index ON
                              geocode_logical(zcta)''')
            cursor.execute('''CREATE INDEX IF NOT EXISTS logical_record_index 
                              ON geocode_race(logical_record)''')
            # Now commit
            connection.commit()
            connection.close()
        except sqlite3.Error as e:
            connection.rollback()
            connection.close()
            raise e

    def get_result_object(self, zip_code):
        '''Takes zip code, returns race object.

           Args:
            zip_code: 5 digit zip code
        Returns:
            Result object with attributes: 
                zcta string
                hispanic float
                white float
                black float
                api float 
                ai float
                multi float
        Raises:
            None
        
        '''
        connection = sqlite3.connect(self.db_path)
        cursor = connection.cursor()
        cursor.execute('''SELECT state, logical_record FROM geocode_logical 
                          WHERE zcta=?''', (zip_code,))
        try:
            state, logical_record = cursor.fetchone()
        except TypeError:
            error_result = Result({'zcta': 0,
                                   'hispanic': 0,
                                   'white': 0,
                                   'black': 0,
                                   'api': 0,
                                   'ai': 0,
                                   'multi': 0}).errorify()
            return error_result
        cursor.execute('''SELECT num_hispanic, num_white, num_black,
                          num_api, num_ai, num_multi FROM geocode_race
                          WHERE logical_record=? AND state=?''',
                       (logical_record, state))
        try:
            row = cursor.fetchone()
        except TypeError:
            error_result = Result({'zcta': 0,
                                   'hispanic': 0,
                                   'white': 0,
                                   'black': 0,
                                   'api': 0,
                                   'ai': 0,
                                   'multi': 0}).errorify()
            return error_result
        count_hispanic = row[0]
        count_white = row[1]
        count_black = row[2]
        count_api = row[3]
        count_ai = row[4]
        count_multi = row[5]
        # Float because dividing later
        total = float(count_hispanic +
                      count_white +
                      count_black +
                      count_api +
                      count_ai +
                      count_multi)
        argument_dict = {'zcta' : zip_code,
                         'hispanic' : round((count_hispanic/total), 5),
                         'white' : round((count_white/total), 5),
                         'black' : round((count_black/total), 5),
                         'api' : round((count_api/total), 5),
                         'ai' : round((count_ai/total), 5),
                         'multi' : round((count_multi/total), 5)}
        result = Result(**argument_dict)
        return result
