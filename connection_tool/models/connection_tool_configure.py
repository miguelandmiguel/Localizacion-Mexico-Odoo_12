# -*- coding: utf-8 -*-

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

from dateutil.relativedelta import relativedelta
import logging
import time


from odoo import api, fields, models
from odoo.exceptions import AccessError, UserError
from odoo.tools.translate import _
from odoo.tools.mimetypes import guess_mimetype
from odoo.tools.safe_eval import safe_eval
from odoo.tools import config, DEFAULT_SERVER_DATE_FORMAT, DEFAULT_SERVER_DATETIME_FORMAT, pycompat

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
OPTIONS = {'headers': True, 'quoting': '"', 'separator': ',', 'encoding': 'utf-8'}
FIELD_TYPES = [(key, key) for key in sorted(fields.Field.by_type)]



class Configure(models.Model):
    _name = 'connection_tool.configure'
    _inherit = ['mail.thread']
    _description = "Import Files Configure"
    _order = 'name'

    # model_ids = fields.Many2many('ir.model', 'import_model_rel','import_id','model_id','Working Models')

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
    recurring_next_date = fields.Datetime('Date of Next Process')
    recurring_interval = fields.Integer('Repeat Every', help="Repeat every (Days/Week/Month/Year)")
    recurring_rule_type = fields.Selection([
        ('minutely', 'Minute(s)'),
        ('hourly', 'Hour(s)'),
        ('daily', 'Day(s)'),
        ('weekly', 'Week(s)'),
        ('monthly', 'Month(s)'),
        ('yearly', 'Year(s)'),
    ], string='Recurrency', help="Import automatically repeat at specified interval")


    # No hay
    register_to_process = fields.Integer('Register to Process', default=1)


    
    quoting = fields.Char('Quoting', size=8, default="\"")
    separator = fields.Char('Separator', size=8, default="|")
    with_header = fields.Boolean(string='With Header?', default=1)
    datas_fname = fields.Char('Filename')
    datas_file = fields.Binary('File', help="File to check and/or import, raw binary (not base64)")
    headers = fields.Html('Headers')
    type = fields.Selection(IMPORT_TYPE, 'Type', default='csv', index=True, change_default=True, track_visibility='always')

    macro_ids = fields.One2many('connection_tool.macro', 'import_id', 'Macro')
    macro_file = fields.Binary('Macro File (.csv Format)')


    ref_ir_act_window = fields.Many2one('ir.actions.act_window', 'Sidebar Action', readonly=True,
             help="Sidebar action to make this template available on records of the related document model")
    ref_ir_value = fields.Many2one('ir.values', 'Sidebar Button', readonly=True, help="Sidebar button to open the sidebar action")
    ref_ir_menu = fields.Many2one('ir.ui.menu', 'Leftbar Menu', readonly=True, help="Leftbar menu to open the leftbar menu action")
    ref_menu_ir_act_window = fields.Many2one('ir.actions.act_window', 'Leftbar Menu Action', readonly=True,
             help="This is the action linked to leftbar menu.")


    secondary_ids = fields.Many2many('connection_tool.configure', 'import_secondary_rel','import_id','secondary_id','Import secondary configurations')
    datas_fname_object_copy = fields.Char('Filename')
    object_copy_data_file = fields.Binary('Object File (.txt Format)')
    string = fields.Text('String in Macro')
    string_macro = fields.Char('String in Macro', size=128)

    table = fields.Char('Table', readonly=True)
    message_instruction = fields.Html('Instructions for Use')
    message_prerequisites = fields.Html('prerequisites')

    output_type = fields.Selection(OUTPUT_TYPE, string='File Type', help="Output file format")
    output_destination = fields.Selection(OUTPUT_DESTINATION, string='Destination', help="Output file destination")
    export_file = fields.Binary(string='Export File', readonly=True)
    export_filename = fields.Char(string='Export CSV Filename', size=128)
    export_file_encoding = fields.Selection([
            ('utf-8', 'UTF-8'),
            ('iso-8859-1', 'iso-8859-1 (ANSI)'),
        ], string='Export File Encodig', help="Export File Encodig")

    company_id = fields.Many2one('res.company', string='Company', change_default=True,
        required=True, readonly=True, default=lambda self: self.env['res.company']._company_default_get('connection_tool.configure'))


    @api.onchange('recurring_import')
    def onchange_recurring_import(self):
        if self.recurring_import:
            date = fields.Datetime.now()
            self.recurring_next_date = '%s'%(date)

    @api.multi
    def recurring_run_import(self):
        self.ensure_one()
        return self._recurring_connection_tool(automatic=False)

    def _cron_connection_tool(self):
        current_date =  time.strftime('%Y-%m-%d %H:%M:%S')
        imprt_ids = self.sudo().search([('recurring_next_date','<=', current_date), ('recurring_import','=', True)])
        _logger.info("CRON imprt_ids %s %s "%(current_date, imprt_ids) )
        for imprt_id in imprt_ids:
            imprt_id.sudo()._recurring_connection_tool(automatic=True)
        return True

    @api.multi
    def _recurring_connection_tool(self, automatic=False):
        self.ensure_one()
        ctx = self._context
        current_date =  time.strftime('%Y-%m-%d %H:%M:%S')
        _logger.info("CRON Recurrent Date %s"%current_date )
        try:
            self.button_import(automatic=automatic) # Run Import
            next_date = datetime.datetime.strptime(current_date, "%Y-%m-%d %H:%M:%S")
            interval = self.recurring_interval
            if self.recurring_rule_type == 'minutely':
                new_date = next_date+relativedelta(minutes=+interval)
            elif self.recurring_rule_type == 'hourly':
                new_date = next_date+relativedelta(hours=+interval)
            elif self.recurring_rule_type == 'daily':
                new_date = next_date+relativedelta(days=+interval)
            elif self.recurring_rule_type == 'weekly':
                new_date = next_date+relativedelta(weeks=+interval)
            elif self.recurring_rule_type == 'monthly':
                new_date = next_date+relativedelta(months=+interval)
            else:
                new_date = next_date+relativedelta(years=+interval)
            self.write({
                'recurring_next_date': new_date.strftime('%Y-%m-%d %H:%M:%S')
            })

        except Exception as e:
            if automatic:
                self._cr.rollback()
                _logger.exception('%s, in recurring import configuration %s'%(e, self.name))
                _logger.debug("Sending recurring import configuration error notification to uid %s", self._uid)
            else:
                raise

        _logger.info("CRON: Termina proceso")
        return True

    @api.onchange('model_id')
    def onchange_model_id(self):
        if self.model_id:
            # model_ids = self.get_inherit_modules()
            # self.model_ids = model_ids
            self.name = self.model_id.name

    @api.onchange('datas_file', 'quoting', 'separator')
    def onchange_datas_file(self):
        if not self.datas_file:
            self.headers=""
            return
        options = {}
        if self.type == 'csv':
            if not self.quoting and self.separator:
                raise UserError(_("Set Quoting and Separator fields before load CSV File."))
            options = OPTIONS
            options['quoting'] = self.quoting or OPTIONS['quoting']
            options['separator'] = self.separator or OPTIONS['separator']
            
        rows_to_import = self._read_file(options)
        if self.with_header:
            self.headers = next(rows_to_import, None)


    @api.multi
    def action_raise_message(self, msg_log=False, automatic=False):
        self.ensure_one()
        context = dict(self._context) or {}
        if not automatic:
            if len(msg_log) != 0:
                raise UserError(msg_log)
        else:
            _logger.info("Mensaje de Validacion %s "%msg_log )
        return True

    @api.multi
    def _get_values(self, data_val_model):
        self.ensure_one()
        #   List of Registers ID
        keys = {}
        import_fields = data_val_model and data_val_model[0] and list(data_val_model[0].keys())
        values = []
        for data in data_val_model:
            data_tmp = []
            for field in import_fields:
                data_tmp.append( data[field] )
            values.append(data_tmp)
        return keys, import_fields, values 

    @api.multi
    def _import_ftp_pre(self, flag_imp=False, automatic=False):
        self.ensure_one()
        message = ""
        _logger.info("CRON: ftp_pre")
        try:
            if self.source_type == 'ftp':
                imprt = self.source_connector_id.with_context(imprt=self)
                imprt._get_ftp_dirfile(filename=self.source_ftp_refilename, automatic=automatic)
                # _check_filename_exist
                if self.source_ftp_write_control:
                    if imprt._get_ftp_check_filename_exist(filename=self.source_ftp_write_control, automatic=automatic):
                        return ''
                #   Check if import data file exist
                if not imprt._get_ftp_check_filename_exist(filename=self.source_ftp_filename, automatic=automatic):
                    return ''
                # First: create control file if if Read Control File Name
                o = StringIO()
                self.source_ftp_write_control and imprt._push_to_ftp(self.source_ftp_write_control, o, automatic=automatic)
                o.close()
                # Second: read file from ftp site
                remote_file = imprt._read_ftp_filename(self.source_ftp_filename, automatic=automatic)
                self.datas_file =  base64.b64encode(remote_file)
                _logger.info("CRON: ftp_pre_fil64")
        except ValueError as e:
            message = str(e)
        except Exception as e:
            message = str(e)
        if message:
            self.datas_file = b''
            message = message.replace("(u'", "").replace("', '')", "").replace("('", "").replace("', None)", "")
            self.action_raise_message(msg_log=message, automatic=automatic)
        return True


    @api.multi
    def _import_ftp_post(self, flag_imp=False, automatic=False):    
        self.ensure_one()
        message = ""
        try:
            if self.source_type == 'ftp':
                imprt = self.source_connector_id.with_context(imprt=self)
                if imprt._get_ftp_check_filename_exist(filename=self.source_ftp_write_control, automatic=automatic):
                    imprt._delete_ftp_filename(self.source_ftp_write_control, automatic=automatic)
        except ValueError as e:
            message = str(e)
        except Exception as e:
            message = str(e)
        if message:
            message = message.replace("(u'", "").replace("', '')", "").replace("('", "").replace("', None)", "")
            self.action_raise_message(msg_log=message, automatic=automatic)
        return True


    @api.multi
    def get_source_python_script(self, import_data, import_fields, flag_imp=False, automatic=False):
        self.ensure_one()
        localdict = {
            'this':self, 
            're': re,
            'time': time,
            'datetime': datetime,
            'context': dict(self._context),
            '_logger': _logger,
            'UserError': UserError,
            'import_data': import_data,
            'import_fields': import_fields
        }
        if self.source_python_script:
            print("self.source_python_script", self.source_python_script)
            try:
                safe_eval(self.source_python_script, localdict, mode='exec', nocopy=True)
            except Exception as e:
                raise UserError(_('%s in macro')%(e))
        result = localdict.get('result',False)
        if result:
            header = result.get('header') or []
            body = result.get('body') or []
            for values in body:
                if self.output_destination == 'this_database':
                    base_model = self.env[self.model_id.model].with_context(import_file=True, name_create_enabled_fields={})
                    b = body[values].get('lines') or []
                    import_result = base_model.load(header, b)
                    _logger.info("import_result %s"%values)
                    self.raise_message(import_result, flag_imp=flag_imp, automatic=automatic)  


        return True


    @api.multi
    def _import(self, flag_imp=False, automatic=False):
        self.ensure_one()
        self._cr.execute('SAVEPOINT import')
        
        context = self._context
        if not self.macro_ids:
            raise UserError(_('No macro lines defined. '))
        self.datas_file = b''

        _logger.info("CRON _import")
        # Busca archivo ftp
        if self.source_connector_id:
            res = self._import_ftp_pre(flag_imp=flag_imp, automatic=automatic)
            if not res:
                return False
        if self.source_python_script:
            options = {
                'headers': self.with_header
            }
            if self.type == 'csv':
                if not self.quoting and self.separator:
                    raise UserError(_("Set Quoting and Separator fields before load CSV File."))
                options = OPTIONS
                options['quoting'] = self.quoting or OPTIONS['quoting']
                options['separator'] = self.separator or OPTIONS['separator']
            import_data, import_fields = self._convert_import_data(options)
            _logger.info("CRON: import_data %s "%(import_data))
            # import_data = self._parse_import_data(import_data, import_fields, options)
            lendatas = len(import_data)
            res = self.get_source_python_script(import_data, import_fields, flag_imp=flag_imp, automatic=automatic)

            res = self._import_ftp_post(flag_imp=False, automatic=automatic)
            if res and self.source_type == 'ftp':
                imprt = self.source_connector_id.with_context(imprt=self)
                imprt._move_ftp_filename(self.source_ftp_write_control, automatic=automatic)
            return {}

        data = {'val':{}}
        meta = {
            'global':{'LINE_IDS':[], 'LINE_IDS_INDEX':0, 'global_debit': 0.0, 'global_credit': 0.0, 'len_datas': 0},
            'model_id':False,
            'model_list':[],
            'register_id':{},
            'first_index':False,
            'relative_index':0,
            'register_counter':{},
            'row_value':{},
            'val':{'register_id':False, 'register':False, 'parent_register_id':False, 'parent_register':False, 'parent_model':False, 'lines': []}
        }
        csv_data = []

        data, meta = self.process_macro(data, meta, automatic)
        if not data['val']:
            return {}
        for model in meta['model_list']:
            if not data['val'].get(model,False) or not data['val'][model].keys():
                continue
            keys, import_fields, values = self._get_values(meta['val']['lines'])
            if flag_imp:
                if self.output_destination == 'this_database':
                    base_model = self.env[model].with_context(import_file=True, name_create_enabled_fields={})
                    import_result = base_model.load(import_fields, values)
                    _logger.info("import_result %s"%import_result)
                    self.raise_message(import_result, flag_imp=flag_imp, automatic=automatic)

            if self.output_type: 
                if self.output_type in ('xlsx'):
                    file_data = BytesIO()
                    workbook = xlsxwriter.Workbook(file_data, {'in_memory': True})
                    worksheet = workbook.add_worksheet( self.model_id.name )
                    worksheet.write_row('A1', import_fields)
                    row = 2
                    for v in values:
                        worksheet.write_row('A%s'%row, v)
                        row += 1
                    workbook.close()
                    file_data.seek(0)
                    self.export_file = base64.b64encode(file_data.getvalue())

        res = self._import_ftp_post(flag_imp=False, automatic=automatic)
        if res and self.source_type == 'ftp':
            imprt = self.source_connector_id.with_context(imprt=self)
            imprt._move_ftp_filename(self.source_ftp_write_control, automatic=automatic)


    def raise_message(self, import_result, flag_imp=False, automatic=False):
        _logger.info(import_result)
        if import_result['messages']:
            messages = ''
            for msg in import_result['messages']:
                messages += '%s \n'%(str( msg.get('message') or '' )) 
            self._import_ftp_post(flag_imp=False, automatic=automatic)
            raise UserError(_('%s')%messages)
        return True


    def process_macro(self, data, meta, automatic=False):
        def cell(import_fields, import_data, macro, data, meta={}, automatic=False):
            val = row_value = row = table = db_field = False
            index = 0
            #if macro.row_type == 'relative' or macro.import_id.type in ('csv','ftp'):
            if macro.row_type == 'relative' or macro.import_id.type != 'file':
                index = meta['relative_index']
            row, col = get_row_col(macro.row, macro.col, index)
            if not self.with_header:
                row -= 1
            if index >= len(import_data):
                return '/*EOF*/', meta                                      # CHECK END OF FILE
            for i, row_value in enumerate(import_data):# get row_value
                if i >= index :
                    break
            val = row_value[col]
            return self.run_python(macro, meta, val, row_value=meta['row_value'], row=(row or index or meta['relative_index']), row_data=row_value, automatic=automatic)


        self.ensure_one()
        context = self._context

        options = {
            'headers': self.with_header
        }
        if self.type == 'csv':
            if not self.quoting and self.separator:
                raise UserError(_("Set Quoting and Separator fields before load CSV File."))
            options = OPTIONS
            options['quoting'] = self.quoting or OPTIONS['quoting']
            options['separator'] = self.separator or OPTIONS['separator']
        import_data, import_fields = self._convert_import_data(options)
        # import_data = self._parse_import_data(import_data, import_fields, options)
        lendatas = len(import_data)

        meta['global']['len_datas'] = len(import_data)

        meta['relative_index'] = meta['first_index'] = sheet_id = 0
        # Define initial metadata Models
        meta['model_id'] = self.model_id.model or self.name
        if not meta['model_id'] in meta['model_list']:
            meta['model_list'].append(meta['model_id'])

        # Process Registry Macros
        type_registry = ('register_id','register','line','next_index','jump','check')
        macro_register = [(x.sequence, x) for x in self.macro_ids if x.type in type_registry and not x.disable]
        i = len(macro_register)
        
        model = meta['model_id']
        while i >= 1:
            if model and not data['val'].get(model,False):
                data['val'][model] = {}
            macro = macro_register[-i][1]
            # Read cell or registry value
            val, meta = cell(import_fields, import_data, macro, data, meta, automatic)
            if val == '/*EOF*/':
                break

            if macro.type == 'register_id':
                if model == meta['model_id']:
                    processed = len(data['val'][meta['model_id']].keys())
                if (self.register_to_process > 0) and ((self.register_to_process) <= processed):
                    break
                if data['val'][model].get(val,False):
                    dup_indx = 1
                    while data['val'][model].get(val+'-'+str(dup_indx),False):
                        dup_indx += 1
                    val = val+'-'+str(dup_indx)
                data['val'][model][val] = {'id':val}
                meta['register_id'][model] = val        # Register_id
                meta['val']['register_id'] = val
                meta['val']['register'] = val and data['val'][model][meta['val']['register_id']]

            # Process Macro Type ** Register **
            elif macro.type == 'register':
                subfix = ''
                if macro.field_id and macro.field_id.ttype in ('many2one','many2many','one2many'):
                    return_type = macro.return_type
                    subfix = (return_type == 'db' and '/.id') or (return_type == 'external' and '/id') or (return_type == 'name' and '')
                    val = (macro.return_type == 'db' and str(val)) or val
                key = macro.field_name and (macro.field_name + subfix) or 'column_%s'%macro.sequence
                if not meta['register_id'].get(model,False):
                    if automatic:
                        self._cr.rollback()
                        _logger.exception(_('Define "Register ID" before macro "%s", sequence = %s .')%(macro.name, macro.sequence))
                    else:
                        raise UserError(_('Define "Register ID" before macro "%s", sequence = %s .')%(macro.name, macro.sequence))
                reg_id = meta['register_id'][model]
                if val == '/*NOT PROCESS*/':
                    val = data['val'][model][reg_id].get(key,False)
                data['val'][model][reg_id].update({key:val})
                meta['val']['register'].update({key:val})

            # Process Macro Type ** Line Object **
            elif macro.type == 'line':
                if macro.field_id and macro.field_id.ttype != 'one2many':
                    if automatic:
                        self._cr.rollback()
                        _logger.exception(_('Field shuld be one2many not %s in Macro %s.')%(macro.field_id.ttype,macro.name))
                    else:
                        raise UserError(_('Field shuld be one2many not %s in Macro %s.')%(macro.field_id.ttype,macro.name))
                meta['val']['parent_register_id'] = meta['val']['register_id']
                meta['val']['parent_model'] = meta['model_id']
                meta['val']['parent_register'] = meta['val']['register']
                meta['model_id'] = macro.field_id and macro.field_id.relation or imprt.name
                if macro.field_id and not macro.field_id.relation in meta['model_list']:
                    meta['model_list'].append(macro.field_id.relation)

            elif macro.type == 'next_index': 
                # IF iteraiting in object lines

                reg_id = meta['register_id'][model]
                line_dict = data['val'][model][reg_id]
                for ldict in line_dict:
                    if line_dict[ldict].startswith("vacio"):
                        line_dict[ldict] = ""

                if self.model_id.model == 'account.move':
                    if line_dict.get("line_ids/credit", "0.0") != "0.0" and line_dict.get("line_ids/debit", "0.0") != "0.0":
                        line_dict_tmp = line_dict.copy()
                        line_dict_tmp["line_ids/credit"] = "0.0"
                        line_dict["line_ids/debit"] = "0.0"
                        meta['val']['lines'].append(line_dict_tmp)


                meta['val']['lines'].append(line_dict)
                

                if meta['global']['LINE_IDS']:
                    meta['global']['LINE_IDS_INDEX'] -= 1
                    if meta['global']['LINE_IDS_INDEX'] == 0:
                        meta['relative_index'] += 1
                        meta['model_id'] = meta['val']['parent_model']
                        meta['global']['/*END OF LINES*/'] = True
                        meta['global']['LINE_IDS'] = []
                        meta['global']['LINE_IDS_INDEX'] = 0
                # IF val == integer
                elif isinstance(val, int):
                    meta['relative_index'] += val
                # IF val == '/*END OF LINES*/, integer'
                elif isinstance(val, (str)) and val.split(',')[0] == '/*END OF LINES*/':
                    meta['global']['/*END OF LINES*/'] = True
                    next_index = int(val.split(',')[1])
                    meta['relative_index'] += next_index
                    meta['model_id'] = meta['val']['parent_model']
                else:
                    if automatic:
                        self._cr.rollback()
                        _logger.exception(_('Can process Macro sequence %s with value "%s".')%(macro.sequence, val))
                    else:
                        raise UserError(_('Can process Macro sequence %s with value "%s".')%(macro.sequence, val))

            # Process Macro Type ** Check **
            elif macro.type == 'check':
                if isinstance(val, str):
                    res = val.split(',')
                    if res[0] == 'OK':
                        if len(res) > 1:
                            ix = len(macro_register)
                            for m in macro_register:
                                if val == m[0]:
                                    i = ix 
                                    break
                                ix -= 1
                        pass
                    elif res[0] == 'PASS':
                        pass
                    elif res[0] == 'JUMP' and len(res) == 3:
                        meta['global'].update(eval(res[1]))
                        meta['relative_index'] += int(res[2])
                    elif res[0] == 'JUMP_AND_CHECK_AGAIN' and len(res) == 3:
                        meta['global'].update(eval(res[1]))
                        meta['relative_index'] += int(res[2])
                        i += 1
                    elif res[0] == 'NEXT_ROW' and len(res) == 2:
                        meta['global'].update(eval(res[1]))
                        meta['relative_index'] += 1
                    elif res[0] == 'PREVIUS_ROW' and len(res) == 2:
                        meta['global'].update(eval(res[1]))
                        meta['relative_index'] -= 1
                    elif res[0] == 'NEXT_AND_CHECK_AGAIN':
                        meta['relative_index'] += 1
                        i += 1
                    elif res[0] == 'PREVIUS_AND_CHECK_AGAIN':
                        meta['relative_index'] -= 1
                        i += 1
                    else:
                        if automatic:
                            self._cr.rollback()
                            _logger.exception(_('Can not process Check in Macro sequence %s with value "%s" in row %s, valid values are "OK[,macro]", "PASS", "NEXT_ROW,{key:value}", "PREVIUS_ROW,{key:value}", "NEXT_AND_CHECK_AGAIN", "PREVIUS_AND_CHECK_AGAIN".')%(macro.sequence, val, meta['relative_index']))
                        else:
                            raise UserError(_('Can not process Check in Macro sequence %s with value "%s" in row %s, valid values are "OK[,macro]", "PASS", "NEXT_ROW,{key:value}", "PREVIUS_ROW,{key:value}", "NEXT_AND_CHECK_AGAIN", "PREVIUS_AND_CHECK_AGAIN".')%(macro.sequence, val, meta['relative_index']))

            # Process Macro Type ** Jump to Macro **
            elif macro.type == 'jump':
                meta['global']['/*END OF LINES*/'] = False
                if isinstance(val, int):
                    ix = len(macro_register)
                    for m in macro_register:
                        if val == m[0]:
                            i = ix
                            break
                        ix -= 1
                    continue
                else:
                    if automatic:
                        self._cr.rollback()
                        _logger.exception(_('Result must be integer in macro sequence %s, the actual result value is %s, row = %s ')%(macro.sequence, val, meta['relative_index']))
                    else:
                        raise UserError(_('Result must be integer in macro sequence %s, the actual result value is %s, row = %s ')%(macro.sequence, val, meta['relative_index']))
            i -= 1
        return data, meta



    @api.model
    def _convert_import_data(self, options):
        import_fields = [x.field_id.name for x in self.macro_ids if x.type in ('register') and not x.disable]
        rows_to_import = self._read_file(options)
        data = list(itertools.islice(rows_to_import, 0, None))
        return data, import_fields



    @api.multi
    def _parse_import_data(self, data, import_fields, options):
        """ Lauch first call to _parse_import_data_recursive with an
        empty prefix. _parse_import_data_recursive will be run
        recursively for each relational field.
        """
        return self._parse_import_data_recursive(self.model_id.model, '', data, import_fields, options)


    @api.multi
    def _parse_import_data_recursive(self, model, prefix, data, import_fields, options):
        # Get fields of type date/datetime
        all_fields = self.env[model].fields_get()
        for name, field in all_fields.items():
            name = prefix + name
            if field['type'] in ('date', 'datetime') and name in import_fields:
                index = import_fields.index(name)
                self._parse_date_from_data(data, index, name, field['type'], options)
            # Check if the field is in import_field and is a relational (followed by /)
            # Also verify that the field name exactly match the import_field at the correct level.
            elif any(name + '/' in import_field and name == import_field.split('/')[prefix.count('/')] for import_field in import_fields):
                # Recursive call with the relational as new model and add the field name to the prefix
                self._parse_import_data_recursive(field['relation'], name + '/', data, import_fields, options)
            elif field['type'] in ('float', 'monetary') and name in import_fields:
                # Parse float, sometimes float values from file have currency symbol or () to denote a negative value
                # We should be able to manage both case
                index = import_fields.index(name)
                self._parse_float_from_data(data, index, name, options)
            elif field['type'] == 'binary' and field.get('attachment') and any(f in name for f in IMAGE_FIELDS) and name in import_fields:
                index = import_fields.index(name)

                with requests.Session() as session:
                    session.stream = True

                    for num, line in enumerate(data):
                        if re.match(config.get("import_image_regex", DEFAULT_IMAGE_REGEX), line[index]):
                            if not self.env.user._can_import_remote_urls():
                                raise AccessError(_("You can not import images via URL, check with your administrator or support for the reason."))

                            line[index] = self._import_image_by_url(line[index], session, name, num)

        return data

    def _parse_date_from_data(self, data, index, name, field_type, options):
        dt = datetime.datetime
        fmt = fields.Date.to_string if field_type == 'date' else fields.Datetime.to_string
        d_fmt = options.get('date_format')
        dt_fmt = options.get('datetime_format')
        for num, line in enumerate(data):
            if not line[index]:
                continue

            v = line[index].strip()
            try:
                # first try parsing as a datetime if it's one
                if dt_fmt and field_type == 'datetime':
                    try:
                        line[index] = fmt(dt.strptime(v, dt_fmt))
                        continue
                    except ValueError:
                        pass
                # otherwise try parsing as a date whether it's a date
                # or datetime
                line[index] = fmt(dt.strptime(v, d_fmt))
            except ValueError as e:
                raise ValueError(_("Column %s contains incorrect values. Error in line %d: %s") % (name, num + 1, e))
            except Exception as e:
                raise ValueError(_("Error Parsing Date [%s:L%d]: %s") % (name, num + 1, e))

    def _import_image_by_url(self, url, session, field, line_number):
        """ Imports an image by URL

        :param str url: the original field value
        :param requests.Session session:
        :param str field: name of the field (for logging/debugging)
        :param int line_number: 0-indexed line number within the imported file (for logging/debugging)
        :return: the replacement value
        :rtype: bytes
        """
        maxsize = int(config.get("import_image_maxbytes", DEFAULT_IMAGE_MAXBYTES))
        try:
            response = session.get(url, timeout=int(config.get("import_image_timeout", DEFAULT_IMAGE_TIMEOUT)))
            response.raise_for_status()

            if response.headers.get('Content-Length') and int(response.headers['Content-Length']) > maxsize:
                raise ValueError(_("File size exceeds configured maximum (%s bytes)") % maxsize)

            content = bytearray()
            for chunk in response.iter_content(DEFAULT_IMAGE_CHUNK_SIZE):
                content += chunk
                if len(content) > maxsize:
                    raise ValueError(_("File size exceeds configured maximum (%s bytes)") % maxsize)

            image = Image.open(io.BytesIO(content))
            w, h = image.size
            if w * h > 42e6:  # Nokia Lumia 1020 photo resolution
                raise ValueError(
                    u"Image size excessive, imported images must be smaller "
                    u"than 42 million pixel")

            return base64.b64encode(content)
        except Exception as e:
            raise ValueError(_("Could not retrieve URL: %(url)s [%(field_name)s: L%(line_number)d]: %(error)s") % {
                'url': url,
                'field_name': field,
                'line_number': line_number + 1,
                'error': e
            })

    @api.model
    def _remove_currency_symbol(self, value):
        value = value.strip()
        negative = False
        # Careful that some countries use () for negative so replace it by - sign
        if value.startswith('(') and value.endswith(')'):
            value = value[1:-1]
            negative = True
        float_regex = re.compile(r'([+-]?[0-9.,]+)')
        split_value = [g for g in float_regex.split(value) if g]
        if len(split_value) > 2:
            # This is probably not a float
            return False
        if len(split_value) == 1:
            if float_regex.search(split_value[0]) is not None:
                return split_value[0] if not negative else '-' + split_value[0]
            return False
        else:
            # String has been split in 2, locate which index contains the float and which does not
            currency_index = 0
            if float_regex.search(split_value[0]) is not None:
                currency_index = 1
            # Check that currency exists
            currency = self.env['res.currency'].search([('symbol', '=', split_value[currency_index].strip())])
            if len(currency):
                return split_value[(currency_index + 1) % 2] if not negative else '-' + split_value[(currency_index + 1) % 2]
            # Otherwise it is not a float with a currency symbol
            return False

    @api.model
    def _parse_float_from_data(self, data, index, name, options):
        for line in data:
            line[index] = line[index].strip()
            if not line[index]:
                continue
            thousand_separator, decimal_separator = self._infer_separators(line[index], options)
            line[index] = line[index].replace(thousand_separator, '').replace(decimal_separator, '.')
            old_value = line[index]
            line[index] = self._remove_currency_symbol(line[index])
            if line[index] is False:
                raise ValueError(_("Column %s contains incorrect values (value: %s)" % (name, old_value)))

    def _infer_separators(self, value, options):
        """ Try to infer the shape of the separators: if there are two
        different "non-numberic" characters in the number, the
        former/duplicated one would be grouping ("thousands" separator) and
        the latter would be the decimal separator. The decimal separator
        should furthermore be unique.
        """
        # can't use \p{Sc} using re so handroll it
        non_number = [
            # any character
            c for c in value
            # which is not a numeric decoration (() is used for negative
            # by accountants)
            if c not in '()-+'
            # which is not a digit or a currency symbol
            if unicodedata.category(c) not in ('Nd', 'Sc')
        ]

        counts = collections.Counter(non_number)
        # if we have two non-numbers *and* the last one has a count of 1,
        # we probably have grouping & decimal separators
        if len(counts) == 2 and counts[non_number[-1]] == 1:
            return [character for character, _count in counts.most_common()]

        # otherwise get whatever's in the options, or fallback to a default
        thousand_separator = options.get('float_thousand_separator', ' ')
        decimal_separator = options.get('float_decimal_separator', '.')
        return thousand_separator, decimal_separator



    @api.multi
    def run_python(self, macro, meta, value=False, row_value=False, row=False, row_data=False, automatic=False):
        self.ensure_one()
        context = self._context
        try:
            import isoweek
        except:
            if automatic:
                self._cr.rollback()
                _logger.exception(_('Install library isoweek: sudo pip install isoweek'))
            else:
                raise UserError(_('Install library isoweek. https://pypi.python.org/packages/source/i/isoweek/isoweek-1.3.0.tar.gz.'))
        sequence = macro.sequence
        python_code = macro.python
        Model = self.env['ir.model']
        # model_ids = Model.search([('model','=',meta['model_id'])], limit=1)
        # model_id = model_ids and model_ids.id
        imprt = self
        localdict = {
            'this':self, 
            'value':value, 
            'row_value':row_value,
            'row_data': row_data,
            'relative_index':meta['relative_index'] + 1, 
            'keys':meta.keys(),
            'data_global':meta['global'],
            'model': meta['model_id'],
            'parent_model': meta['val'].get('parent_model',False),
            'model_list': meta['model_list'],
            'register_id': meta['val']['register_id'],
            'parent_register_id': meta['val']['parent_register_id'], 
            'meta_val': meta['val'],
            'register': meta['val']['register'],
            'parent_register': meta['val']['parent_register'], 
            'end_of_lines': meta['global'].get('/*END OF LINES*/',False),
            'remove_accents': remove_accents, 
            're': re,
            'time': time,
            'datetime': datetime,
            'ws':False,  #TODO add a web service 
            'context':context,
            '_logger': _logger,
            'UserError': UserError
        }
        if python_code:
            try:
                safe_eval(python_code, localdict, mode='exec', nocopy=True)
            except Exception as e:
                raise UserError(_('%s in macro sequence %s, value = [%s], Row %s.')%(e, sequence, value or '', row or ''))
        result = localdict.get('result',False)
        if (macro.type == 'register' and imprt.output_type in ['text', 'text_columns']):
            if result:
                result = result[0:macro.lenght]
            if macro.result_required and len(result) == 0:
                raise UserError(_('Error in macro sequence %s, value = [%s], Row %s. \n El campo "%s" es Requerido')%(sequence, value or '', row or '', macro.name))
            field_value = result
            field_length = macro.lenght
            field_zero = macro.result_zero
            field_type = macro.result_type
            field_format_date = macro.result_format_date
            field_format_number = macro.result_format_number
            if field_type == 'date':
                field_value = field_value or str(datetime.date.today())
                if field_format_date == 'ddmmyyyy':
                    field_value = time.strftime('%d%m%Y', time.strptime(field_value,'%Y-%m-%d'))
                if field_format_date == 'mmddyyyy':
                    field_value = time.strftime('%m%d%Y', time.strptime(field_value,'%Y-%m-%d'))
                if field_format_date == 'yyyymmdd':
                    field_value = time.strftime('%Y%m%d', time.strptime(field_value,'%Y-%m-%d'))
            if field_type == 'integer':
                if field_value:
                    try:
                        field_value = str(int(field_value))
                    except Exception as e:
                        raise UserError(_("The field '%s' must be numeric!") % (macro.name,))
            if field_type == 'float':
                if type(field_value).__name__ == 'float':
                    n = '1' + '0' * int(field_length)
                try:
                    field_value = str(int(float(field_value)*int(n)))
                except:
                    raise UserError( _("The field '%s' must be float!") % (macro.name,))
            length = field_value and len(field_value) or 0
            if field_zero == 'left' and length < field_length:                     #add 0 to the left
                result = '0'*(field_length - length) + (field_value or '')
            if field_zero == 'rigth' and length < field_length:                    #add 0 to the rigth
                result = (field_value or '') + '0'*(field_length - length)
            if field_zero == 'sleft' and length < field_length:                    #add ' ' (space) to the left
                result = ' '*(field_length - length) + (field_value or '')
            if field_zero == 'srigth' and length < field_length:                   #add ' ' (space) to the rigth
                result = (field_value or '') + ' '*(field_length - length)
            result = u"%s"%result
        return result, meta


    # 
    # Botones
    # 
    @api.multi
    def button_import(self, automatic=False):
        return self._import(flag_imp=True, automatic=automatic)

    @api.multi
    def button_test_import(self, automatic=False):
        return self._import(flag_imp=False, automatic=False)

    # Macros
    @api.multi
    def button_disable(self):
        for imprt in self:
            for macro in imprt.macro_ids:
                macro.write({'disable':True})
        return {}

    @api.multi
    def button_enable(self):
        for imprt in self:
            for macro in imprt.macro_ids:
                macro.write({'disable':False})
        return {}

    @api.multi
    def button_delete_macro(self): 
        for imprt in self:
            self.macro_ids.unlink()

    @api.multi
    def button_create_macro(self): 
        Macros = self.env['connection_tool.macro']
        for imprt in self:
            tmp = {}

            values, field_ids = [], []
            for idx, field in enumerate([1] + field_ids + [2,3]):
                field_int = type(field).__name__ == 'int' or False
                ttype = field_int and (field==1 and 'register_id' or field==2 and 'next_index' or field==3 and 'jump') or 'register'
                # model_ids = [x.id for x in imprt.model_ids]
                db_field, db_field_type = None, None # self.get_db_field(field, imprt, ttype)
                selection = False
                return_type = False
                if not field_int:
                    if field.ttype in ('many2many', 'one2many', 'many2one'):
                        return_type = 'external'
                    elif field.ttype == 'selection':
                        selection = tmp_fields.get( field.name ) and tmp_fields[field.name]['selection'] or []
                val = {
                    'name': not field_int and field.field_description or dict(TYPE_SELECTION)[ttype],
                    'field_id': not field_int and field.id,
                    'field_name': not field_int and field.name,
                    'field_type': not field_int and field.ttype,
                    'field_model': not field_int and field.model,
                    'selection': selection,
                    'return_type': return_type,
                    'table': imprt.table,
                    'parent_table': imprt.table,
                    'row': imprt.table,
                    'col': db_field,
                    'db_field': db_field,
                    'db_field_type': db_field_type,
                    'sequence': idx + 1,
                    'model_id': imprt.model_id.id,
                    # 'model_ids': [(6, False, model_ids)],
                    'type': ttype,
                    'import_type': imprt.type,
                    'row_type': 'relative',
                }
                values.append(val)
            imprt.write({'macro_ids': map(lambda x: (0,0,x), values)})
        return {}



    @api.multi
    def get_inherit_modules(self):
        if self.model_id:
            return self.model_id.ids
        return []

    @api.model
    def get_fields(self, model, depth=FIELDS_RECURSION_LIMIT):
        Model = self.env[model]
        importable_fields = [{
            'id': 'id',
            'name': 'id',
            'string': _("External ID"),
            'required': False,
            'fields': [],
            'type': 'id',
        }]
        if not depth:
            return importable_fields

        model_fields = Model.fields_get()
        blacklist = models.MAGIC_COLUMNS + [Model.CONCURRENCY_CHECK_FIELD]
        for name, field in model_fields.items():
            if name in blacklist:
                continue
            # an empty string means the field is deprecated, @deprecated must
            # be absent or False to mean not-deprecated
            if field.get('deprecated', False) is not False:
                continue
            if field.get('readonly'):
                states = field.get('states')
                if not states:
                    continue
                # states = {state: [(attr, value), (attr2, value2)], state2:...}
                if not any(attr == 'readonly' and value is False
                           for attr, value in itertools.chain.from_iterable(states.values())):
                    continue
            field_value = {
                'id': name,
                'name': name,
                'string': field['string'],
                # Y U NO ALWAYS HAS REQUIRED
                'required': bool(field.get('required')),
                'fields': [],
                'type': field['type'],
            }

            if field['type'] in ('many2many', 'many2one'):
                field_value['fields'] = [
                    dict(field_value, name='id', string=_("External ID"), type='id'),
                    dict(field_value, name='.id', string=_("Database ID"), type='id'),
                ]
            elif field['type'] == 'one2many':
                field_value['fields'] = self.get_fields(field['relation'], depth=depth-1)
                if self.user_has_groups('base.group_no_one'):
                    field_value['fields'].append({'id': '.id', 'name': '.id', 'string': _("Database ID"), 'required': False, 'fields': [], 'type': 'id'})
            elif field['type'] == 'selection':
                field_value['selection'] = field.get('selection') or []

            importable_fields.append(field_value)

        # TODO: cache on model?
        return importable_fields

    
    @api.multi
    def _read_file(self, options):
        """ Dispatch to specific method to read file content, according to its mimetype or file type
            :param options : dict of reading options (quoting, separator, ...)
        """
        self.ensure_one()
        # guess mimetype from file content
        mimetype = guess_mimetype(base64.b64decode(self.datas_file) or b'')
        (file_extension, handler, req) = FILE_TYPE_DICT.get(mimetype, (None, None, None))
        if handler:
            try:
                return getattr(self, '_read_' + file_extension)(options)
            except Exception:
                _logger.warn("Failed to read file '%s' (transient id %d) using guessed mimetype %s", self.datas_fname or '<unknown>', self.id, mimetype)
        # try reading with user-provided mimetype
        (file_extension, handler, req) = FILE_TYPE_DICT.get(self.type, (None, None, None))
        if handler:
            try:
                return getattr(self, '_read_' + file_extension)(options)
            except Exception:
                _logger.warn("Failed to read file '%s' (transient id %d) using user-provided mimetype %s", self.datas_fname or '<unknown>', self.id, self.type)
        # fallback on file extensions as mime types can be unreliable (e.g.
        # software setting incorrect mime types, or non-installed software
        # leading to browser not sending mime types)
        if self.datas_fname:
            p, ext = os.path.splitext(self.datas_fname)
            if ext in EXTENSIONS:
                try:
                    return getattr(self, '_read_' + ext[1:])(options)
                except Exception:
                    _logger.warn("Failed to read file '%s' (transient id %s) using file extension", self.datas_fname, self.id)
        if req:
            raise ImportError(_("Unable to load \"{extension}\" file: requires Python module \"{modname}\"").format(extension=file_extension, modname=req))
        raise ValueError(_("Unsupported file format \"{}\", import only supports CSV, ODS, XLS and XLSX").format(self.type))


    @api.multi
    def _read_xls(self, options):
        """ Read file content, using xlrd lib """
        book = xlrd.open_workbook(file_contents=base64.b64decode(self.datas_file) or b'')
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
    def _read_ods(self, options):
        """ Read file content using ODSReader custom lib """
        doc = odf_ods_reader.ODSReader(file=io.BytesIO(base64.b64decode(self.datas_file) or b''))
        return (
            row
            for row in doc.getFirstSheet()
            if any(x for x in row if x.strip())
        )

    @api.multi
    def _read_csv(self, options):
        """ Returns a CSV-parsed iterator of all non-empty lines in the file
            :throws csv.Error: if an error is detected during CSV parsing
        """
        csv_data = base64.b64decode(self.datas_file) or b''
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


    @api.multi
    def create_action(self):
        ModelData = self.env['ir.model.data']
        ActWindow = self.env['ir.actions.act_window']
        IrVaues = self.env['ir.default']
        model_data_id = self.env.ref('connection_tool.view_wizard_connection_tool')
        action_id = ActWindow.create({
            'name': self.name,
             'type': 'ir.actions.act_window',
             'res_model': 'wizard.connection.tool',
             'src_model': self.model_id.model,
             'view_type': 'form',
             'context': "{'import_id': %d}" % (self.id),
             'view_mode':'form,tree',
             'view_id': model_data_id.id,
             'target': 'new',
             'auto_refresh':1
        })
        value_id  = IrVaues.create({
            'name': self.name,
            'model': self.model_id.model,
            'key2': 'client_action_multi',
            'value': "ir.actions.act_window," + str(action_id),
            'object': True,  
        })
        self.write({
            'ref_ir_act_window': action_id,
            'ref_ir_value': value_id,
        })
        return True

    @api.multi
    def unlink_menu(self):
        try:
            if self.ref_menu_ir_act_window:
                self.env['ir.actions.act_window'].sudo().browse([self.ref_menu_ir_act_window.id]).unlink()
            if self.ref_ir_menu:
                self.env['ir.ui.menu'].sudo().browse([self.ref_ir_menu.id]).unlink()
        except:
            raise UserError(_("Deletion of the action record failed."))
        return True


    def create_action_old(self, cr, uid, ids, context=None):
        if not context:
            context = {}
        data_obj = self.pool.get('ir.model.data')
        action_obj = self.pool.get('ir.actions.act_window')
        model_data_id = data_obj._get_id(cr, uid, 'connection_tool', 'view_wizard_connection_tool')
        for template in self.browse(cr, uid, ids, context=context):
            src_obj = template.model_id.model
            res_id = data_obj.browse(cr, uid, model_data_id, context=context).res_id
            button_name = template.name
            action_id = action_obj.create(cr, uid, {
                 'name': button_name,
                 'type': 'ir.actions.act_window',
                 'res_model': 'wizard.connection.tool',
                 'src_model': src_obj,
                 'view_type': 'form',
                 'context': "{'import_id': %d}" % (template.id),
                 'view_mode':'form,tree',
                 'view_id': res_id,
                 'target': 'new',
                 'auto_refresh':1
            }, context)
            value_id = self.pool.get('ir.values').create(cr, uid, {
                 'name': button_name,
                 'model': src_obj,
                 'key2': 'client_action_multi',
                 'value': "ir.actions.act_window," + str(action_id),
                 'object': True,
             }, context)
        self.write(cr, uid, ids, {
                    'ref_ir_act_window': action_id,
                    'ref_ir_value': value_id,
                }, context)
        return True

# access_connection_tool_macro,connection_tool.macro,model_connection_tool_macro,,1,1,1,1
# access_connection_tool_sheet,connection_tool.sheet,model_connection_tool_sheet,,1,1,1,1


class WizardConnectionTool(models.TransientModel):
    """Credit Notes"""

    _name = "wizard.connection.tool"
    _description = "wizard.connection.tool"

    name = fields.Char(string="Name", default="Import Files", readonly=True)
    note = fields.Text(string="Note", readonly=True)

    @api.multi
    def button_import(self):
        Configure = self.env['connection_tool.configure']
        import_id = self._context.get('import_id')
        if import_id:
            imprt = Configure.browse(import_id)._import(flag_imp=False, automatic=False)



class WizardImportMenuCreate(models.TransientModel):
    """Credit Notes"""

    _name = "wizard.import.menu.create"
    _description = "wizard.import.menu.create"

    menu_id = fields.Many2one('ir.ui.menu', 'Parent Menu', required=True)
    name = fields.Char(string='Menu Name', size=64, required=True)
    sequence = fields.Integer(string='Sequence')
    group_ids = fields.Many2many('res.groups', 'menuimport_group_rel', 'menu_id', 'group_id', 'Groups')

    @api.multi
    def menu_create(self):
        ModelData = self.env['ir.model.data']
        ActWindow = self.env['ir.actions.act_window']
        IrMenu = self.env['ir.ui.menu']
        Configure = self.env['connection_tool.configure']
        model_data_id = self.env.ref('connection_tool.view_wizard_connection_tool')

        import_id = self._context.get('import_id')
        vals = {
            'name': self.name,
            'type': 'ir.actions.act_window',
            'res_model': 'wizard.connection.tool',
            'view_type': 'form',
            'context': "{'import_id': %d}" % (import_id),
            'view_mode': 'tree,form',
            'view_id': model_data_id.id,
            'target': 'new',
            'auto_refresh':1
        }
        action_id = ActWindow.sudo().create(vals)
        menu_id = IrMenu.sudo().create({
            'name': self.name,
            'parent_id': self.menu_id.id,
            'action': 'ir.actions.act_window,%d' % (action_id.id,),
            'icon': 'STOCK_INDENT',
            'sequence': self.sequence,
            'groups_id': self.group_ids and [(6, False, [x.id for x in self.group_ids])] or False,
        })
        Configure.sudo().browse([import_id]).write({
            'ref_menu_ir_act_window': action_id.id,
            'ref_ir_menu': menu_id.id,
        })
        return {'type':'ir.actions.act_window_close'}


class Macro(models.Model):
    _name = 'connection_tool.macro'
    _description = "File Macro"
    _order = "sequence, disable"

    name = fields.Char(string="Name")
    row = fields.Char(string="Row")
    col = fields.Char(string="Col")
    col_csv = fields.Char(string="Col CSV")
    field_name = fields.Char(string="Field Name")
    
    selection = fields.Text(string="Selection")
    python = fields.Text(string="Python")
    sequence = fields.Integer(string="Sequence")
    lenght = fields.Integer(string="Length")
    disable = fields.Boolean(string="Disable")

    import_id = fields.Many2one('connection_tool.configure', string='Import', ondelete="cascade")

    field_id = fields.Many2one('ir.model.fields', string='Field')
    model_id = fields.Many2one('ir.model', string='Model')
    # model_ids = fields.Many2many('ir.model', 'macro_model_rel','import_id','model_id', string='Models')
    import_type = fields.Selection(IMPORT_TYPE, string='Import Type')
    field_type = fields.Selection(selection=FIELD_TYPES, string='Field Type')
    output_type = fields.Selection(selection=OUTPUT_TYPE, string='Output Type', help="Output file format")
    return_type = fields.Selection([
            ('name','Name'),
            ('db','Database ID'),
            ('external','External ID')
        ], string='Return type', 
        help="Define the type of ID for inport, if 'Name' the import header is the field name, if 'External ID' the import header is 'field_name/id', and finaly if 'Database ID' the import header is 'field_name/.id', it only apply to relational fields.")
    row_type = fields.Selection([
            ('absolute','Absolute'),
            ('relative','Relative')
        ], string='Row Type', 
        help="'Absolute' for use the fiele row or 'Relative to use Relative Index + Row, relative index is an internal counte for registries.")
    type = fields.Selection(TYPE_SELECTION, string='Action')
    result_type = fields.Selection([
            ('float','With Decimals'), 
            ('integer','Integer'), 
            ('char','Character'),
            ('date','Date')
        ], string='RType', readonly=False, default='char')
    result_zero = fields.Selection([
        ('left','Add Zero Left'), 
        ('rigth','Add Zero Right'),
        ('sleft','Add Space Left'),
        ('srigth','Add Space Right'), ], string='Zero/Space', readonly=False, default='sleft')
    result_start = fields.Integer(string='Start', required=False, default=0)
    result_end = fields.Integer(string='End', required=False, default=0)
    result_required = fields.Boolean(string='Required', default=False)
    result_format_date = fields.Selection([
        ('ddmmyyyy','DDMMYYYY'), 
        ('mmddyyyy','MMDDYYYY'), 
        ('yyyymmdd','YYYYMMDD')], string='Format Date', readonly=False, default='ddmmyyyy')
    result_format_number = fields.Selection([
        ('2','######00'), 
        ('3','#####000'), 
        ('4','####0000'), 
        ('5','###00000'), 
        ('6','##000000'), 
        ('7','#0000000'), ], string='Format Number', readonly=False, default='2')
    result_where = fields.Char(string='Format WHERE', size=254)
    result_orderby = fields.Char(string='Format ORDER BY', size=254)

    table = fields.Char(string="Table")
    parent_table = fields.Char(string="Parent Table")
    db_field = fields.Char(string="Data Base Field")
    db_field_type = fields.Char(string="Data Base Field Type")
    db_relational_field = fields.Char(string="Data Base Field Type")
    field_model = fields.Char(string="Relational Field")

    
  

class ResCompany(models.Model):
    _inherit = 'res.company'

    account_import_id = fields.Many2one('account.account', string='Adjustment Account (import)')


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    @api.one
    @api.depends('company_id')
    def _get_account_import_id(self):
        self.account_import_id = self.company_id.account_import_id

    @api.one
    def _set_account_import_id(self):
        if self.account_import_id != self.company_id.account_import_id:
            self.company_id.account_import_id = self.account_import_id

    

    account_import_id = fields.Many2one('account.account', compute='_get_account_import_id', inverse='_set_account_import_id', required=False,
        string='Adjustment Account (import)', help="Adjustment Account (import).")








"""

import re


vat = 'FRDGLIMPPOL20190509094113.dat'
vat_re = r"^([^0-9 ]{11}[0-9]{14})\.dat$"

regex = re.compile(vat_re)
# vat_re = "[^0-9]{5,5}[A-Z]{3,3}[A-Z]{3,3}[0-9]{4,3}[0-9]{2,2}[0-9]{2,2}[0-9]{3,2}[0-9]{3,2}"

b  = regex.match(vat) and True or False
print "b", b

reg = r"^(([0-9]|[1-9][0-9]|1[0-9]{2}|2[0-4][0-9]|25[0-5])\.){3}([0-9]|[1-9][0-9]|1[0-9]{2}|2[0-4][0-9]|25[0-5])$"

"""