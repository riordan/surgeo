import abc
import csv
import logging
import os
import shutil
import sqlite3

from surgeo.utilities.error_class import SurgeoError

###############################################################################


class BaseModel(metaclass=abc.ABCMeta):
    '''Base class for creating models.

    Attributes:
        self.db: an sqlite3 database connection shared for all methods
        self.surgeo_folder_path: path to surgeo directory
        self.model_folder_path: path to surgeo model directory
        self.temp_folder_path: path to temp folder
        
    Methods:
        build_up(): setups up data as necessary
        db_check(): checks db for proper table
        db_create(): creates db tables if necessary
        db_destroy(): removes database tables associated with this class.
        get_result_object(): take parameters return result ProxyResult object.
        get_result_string(): takes parameters and returns result as string.
        process_csv(): takes two paths. Reads one, writes to another.
        temp_cleanup(): this function is used with atexit for cleanup.

    '''
    def __init__(self):
        surgeo_folder_path = os.path.join(os.path.expanduser('~'), '.surgeo')
        self.temp_folder_path = os.path.join(os.path.expanduser('~'),
                                             '.surgeo',
                                             'temp')
        self.db_path = os.path.join(surgeo_folder_path, 'surgeo.sqlite')
        self.logger = logging.getLogger(__class__.__name__)
        self.build_up()

    def build_up(self):
        '''Does setup for model.'''
        pass

    @abc.abstractmethod  
    def db_check(self):
        '''Checks whether the proper db tables exist.'''
        raise NotImplementedError

    @abc.abstractmethod      
    def db_create(self):
        '''Downloads information from public sources and creates tables.'''
        raise NotImplementedError
        
    def db_destroy(self):
        '''Destroys tables prefixed with classname.'''
        connection = sqlite3.connect(self.db_path)
        cursor = connection.cursor()
        for row in cursor.execute('''SELECT name FROM sqlite_master WHERE 
                                     type=\'table\''''):
            table_name = row[0]
            table_prefix = row[0].partition('_')[0].lower()
            class_name = self.__class__.__name__.lower()
            if class_name.rstrip('model') == table_prefix:
                cursor.execute('''DROP TABLE {}'''.format(table_name))
        connection.commit()
        connection.close()

    @abc.abstractmethod  
    def get_result_object(self,
                          **kwargs):
        '''Takes arguments and generates result object.'''
        raise NotImplementedError

    def get_result_string(self,
                          **kwargs):
        '''Takes arguments, gets result as string.'''
        proxy_result = self.get_result_object(**kwargs)
        result_string = proxy_result.as_string()
        return result_string

    def process_csv(self,
                    filepath_in,
                    filepath_out, 
                    header_tuple,
                    argument_tuple,
                    continue_on_model_fail=True):
        '''This this the public facing csv processing function.
        
        Args:
            filepath_in: file path of csv from which data is read
            filepath_out: file path of csv where data is written
            header_tuple: takes string args to search for in csv header
            argument_tuple: takes string arguments being put in to model
            continue_on_model_fail: takes boolean
        Returns:
            None
        Raises:
            SurgeoError

        '''
        if not len(header_tuple) == len(attribute_tuple):
            raise SurgeoError('{} header elements and {} attribute elements. '
                              'These should be equal.'
                              .format(len(header_tuple), len(attribute_tuple)))
        number_arguments_for_model = self.get_result_object
        # Open file, determine if zip and name in header
        tempfile = open(filepath_in, 'rU')
        number_of_rows = len(tempfile.readlines())
        tempfile.close()
        # Tuple is header index, argument index, csv_index
        tuple_keys = []
        with open(filepath_in, 'rU') as input_csv:
            csv_reader = csv.reader(input_csv)
            row_1 = next(csv_reader)
            number_of_columns_base = len(row_1)
            # Get index for each header
            for tuple_index, tuple_item in enumerate(header_tuple):
                for row_index, row_item in enumerate(row_1):
                    if tuple_item.lower() == row_item.lower():
                        # header tuple and arugment tuple index are same
                        combined_tuples.append(tuple([tuple_index,
                                                      tuple_index,
                                                      row_index]))
            if len(tuple_keys) != len(header_tuple):
                raise SurgeoError('Number of csv matches inconsistent with '
                                  'number of arguments.')
            # Go through all lines, amended lines with new data, and stage.
            # Writing to string buffer rather than file.
            line_buffer = io.StringIO()
            csv_writer = csv.writer(line_buffer)
            # Create data object based on row two to figure out csv length.
            row_2 = next(csv_reader)
            argument_dict = {}
            for tuple_key in tuple_keys:
                header_index = tuple_key[0]
                argument_index = tuple_key[1]
                argument_value = argument_tuple[argument_index]
                csv_index = tuple_key[2]
                row_value = row_2[csv_index]
                argument_dict[argument_value] = row_value
            result = self.get_result_object(argument_dict)
            attribute_list = result.attribute_list()
            len_attribute_list = len(attribute_list)
            # Write header row first by splicing together
            chopped_header_row = row_1[:number_of_columns]
            header_row = [item for item in itertools.chain(chopped_header_row,
                                                           attribute_list)]
            csv_writer.writerow(header_row)
            # You already did a next() twice on the iterator, line 3
            argument_dict = {}
            for index, entry in enumerate(csv_reader, start=2):
                for tuple_key in tuple_keys:
                    header_index = tuple_key[0]
                    argument_index = tuple_key[1]
                    argument_value = argument_tuple[argument_index]
                    csv_index = tuple_key[2]
                    row_value = row_2[csv_index]
                    argument_dict[argument_value] = row_value
                try:
                    result = self.get_result_object(argument_dict)
                except Exception as e:
                    if continue_on_model_fail is True:
                        raise e
                    else:
                        self.logger.exception(''.join([e.__class__.__name__, 
                                                       ': ',
                                                       e.__str__()]))
                result_list = result.value_list()
                # Chop row in the event that rows are a different length
                chopped_row = entry[:number_of_columns_base]
                # Splice new row together
                new_row = [item for item in
                           itertools.chain(chopped_row, result_list)]
                csv_writer.writerow(new_row)
            with open(filepath_out, 'w+') as f:
                f.write(line_buffer.getvalue())
            line_buffer.close()

    def temp_cleanup(self):
        '''This function is used with atexit to ensure cleanup.'''
        try:
            shutil.rmtree(self.temp_folder_path)
            os.mkdir(self.temp_folder_path)
        # BAD, BAD PYTHON.
        except:
            pass

