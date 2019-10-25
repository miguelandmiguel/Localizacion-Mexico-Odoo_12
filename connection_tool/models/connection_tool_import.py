# -*- coding: utf-8 -*-

import shutil
from ftplib import FTP
try:
    from itertools import ifilter as filter
except ImportError:
    pass
try:
    from itertools import imap
except ImportError:
    imap=map
import io
from io import BytesIO
try:
    from StringIO import StringIO
except ImportError:
    from io import StringIO
try:
    import xlrd
    try:
        from xlrd import xlsx
    except ImportError:
        xlsx = None
except ImportError:
    xlrd = xlsx = None
from tempfile import TemporaryFile
import base64
import codecs
import collections
import unicodedata
import chardet
import datetime
import itertools
import logging
import psycopg2
import operator
import os
import re
import requests
import threading
from dateutil.relativedelta import relativedelta
import time
from odoo import api, fields, models, registry, _, SUPERUSER_ID
from odoo.exceptions import AccessError, UserError
from odoo.tools.translate import _
from odoo.tools.mimetypes import guess_mimetype
from odoo.tools.safe_eval import safe_eval
from odoo.tools import config, DEFAULT_SERVER_DATE_FORMAT, DEFAULT_SERVER_DATETIME_FORMAT, pycompat
import csv

_logger = logging.getLogger(__name__)

try:
    import xlsxwriter
except ImportError:
    _logger.debug('Can not import xlsxwriter`.')

FIELDS_RECURSION_LIMIT = 2
ERROR_PREVIEW_BYTES = 200
DEFAULT_IMAGE_TIMEOUT = 3
DEFAULT_IMAGE_MAXBYTES = 10 * 1024 * 1024
DEFAULT_IMAGE_REGEX = r"(?:http|https)://.*(?:png|jpe?g|tiff?|gif|bmp)"
DEFAULT_IMAGE_CHUNK_SIZE = 32768
IMAGE_FIELDS = ["icon", "image", "logo", "picture"]
BOM_MAP = {
    'utf-16le': codecs.BOM_UTF16_LE,
    'utf-16be': codecs.BOM_UTF16_BE,
    'utf-32le': codecs.BOM_UTF32_LE,
    'utf-32be': codecs.BOM_UTF32_BE,
}
try:
    import xlrd
    try:
        from xlrd import xlsx
    except ImportError:
        xlsx = None
except ImportError:
    xlrd = xlsx = None
try:
    from . import odf_ods_reader
except ImportError:
    odf_ods_reader = None

FILE_TYPE_DICT = {
    'text/csv': ('csv', True, None),
    'application/octet-stream': ('csv', True, None),
    'application/vnd.ms-excel': ('xls', xlrd, 'xlrd'),
    'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet': ('xlsx', xlsx, 'xlrd >= 1.0.0'),
    'application/vnd.oasis.opendocument.spreadsheet': ('ods', odf_ods_reader, 'odfpy')
}
EXTENSIONS = {
    '.' + ext: handler
    for mime, (ext, handler, req) in FILE_TYPE_DICT.items()
}

# from odoo.addons.connection_tool.models.common_import import *

class StrToBytesIO(io.BytesIO):
    def write(self, s, encoding='utf-8'):
        return super().write(s.encode(encoding))


def remove_accents(s):
    def remove_accent1(c):
        return unicodedata.normalize('NFD', c)[0]
    return u''.join(map(remove_accent1, s))

COL = {'A':0,'B':1,'C':2,'D':3,'E':4,'F':5,'G':6,'H':7,'I':8,'J':9,'K':10,'L':11,'M':12,'N':13,'O':14,'P':15,
        'Q':16,'R':17,'S':18,'T':19,'U':20,'V':21,'W':22,'X':23,'Y':24,'Z':25}

def get_row_col(row, column, index):
    try:
        row = abs(int(row) - 1)
    except:
        raise osv.except_osv(_('Error!'), _('Row is wrong deffined in acction type Field Map'))
    try:
        col = int(column)
    except:
        col = i = 0
        for char in column.upper():
            if char in COL.keys():
                col += COL[char] + 26 * i
                i += 1
    return row+index, col

TYPE_SELECTION = [
    ('first_index','Define First Index'),
    ('register_id','Register ID'),
    ('register','Register'),
    ('line','Line of Register'),
    ('next_index','Next Index'),
    ('check','Check'),
    ('jump','Jump To Sequence'),
    ('python','Python'),
]
IMPORT_TYPE = [
    ('csv','Import CSV File'),
    ('file','Import XLS File'),
    ('postgresql','PostgreSQL'),
    ('ftp','FTP'),
    ('wizard','Wizard'),
    ('xml-rpc','XML RPC')
]
OUTPUT_TYPE = [
    ('csv', 'CSV'),
    ('xlsx', 'Excel (xlsx)'),
    ('csv_meta', 'CSV with Metadata'),
    ('text', 'Text'),
    ('text_columns', 'Text with Columns Header'),
]
OUTPUT_DESTINATION = [
    ('field', 'None'),
    ('this_database', 'This Database'),
    ('ftp', 'FTP'),
    ('ftp_traffic', 'FTP w/Control File'),
    ('local', 'Local Directory'),
    ('xml-rpc', 'XML-RPC'),
]
OPTIONS = {
    'headers': True, 'advanced': True, 'keep_matches': False, 
    'name_create_enabled_fields': {}, 'encoding': 'utf-8', 'separator': ',', 
    'quoting': '"', 'date_format': '%Y-%m-%d', 'datetime_format': '', 
    'float_thousand_separator': ',', 
    'float_decimal_separator': '.'
}

{'headers': True, 'separator': ',', 'quoting': '"', 'date_format': '%Y-%m-%d', 'datetime_format': ''}

FIELD_TYPES = [(key, key) for key in sorted(fields.Field.by_type)]



class AccountMove(models.Model):
    _inherit = "account.move"

    @api.multi
    def assert_balanced(self):
        if not self.ids:
            return True
        ctx = self._context
        if ctx.get('ConnectionTool', False) == True:
            return True
        else:
            return super(AccountMove, self).assert_balanced()
        return True


class ConnectionToolImportWiz(models.TransientModel):
    _name = 'connection_tool.import.wiz'
    _description = 'Run Import Manually'

    def _import_calculation_files(self):
        with api.Environment.manage():
            # As this function is in a new thread, I need to open a new cursor, because the old one may be closed
            new_cr = self.pool.cursor()
            self = self.with_env(self.env(cr=new_cr))
            self.env['connection_tool.import'].run_import(use_new_cursor=self._cr.dbname)
            new_cr.close()
            return {}

    def import_calculation(self):
        threaded_calculation = threading.Thread(target=self._import_calculation_files, args=())
        threaded_calculation.start()
        return {'type': 'ir.actions.act_window_close'}


class Configure(models.Model):
    _name = 'connection_tool.import'
    _inherit = ['mail.thread']
    _description = "Import Files Configure"
    _order = 'name'

    name = fields.Char(string='Name',required=True)
    model_id = fields.Many2one('ir.model', 'Model')
    source_connector_id = fields.Many2one('connection_tool.connector', 'Source Connector')
    source_type = fields.Selection(related='source_connector_id.type', string="Source Type", store=True, readonly=True)
    source_ftp_path = fields.Char(string='FTP Path', default="/")
    source_ftp_path_done = fields.Char(string='FTP Path Done', default="/")
    source_ftp_filename = fields.Char(string='Import Filename')
    source_ftp_refilename = fields.Char(string='Regular Expression Filename')
    source_ftp_re = fields.Boolean(string='Regular Expression?')
    source_ftp_read_control = fields.Char('Read Control Filename')
    source_ftp_write_control = fields.Char('Write Control Filename')
    source_python_script = fields.Text("Python Script")
    recurring_import = fields.Boolean('Recurring Import?')
    source_ftp_filenamedatas = fields.Text(string='Import Filename')
    output_messages = fields.Html('Log...')

    output_destination = fields.Selection(OUTPUT_DESTINATION, string='Destination', help="Output file destination")
    type = fields.Selection(IMPORT_TYPE, 'Type', default='csv', index=True, change_default=True, track_visibility='always')
    quoting = fields.Char('Quoting', size=8, default="\"")
    separator = fields.Char('Separator', size=8, default="|")
    with_header = fields.Boolean(string='With Header?', default=1)
    datas_fname = fields.Char('Filename')
    datas_file = fields.Binary('File', help="File to check and/or import, raw binary (not base64)")
    headers = fields.Html('Headers')


    @api.multi
    def button_import(self):
        print("button")

    @api.model
    def run_import(self, use_new_cursor=False):
        try:
            if use_new_cursor:
                cr = registry(self._cr.dbname).cursor()
                self = self.with_env(self.env(cr=cr))  # TDE FIXME
            self._run_import_files(use_new_cursor=use_new_cursor)
        finally:
            if use_new_cursor:
                try:
                    self._cr.close()
                except Exception:
                    pass
        return {}

    def getCsvFile(self, path):
        tmp_list = []
        with open(path, 'r') as f:
            reader = csv.reader(f, delimiter=',')
            tmp_list = list(reader)
        return tmp_list

    @api.model
    def _run_import_files(self, use_new_cursor=False):
        for imprt in self.sudo().search([('recurring_import','=', True)]):
            imprt.sudo()._run_import_files_log_init(use_new_cursor=use_new_cursor)
            msg = "<span><b>Inicia Proceso:</b> %s</span><hr/>"%(time.strftime('%Y-%m-%d %H:%M:%S'))
            imprt.sudo()._run_import_files_log(use_new_cursor=use_new_cursor, msg=msg)
            imprt.import_files(use_new_cursor=use_new_cursor)
            if use_new_cursor:
                self._cr.commit()
            msg = "<span><b>Termina Proceso:</b> %s</span><hr/>"%(time.strftime('%Y-%m-%d %H:%M:%S'))
            imprt.sudo()._run_import_files_log(use_new_cursor=use_new_cursor, msg=msg)
        if use_new_cursor:
            self._cr.commit()


    @api.model
    def import_files(self, use_new_cursor=False):
        if use_new_cursor:
            cr = registry(self._cr.dbname).cursor()
            self = self.with_env(self.env(cr=cr))
        directory = "/tmp/tmpsftp%s"%(self.id)
        if not os.path.exists(directory):
            os.makedirs(directory)
        dd = os.listdir(directory)
        if (len(dd) == 0) or (len(dd) == 3 and dd[0] in ['done', 'csv', 'tmpimport', 'import']):
            pass
        else:
            self.sudo()._run_import_files_log(use_new_cursor=use_new_cursor, msg="<span>Procesando archivos previos</span><br />")
            if use_new_cursor:
                cr.commit()
                cr.close()
            return None
        if not os.path.exists(directory+'/done'):
            os.makedirs(directory+'/done')
        if not os.path.exists(directory+'/csv'):
            os.makedirs(directory+'/csv')
        if not os.path.exists(directory+'/tmpimport'):
            os.makedirs(directory+'/tmpimport')
        if not os.path.exists(directory+'/import'):
            os.makedirs(directory+'/import')

        imprt = self.source_connector_id.with_context(imprt_id=self.id, directory=directory)
        res = imprt.getFTData()
        if res == None:
            self.sudo()._run_import_files_log(use_new_cursor=use_new_cursor, msg="<span>No existe archivo para procesar</span><br />")
            if use_new_cursor:
                cr.commit()
                cr.close()
            return res
        elif res and res.get('error'):
            self.sudo()._run_import_files_log(use_new_cursor=use_new_cursor, msg="<span>%s</span><br/>"%res.get('error'))
            if use_new_cursor:
                cr.commit()
                cr.close()
            return res

        pairs = []
        for files in os.listdir(directory):
            if files in ['done', 'csv', 'tmpimport', 'import']:
                continue
            location = os.path.join(directory, files)
            size = os.path.getsize(location)
            pairs.append((size, files))
        pairs.sort(key=lambda s: s[0])
        for dir_files in pairs:
            files = dir_files[1]
            if files in ['done', 'csv', 'tmpimport', 'import']:
                continue
            self.import_files_datas(use_new_cursor=use_new_cursor, files=files, directory=directory, imprt=imprt)
        if use_new_cursor:
            cr.commit()
            cr.close()
        try:
            shutil.rmtree(directory)
        except:
            pass
        imprt._delete_ftp_filename(self.source_ftp_write_control, automatic=True)

    @api.model
    def import_files_datas(self, use_new_cursor=False, files=False, directory=False, imprt=False):
        if use_new_cursor:
            cr = registry(self._cr.dbname).cursor()
            self = self.with_env(self.env(cr=cr))

        self.source_ftp_filename = files
        imprt = self.source_connector_id.with_context(imprt_id=self.id, directory=directory)
        if use_new_cursor:
            cr.commit()
        if self.source_python_script:
            options = {
                'encoding': 'utf-8'
            }
            if self.type == 'csv':
                if not self.quoting and self.separator:
                    self.sudo()._run_import_files_log(use_new_cursor=use_new_cursor, msg="<span>Set Quoting and Separator fields before load CSV File</span><br />")
                options = OPTIONS
                options['quoting'] = self.quoting or OPTIONS['quoting']
                options['separator'] = self.separator or OPTIONS['separator']
            info = open(directory+'/'+files, "r")
            import_data = self._convert_import_data(options, info.read().encode("utf-8"))
            res = None
            try:
                res = self.get_source_python_script(use_new_cursor=use_new_cursor, files=files, import_data=import_data, options=options)
            except Exception as e:
                self.sudo()._run_import_files_log(use_new_cursor=use_new_cursor, msg="<span>%s in macro</span><br />"%e)
                imprt._delete_ftp_filename(self.source_ftp_write_control, automatic=True)
        if use_new_cursor:
            cr.commit()
            cr.close()

    @api.model
    def get_source_python_script(self, use_new_cursor=False, files=False, import_data=False, options=False):
        if use_new_cursor:
            cr = registry(self._cr.dbname).cursor()
            self = self.with_env(self.env(cr=cr))
        localdict = {
            'this':self,
            'file_name': files.replace(".dat", ".csv").replace(".DAT", ".csv"),
            'directory': "/tmp/tmpsftp%s"%(self.id),
            'csv': csv,
            'open': open,
            're': re,
            'time': time,
            'datetime': datetime,
            'context': dict(self._context),
            '_logger': _logger,
            'UserError': UserError,
            'import_data': import_data,
            'import_fields': []
        }
        if self.source_python_script:
            try:
                safe_eval(self.source_python_script, localdict, mode='exec', nocopy=True)
            except Exception as e:
                self.sudo()._run_import_files_log(use_new_cursor=use_new_cursor, msg="<span>%s in macro</span><br />"%e)
                if use_new_cursor:
                    cr.commit()
                    cr.close()
            result = localdict.get('result',False)
            if result:
                header = result.get('header') or []
                body = result.get('body') or []
                fileTmp = {}
                procesados = True
                for ext_id in body:
                    if self.output_destination == 'this_database':
                        fileTmp[ext_id] = None
                        try:
                            msg="<span>Archivo: <b>%s</b> </span><br /><span>External ID: %s</span><br />"%(files, ext_id)
                            self.sudo()._run_import_files_log(use_new_cursor=use_new_cursor, msg=msg)
                            file_ext_id = "/tmp/tmpsftp%s/import/%s.csv"%(self.id, ext_id)
                            output = io.BytesIO()
                            writer = pycompat.csv_writer(output, quoting=1)
                            with open(file_ext_id, 'r') as f:
                                reader = csv.reader(f, delimiter=',')
                                for tmp_list in list(reader):
                                    writer.writerow(tmp_list)
                            import_wizard = self.env['base_import.import'].sudo().create({
                                'res_model': self.model_id.model,
                                'file_name': '%s.csv'%(ext_id),
                                'file': output.getvalue(),
                                'file_type': 'text/csv',
                            })
                            results = import_wizard.with_context(ConnectionTool=True).sudo().do(header, [], {'headers': True, 'separator': ',', 'quoting': '"', 'date_format': '%Y-%m-%d', 'datetime_format': ''}, False)
                            if results.get("ids"):
                                fileTmp[ext_id] = results['ids']
                                msg="<span>Database ID: %s</span><br />"%(results['ids'])
                                # directory = "/tmp/tmpsftp%s"%(self.id)
                                # imprt = self.source_connector_id.with_context(imprt_id=self.id, directory=directory)
                                # shutil.move(directory+'/'+files, directory+'/done/'+files)
                                # imprt._move_ftp_filename(files, automatic=True)
                            else:
                                procesados = False
                                msg="<span>Error: %s</span> "%(results['messages'])
                            self.sudo()._run_import_files_log(use_new_cursor=use_new_cursor, msg=msg)
                        except Exception as e:
                            self.sudo()._run_import_files_log(use_new_cursor=use_new_cursor, msg="<span>%s in macro</span><br />"%e)
                            if use_new_cursor:
                                cr.commit()
                                cr.close()
                if procesados:
                    directory = "/tmp/tmpsftp%s"%(self.id)
                    imprt = self.source_connector_id.with_context(imprt_id=self.id, directory=directory)
                    shutil.move(directory+'/'+files, directory+'/done/'+files)
                    imprt._move_ftp_filename(files, automatic=True)

        self.sudo()._run_import_files_log(use_new_cursor=use_new_cursor, msg="<hr />")
        if use_new_cursor:
            cr.commit()
            cr.close()



    @api.model
    def _run_import_files_log_init(self, use_new_cursor=False):
        if use_new_cursor:
            cr = registry(self._cr.dbname).cursor()
            self = self.with_env(self.env(cr=cr))
        message = ""
        if self.output_messages:
            message = self.output_messages
        res_id = self.write({
            "output_messages": ""
        })
        if use_new_cursor:
            cr.commit()
            cr.close()

    @api.model
    def _run_import_files_log(self, use_new_cursor=False, msg=""):
        if use_new_cursor:
            cr = registry(self._cr.dbname).cursor()
            self = self.with_env(self.env(cr=cr))
        message = ""
        if self.output_messages:
            message = self.output_messages
        res_id = self.write({
            "output_messages": message + msg
        })
        if use_new_cursor:
            cr.commit()
            cr.close()



    @api.model
    def _convert_import_data(self, options, datas):
        import_fields = []
        rows_to_import = self._read_file(options, datas)
        data = list(itertools.islice(rows_to_import, 0, None))
        return data

    @api.multi
    def _read_file(self, options, datas):
        """ Dispatch to specific method to read file content, according to its mimetype or file type
            :param options : dict of reading options (quoting, separator, ...)
        """
        self.ensure_one()
        # guess mimetype from file content
        mimetype = guess_mimetype(datas)
        (file_extension, handler, req) = FILE_TYPE_DICT.get(mimetype, (None, None, None))
        if handler:
            try:
                return getattr(self, '_read_' + file_extension)(options, datas)
            except Exception:
                _logger.warn("Failed to read file '%s' (transient id %d) using guessed mimetype %s", self.datas_fname or '<unknown>', self.id, mimetype)
        # try reading with user-provided mimetype
        (file_extension, handler, req) = FILE_TYPE_DICT.get(self.type, (None, None, None))
        if handler:
            try:
                return getattr(self, '_read_' + file_extension)(options, datas)
            except Exception:
                _logger.warn("Failed to read file '%s' (transient id %d) using user-provided mimetype %s", self.datas_fname or '<unknown>', self.id, self.type)
        # fallback on file extensions as mime types can be unreliable (e.g.
        # software setting incorrect mime types, or non-installed software
        # leading to browser not sending mime types)
        if self.datas_fname:
            p, ext = os.path.splitext(self.datas_fname)
            if ext in EXTENSIONS:
                try:
                    return getattr(self, '_read_' + ext[1:])(options, datas)
                except Exception:
                    _logger.warn("Failed to read file '%s' (transient id %s) using file extension", self.datas_fname, self.id)
        if req:
            raise ImportError(_("Unable to load \"{extension}\" file: requires Python module \"{modname}\"").format(extension=file_extension, modname=req))
        raise ValueError(_("Unsupported file format \"{}\", import only supports CSV, ODS, XLS and XLSX").format(self.type))

    @api.multi
    def _read_xls(self, options, datas):
        """ Read file content, using xlrd lib """
        book = xlrd.open_workbook(file_contents=datas)
        return self._read_xls_book(book)

    def _read_xls_book(self, book):
        sheet = book.sheet_by_index(0)
        # emulate Sheet.get_rows for pre-0.9.4
        for row in pycompat.imap(sheet.row, range(sheet.nrows)):
            values = []
            for cell in row:
                if cell.ctype is xlrd.XL_CELL_NUMBER:
                    is_float = cell.value % 1 != 0.0
                    values.append(
                        pycompat.text_type(cell.value)
                        if is_float
                        else pycompat.text_type(int(cell.value))
                    )
                elif cell.ctype is xlrd.XL_CELL_DATE:
                    is_datetime = cell.value % 1 != 0.0
                    # emulate xldate_as_datetime for pre-0.9.3
                    dt = datetime.datetime(*xlrd.xldate.xldate_as_tuple(cell.value, book.datemode))
                    values.append(
                        dt.strftime(DEFAULT_SERVER_DATETIME_FORMAT)
                        if is_datetime
                        else dt.strftime(DEFAULT_SERVER_DATE_FORMAT)
                    )
                elif cell.ctype is xlrd.XL_CELL_BOOLEAN:
                    values.append(u'True' if cell.value else u'False')
                elif cell.ctype is xlrd.XL_CELL_ERROR:
                    raise ValueError(
                        _("Error cell found while reading XLS/XLSX file: %s") %
                        xlrd.error_text_from_code.get(
                            cell.value, "unknown error code %s" % cell.value)
                    )
                else:
                    values.append(cell.value)
            if any(x for x in values if x.strip()):
                yield values

    # use the same method for xlsx and xls files
    _read_xlsx = _read_xls

    @api.multi
    def _read_ods(self, options, datas):
        """ Read file content using ODSReader custom lib """
        doc = odf_ods_reader.ODSReader(file=io.BytesIO(datas))
        return (
            row
            for row in doc.getFirstSheet()
            if any(x for x in row if x.strip())
        )

    @api.multi
    def _read_csv(self, options, datas):
        """ Returns a CSV-parsed iterator of all non-empty lines in the file
            :throws csv.Error: if an error is detected during CSV parsing
        """
        csv_data = datas
        if not csv_data:
            return iter([])
        encoding = options.get('encoding')
        if not encoding:
            encoding = options['encoding'] = chardet.detect(csv_data)['encoding'].lower()
            # some versions of chardet (e.g. 2.3.0 but not 3.x) will return
            # utf-(16|32)(le|be), which for python means "ignore / don't strip
            # BOM". We don't want that, so rectify the encoding to non-marked
            # IFF the guessed encoding is LE/BE and csv_data starts with a BOM
            bom = BOM_MAP.get(encoding)
            if bom and csv_data.startswith(bom):
                encoding = options['encoding'] = encoding[:-2]
        if encoding != 'utf-8':
            csv_data = csv_data.decode(encoding).encode('utf-8')

        separator = options.get('separator')
        if not separator:
            # default for unspecified separator so user gets a message about
            # having to specify it
            separator = ','
            for candidate in (',', ';', '\t', ' ', '|', unicodedata.lookup('unit separator')):
                # pass through the CSV and check if all rows are the same
                # length & at least 2-wide assume it's the correct one
                it = pycompat.csv_reader(io.BytesIO(csv_data), quotechar=options['quoting'], delimiter=candidate)
                w = None
                for row in it:
                    width = len(row)
                    if w is None:
                        w = width
                    if width == 1 or width != w:
                        break # next candidate
                else: # nobreak
                    separator = options['separator'] = candidate
                    break
        csv_iterator = pycompat.csv_reader(
            io.BytesIO(csv_data),
            quotechar=options['quoting'],
            delimiter=separator)
        return (
            row for row in csv_iterator
            if any(x for x in row if x.strip())
        )