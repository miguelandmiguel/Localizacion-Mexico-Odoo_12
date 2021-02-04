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
from odoo import api, fields, models, registry, _, SUPERUSER_ID, tools
from odoo.tools.translate import _
from odoo.tools.mimetypes import guess_mimetype
from odoo.tools.safe_eval import safe_eval
from odoo.tools import config, DEFAULT_SERVER_DATE_FORMAT, DEFAULT_SERVER_DATETIME_FORMAT, pycompat
import csv
from odoo.tools import float_compare, float_is_zero
from odoo.exceptions import MissingError, UserError, ValidationError, AccessError
from odoo.tools.safe_eval import safe_eval, test_python_expr

_logger = logging.getLogger(__name__)

try:
    import mimetypes
except ImportError:
    _logger.debug('Can not import mimetypes')

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
    'text/plain': ('csv', True, None),
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

IMPORT_TYPE = [
    ('csv','Import CSV File'),
    ('txt','TXT Espacios'),
    ('file','Import XLS File'),
    ('postgresql','PostgreSQL'),
    ('ftp','FTP'),
    ('wizard','Wizard'),
    ('xml-rpc','XML RPC')
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
        Configure = self.env['connection_tool.import']
        model_data_id = self.env.ref('connection_tool.connection_tool_import_wizard_form')
        import_id = self._context.get('import_id')
        vals = {
            'name': self.name,
            'type': 'ir.actions.act_window',
            'res_model': 'connection_tool.import.wiz',
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


class ConnectionToolImportWiz(models.TransientModel):
    _name = 'connection_tool.import.wiz'
    _description = 'Run Import Manually'

    datas_fname = fields.Char('Filename')
    datas_file = fields.Binary('File', help="File to check and/or import, raw binary (not base64)")

    def import_calculation(self):
        import_id = self._context.get('import_id')
        threaded_calculation = threading.Thread(target=self._import_calculation_files, args=(import_id, False))
        threaded_calculation.start()
        return {'type': 'ir.actions.act_window_close'}

    def _import_calculation_files(self, import_id, import_wiz):
        with api.Environment.manage():
            # As this function is in a new thread, I need to open a new cursor, because the old one may be closed
            new_cr = self.pool.cursor()
            self = self.with_env(self.env(cr=new_cr))
            self.env['connection_tool.import'].run_import(use_new_cursor=self._cr.dbname, import_id=import_id, import_wiz=import_wiz)
            new_cr.close()
            return {}

    def import_calculation_wiz_old(self):
        import_id = self._context.get('import_id')
        threaded_calculation = threading.Thread(target=self._import_calculation_files_wiz, args=(import_id, self.id))
        threaded_calculation.start()
        return {'type': 'ir.actions.act_window_close'}

    def _import_calculation_files_wiz(self, import_id, import_wiz):
        with api.Environment.manage():
            new_cr = self.pool.cursor()
            self = self.with_env(self.env(cr=new_cr))
            self.env['connection_tool.import'].run_import_wiz(use_new_cursor=self._cr.dbname, import_id=import_id, import_wiz=import_wiz)
            new_cr.close()
            return {}

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
    source_ftp_fileext = fields.Char(string='Import File Ext', default=".dat")
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
    import_from_wizard = fields.Boolean("Import From Wizard?")
    headers = fields.Html('Headers')

    ref_ir_act_window = fields.Many2one('ir.actions.act_window', 'Sidebar Action', readonly=True,
             help="Sidebar action to make this template available on records of the related document model")
    # ref_ir_value = fields.Many2one('ir.values', 'Sidebar Button', readonly=True, help="Sidebar button to open the sidebar action")
    ref_ir_value = fields.Char(string='ir.values')
    ref_ir_menu = fields.Many2one('ir.ui.menu', 'Leftbar Menu', readonly=True, help="Leftbar menu to open the leftbar menu action")
    ref_menu_ir_act_window = fields.Many2one('ir.actions.act_window', 'Leftbar Menu Action', readonly=True,
             help="This is the action linked to leftbar menu.")
    
    export_file_encoding = fields.Selection([
            ('utf-8', 'UTF-8'),
            ('iso-8859-1', 'iso-8859-1 (ANSI)'),
        ], string='Export File Encodig', default='iso-8859-1', help="Export File Encodig")


    @api.constrains('source_python_script')
    def _check_python_code(self):
        for action in self.sudo().filtered('source_python_script'):
            msg = test_python_expr(expr=action.source_python_script.strip(), mode="exec")
            if msg:
                raise ValidationError(msg)

    @api.multi
    def button_import(self):
        wiz_id = self.env['connection_tool.import.wiz'].with_context(import_id=self.id).create({})
        wiz_id.with_context(import_id=self.id).import_calculation()
        return {'type': 'ir.actions.act_window_close'}


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

    # wizard
    @api.model
    def run_import_wiz(self, use_new_cursor=False, import_id=False, import_wiz=False):
        try:
            if use_new_cursor:
                cr = registry(self._cr.dbname).cursor()
                self = self.with_env(self.env(cr=cr))  # TDE FIXME
            self._run_import_files_wiz(use_new_cursor=use_new_cursor, import_id=import_id, import_wiz=import_wiz)
        finally:
            if use_new_cursor:
                try:
                    self._cr.close()
                except Exception:
                    pass
        return {}

    @api.model
    def _run_import_files_wiz(self, use_new_cursor=False, import_id=False, import_wiz=False):
        where = [('id', '=', import_id)]
        for imprt in self.search(where):
            _logger.info("-----------Inicia Proceso Wizard")
            self.sudo()._run_import_files_log_init(use_new_cursor=use_new_cursor)
            msg = "<span><b>Inicia Proceso:</b> %s</span><hr/>"%(time.strftime('%Y-%m-%d %H:%M:%S'))
            self.sudo()._run_import_files_log(use_new_cursor=use_new_cursor, msg=msg)

            directory = "/tmp/tmpsftpwiz%simport%s"%(import_wiz, imprt.id)
            if not os.path.exists(directory):
                os.makedirs(directory)
            if not os.path.exists(directory+'/done'):
                os.makedirs(directory+'/done')
            if not os.path.exists(directory+'/csv'):
                os.makedirs(directory+'/csv')
            if not os.path.exists(directory+'/tmpimport'):
                os.makedirs(directory+'/tmpimport')
            if not os.path.exists(directory+'/import'):
                os.makedirs(directory+'/import')
            if not os.path.exists(directory+'/wiz'):
                os.makedirs(directory+'/wiz')
            wizard_id = self.env['connection_tool.import.wiz'].browse(import_wiz)

            # Escribe datos
            wiz_file = base64.decodestring(wizard_id.datas_file)
            wiz_filename = '%s/%s'%(directory, wizard_id.datas_fname)
            new_file = open(wiz_filename, 'wb')
            new_file.write(wiz_file)
            new_file.close()

            data = []
            options = OPTIONS
            if imprt.type == 'csv':
                mimetype, encoding = mimetypes.guess_type(wiz_filename)
                (file_extension, handler, req) = FILE_TYPE_DICT.get(mimetype, (None, None, None))
                rows_to_import=None
                options['quoting'] = imprt.quoting or OPTIONS['quoting']
                options['separator'] = imprt.separator or OPTIONS['separator']
                f = open(wiz_filename, 'rb')
                datas = f.read()
                f.close()
                if handler:
                    try:
                        rows_to_import=getattr(imprt, '_read_' + file_extension)(options, datas)
                    except Exception:
                        _logger.warn("Failed to read file '%s' (transient id %d) using guessed mimetype %s", wizard_id.datas_fname or '<unknown>', wizard_id.id, mimetype)
                rows_to_import = rows_to_import or []
                data = list(itertools.islice(rows_to_import, 0, None))
            elif imprt.type == 'txt':
                # fp = io.open('wiz_filename')
                with open(wiz_filename, encoding=imprt.export_file_encoding) as fp:
                    for line in fp.readlines():
                        data.append(line)
                fp.close()
                # data = wiz_file
            imprt.get_source_python_script(use_new_cursor=use_new_cursor, files=wizard_id.datas_fname, import_data=data, options=options, import_wiz=directory)
            if use_new_cursor:
                self._cr.commit()

        if use_new_cursor:
            self._cr.commit()

        try:
            shutil.rmtree(directory)
        except:
            pass

    @api.model
    def run_import(self, use_new_cursor=False, import_id=False, import_wiz=False):
        try:
            if use_new_cursor:
                cr = registry(self._cr.dbname).cursor()
                self = self.with_env(self.env(cr=cr))  # TDE FIXME
            self._run_import_files(use_new_cursor=use_new_cursor, import_id=import_id, import_wiz=import_wiz)
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
    def _run_import_files(self, use_new_cursor=False, import_id=False, import_wiz=False):
        where = [('recurring_import','=', True)]
        if import_id:
            where += [('id', '=', import_id)]
        for imprt in self.sudo().search(where):
            imprt.import_files(use_new_cursor=use_new_cursor, import_wiz=import_wiz)
            if use_new_cursor:
                self._cr.commit()
        if use_new_cursor:
            self._cr.commit()


    @api.model
    def action_shutil_directory(self, directory):
        try:
            shutil.rmtree(directory)
        except:
            pass

    @api.multi
    def button_clear_import(self):
        directory = "/tmp/tmpsftp_import_%s"%(self.id)
        imprt = self.source_connector_id.with_context(imprt_id=self.id, directory=directory)
        if self.source_connector_id:
            imprt._delete_ftp_filename(self.source_ftp_write_control, automatic=True)
        if os.path.exists(directory):
            try:
                shutil.rmtree(directory)
            except:
                pass
        return True


    @api.model
    def import_files(self, use_new_cursor=False, import_wiz=False):
        if use_new_cursor:
            cr = registry(self._cr.dbname).cursor()
            self = self.with_env(self.env(cr=cr))
        directory = "/tmp/tmpsftp%s"%(self.id)
        if import_wiz:
            directory = "/tmp/tmpsftp_wiz%s"%(self.id)

        if os.path.exists(directory):
            if use_new_cursor:
                cr.commit()
                cr.close()
            return None

        if not os.path.exists(directory):
            os.makedirs(directory)
        dd = os.listdir(directory)
        if (len(dd) == 0) or (len(dd) == 3 and dd[0] in ['done', 'csv', 'tmpimport', 'import']):
            pass
        else:
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

        imprt = None
        if import_wiz:
            wiz_id = self.env['connection_tool.import.wiz'].browse(import_wiz)
            wiz_file = base64.decodestring(wiz_id.datas_file)
            wiz_filename = '%s/%s'%(directory, wiz_id.datas_fname)
            new_file = open(wiz_filename, 'wb')
            new_file.write(wiz_file)
            new_file.close()
        else:
            imprt = self.source_connector_id.with_context(imprt_id=self.id, directory=directory)
            
            self.sudo()._run_import_files_log_init(use_new_cursor=use_new_cursor)
            msg = "<span><b>Inicia Proceso:</b> %s</span><hr/>"%(time.strftime('%Y-%m-%d %H:%M:%S'))
            self.sudo()._run_import_files_log(use_new_cursor=use_new_cursor, msg=msg)
          
            res = imprt.getFTData()
            if res == None:
                self.sudo()._run_import_files_log(use_new_cursor=use_new_cursor, msg="<span>No existe archivo para procesar</span><br />")
                if use_new_cursor:
                    cr.commit()
                    cr.close()
                self.action_shutil_directory(directory)
                return res
            elif res and res.get('error'):
                self.sudo()._run_import_files_log(use_new_cursor=use_new_cursor, msg="<span>%s</span><br/>"%res.get('error'))
                if use_new_cursor:
                    cr.commit()
                    cr.close()
                self.action_shutil_directory(directory)
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
            self.import_files_datas(use_new_cursor=use_new_cursor, files=files, directory=directory, imprt=imprt, import_wiz=import_wiz)
        if use_new_cursor:
            cr.commit()
            cr.close()
        try:
            shutil.rmtree(directory)
        except:
            pass
        if import_wiz == False:
            if self.source_connector_id:
                imprt._delete_ftp_filename(self.source_ftp_write_control, automatic=True)

        msg = "<span><b>Termina Proceso:</b> %s</span><hr/>"%(time.strftime('%Y-%m-%d %H:%M:%S'))
        self.sudo()._run_import_files_log(use_new_cursor=use_new_cursor, msg=msg)
        return True


    @api.model
    def import_files_datas(self, use_new_cursor=False, files=False, directory=False, imprt=False, import_wiz=False):
        if use_new_cursor:
            cr = registry(self._cr.dbname).cursor()
            self = self.with_env(self.env(cr=cr))

        self.source_ftp_filename = files
        
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
                res = self.get_source_python_script(use_new_cursor=use_new_cursor, files=files, import_data=import_data, options=options, import_wiz=import_wiz, directory=directory)
            except Exception as e:
                self.sudo()._run_import_files_log(use_new_cursor=use_new_cursor, msg="<span>%s in macro</span><br />"%e)
                if import_wiz == False:
                    imprt = self.source_connector_id.with_context(imprt_id=self.id, directory=directory)
                    imprt._delete_ftp_filename(self.source_ftp_write_control, automatic=True)
                if use_new_cursor:
                    cr.commit()
                    cr.close()
                return None

        if use_new_cursor:
            cr.commit()
            cr.close()

    @api.model
    def get_source_python_script(self, use_new_cursor=False, files=False, import_data=False, options=False, import_wiz=False, directory=False):
        if use_new_cursor:
            cr = registry(self._cr.dbname).cursor()
            self = self.with_env(self.env(cr=cr))
        # directory = "/tmp/tmpsftp%s"%(self.id)
        # if import_wiz:
        #     directory = import_wiz
        localdict = {
            'this': self,
            'user_id': self.env.context.get('uid') or self.env.uid,
            'file_name': files,
            'directory': directory,
            'csv': csv,
            'open': open,
            're': re,
            'time': time,
            'datetime': datetime,
            'context': dict(self._context),
            '_logger': _logger,
            'UserError': UserError,
            'import_data': import_data,
            'import_fields': [],
            'io': io,
            'pycompat': pycompat,
            'shutil': shutil,
            'use_new_cursor': use_new_cursor,
            'next': next
        }
        if self.source_python_script:
            try:
                safe_eval(self.source_python_script, localdict, mode='exec', nocopy=True)
            except Exception as e:
                _logger.info("--- Error en Python Source %s "%(str(e)) )
                self.sudo()._run_import_files_log(use_new_cursor=use_new_cursor, msg="<span>%s in macro</span><br />"%e)
                if self.source_connector_id:
                    imprt = self.source_connector_id.with_context(imprt_id=self.id, directory=directory)
                    imprt._move_ftp_filename_noprocesados(files, automatic=True)
                    imprt._delete_ftp_filename(self.source_ftp_write_control, automatic=True)
                try:
                    shutil.rmtree(directory)
                except:
                    pass
                return None

            result = localdict.get('result',False)
            _logger.info("----- Result %s "%(result) )
            if result:
                header = result.get('header') or []
                body = result.get('body') or []
                onchange = result.get('onchange') or {}
                error_proceso = result.get('error_proceso') or False
                _logger.info("----------- Error en Proceso %s "%(error_proceso) )
                if error_proceso:
                    if self.source_connector_id:
                        imprt = self.source_connector_id.with_context(imprt_id=self.id, directory=directory)
                        imprt._move_ftp_filename_noprocesados(files, automatic=True)
                        imprt._delete_ftp_filename(self.source_ftp_write_control, automatic=True)
                    try:
                        shutil.rmtree(directory)
                    except:
                        pass
                    return None

                fileTmp = {}
                procesados = True
                for ext_id in body:
                    if self.output_destination == 'this_database':
                        fileTmp[ext_id] = None
                        try:
                            msg="<span>Archivo: <b>%s</b> </span><br /><span>External ID: %s</span><br />"%(files, ext_id)
                            self.sudo()._run_import_files_log(use_new_cursor=use_new_cursor, msg=msg)
                            file_ext_id = "%s/import/%s.csv"%(directory, ext_id)
                            output = io.BytesIO()
                            writer = pycompat.csv_writer(output, quoting=1)
                            with open(file_ext_id, 'r') as f:
                                reader = csv.reader(f, delimiter=',')
                                for tmp_list in list(reader):
                                    writer.writerow(tmp_list)
                            dtas_csv = output.getvalue()
                            import_wizard = self.env['base_import.import'].sudo().create({
                                'res_model': self.model_id.model,
                                'file_name': '%s.csv'%(ext_id),
                                'file': dtas_csv,
                                'file_type': 'text/csv',
                            })
                            results = import_wizard.with_context(ConnectionTool=True).sudo().do(header, [], {'headers': True, 'separator': ',', 'quoting': '"', 'date_format': '%Y-%m-%d', 'datetime_format': ''}, False)
                            _logger.info("---------  Result Importa Data %s "%results)
                            if results.get("ids"):
                                fileTmp[ext_id] = results['ids']
                                msg="<span>Database ID: %s</span><br />"%(results['ids'])

                                if (onchange.get('lines') or ''):
                                    model_name = self.model_id.model
                                    model_ids = results['ids']
                                    model_line = onchange['lines'].get('model') or ''
                                    related_id = onchange['lines'].get('related_id') or ''
                                    action_onchange = onchange['lines'].get('onchange') or []
                                    self.action_onchange_post(model_name=model_name, model_ids=model_ids, model_line=model_line, related_id=related_id, onchange=action_onchange)
                            else:
                                procesados = False
                                msg="<span>Error: %s</span> "%(results['messages'])
                            self.sudo()._run_import_files_log(use_new_cursor=use_new_cursor, msg=msg)
                        except Exception as e:
                            self.sudo()._run_import_files_log(use_new_cursor=use_new_cursor, msg="<span>Error %s </span><br />"%e)
                            if self.source_connector_id:
                                imprt = self.source_connector_id.with_context(imprt_id=self.id, directory=directory)
                                imprt._move_ftp_filename(files, automatic=True)
                                imprt._delete_ftp_filename(self.source_ftp_write_control, automatic=True)
                            if use_new_cursor:
                                cr.commit()
                                cr.close()
                            return None
                _logger.info("---------  Result Importa Data procesados %s "%procesados)
                if procesados:
                    if self.source_connector_id:
                        imprt = self.source_connector_id.with_context(imprt_id=self.id, directory=directory)
                        imprt._move_ftp_filename(files, automatic=True)
                        imprt._delete_ftp_filename(self.source_ftp_write_control, automatic=True)
                    # shutil.move(directory+'/'+files, directory+'/done/'+files)
                    try:
                        shutil.rmtree(directory)
                    except:
                        pass
                    if use_new_cursor:
                        cr.commit()
                        cr.close()
                    return None

        self.sudo()._run_import_files_log(use_new_cursor=use_new_cursor, msg="<hr />")
        if use_new_cursor:
            cr.commit()
            cr.close()

    @api.one
    def action_onchange_post(self, model_name=False, model_ids=False, model_line=False, related_id=False, onchange=False):
        ids = self.env[model_name].browse(model_ids)
        if model_line:
            for line_id in self.env[model_line].search([(related_id, 'in', ids.ids)]):
                for action_onchange in onchange:
                    getattr(line_id, action_onchange)()




    @api.model
    def _run_import_files_log_init(self, use_new_cursor=False):
        if use_new_cursor:
            cr = registry(self._cr.dbname).cursor()
            self = self.with_env(self.env(cr=cr))
        # message = ""
        # if self.output_messages:
        #     message = self.output_messages
        self.write({
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














    @api.model
    def process_bank_statement_thread(self, use_new_cursor=False, directory='', import_data=''):
        if use_new_cursor:
            cr = registry(self._cr.dbname).cursor()
            self = self.with_env(self.env(cr=cr))  # TDE FIXME
        self.action_process_bank_statement_thread(directory=directory, import_data=import_data)
        if use_new_cursor:
            self._cr.commit()

        if use_new_cursor:
            try:
                self._cr.close()
            except Exception as e:
                _logger.info("---------ERROR %s "%(e) )
                pass
        return {}

    # def action_process_bank_statement_thread(self, directory='', import_data=''):
    def process_bank_statement(self, directory='', import_data=''):
        this = self
        Journal = this.env['account.journal']
        Layout = this.env['bank.statement.export.layout']
        LayoutLine = this.env['bank.statement.export.layout.line']
        bankstatement = this.env['account.bank.statement']
        bankstatementLine = this.env['account.bank.statement.line']

        result = {
            'header': [],
            'body': []
        }
        body = [
        ]
        journal_id = False
        openBalance = 0.0
        balance = 0.0
        encoding = 'utf-8'
        len_import_data = len(import_data)
        for indx, line in enumerate(import_data):
            _logger.info("----------- Process statement %s/%s"%(indx, len_import_data))
            nocuenta = line[0:18].replace('/', '-')
            journal_ids = Journal.search_read([('name', 'ilike', nocuenta)], fields=["name", "company_id"])
            for journal in journal_ids:
                journal_id = journal.get("id")
                if indx == 0:
                    openBalance = 0.0 
                transaccion = "%s|%s"%(line[152:155], line[34:64])
                # fecha = line[130:140].replace('/', '-')
                fecha = line[18:28]
                
                folioBanco = line[28:34]
                amount = float(line[65:81] or '0.0')
                tipoOperacion = 1 if (line[64:65] in ['0', '2']) else -1
                
                referencia = line[93:123]
                codigoTransaccion = line[152:155]
                if codigoTransaccion in ["T17", "T22", "T06"]:
                    folioOdoo = referencia[7:17]
                elif codigoTransaccion in ["P14"]:
                    folioOdoo = referencia.replace('REF:', '').replace('CIE:1', '').replace('CIE:0', '').strip()
                else:
                    folioOdoo = referencia[:10]
                partner_id = ''
                for layoutline_id in LayoutLine.search_read([('name', '=', folioOdoo)], ['id', 'name', 'cuenta_cargo', 'cuenta_abono', 'motivo_pago', 'referencia_numerica', 'layout_id', 'movel_line_ids', 'partner_id', 'importe']):
                    partner_id = layoutline_id.get('partner_id') and layoutline_id['partner_id'][0] or False
                    layout_id = layoutline_id.get('layout_id') and layoutline_id['layout_id'][0]
                balance += (openBalance + (amount * tipoOperacion))
                amount_tmp = '%s'%(amount * tipoOperacion)
                balance_tmp = '%s'%(balance if indx == 0 else balance)
                fecha_tmp = '%s'%(fecha)
                referencia_tmp = '%s'%(referencia)
                transaccion_tmp = '%s'%transaccion
                folioBanco_tmp = '%s'%folioBanco
                partner_tmp = '%s'%partner_id
                journal_tmp = '%s'%(journal.get("company_id") and journal["company_id"][0] or '')
                body_tmp = [
                    amount_tmp,    #.encode(encoding),
                    balance_tmp,    #.encode(encoding),
                    fecha_tmp,    #.encode(encoding),
                    referencia_tmp,    #.encode(encoding),
                    transaccion_tmp,
                    folioBanco_tmp,    #.encode(encoding),
                    partner_tmp,    #.encode(encoding),
                    journal_tmp,    #.encode(encoding),
                ]
                body.append(body_tmp)
        output =  io.StringIO()
        writer = csv.writer(output, dialect='excel', delimiter=',')
        for line in body:
            writer.writerow(line)
        content = output.getvalue()

        filename = '__export__.account_bank_statement_line_%s.csv'%(self.id)
        _logger.info("-------------filename %s"%(filename) )
        ctx = dict(this.env.context)
        ctx['bank_stmt_import'] = True
        ctx['journal_id'] = journal_id
        import_wizard = this.env['base_import.import'].with_context(**ctx).sudo().create({
            'res_model': 'account.bank.statement.line',
            'file': content.encode('utf-8'),
            'file_name': filename,
            'file_type': 'text/csv'
        })
        _logger.info("------------ import_wizard %s"%(import_wizard))
        header =  ["amount","balance","date","ref","note","name","partner_id/.id", "company_id/.id"]
        options = {'headers': False, 'advanced': True, 'keep_matches': False, 'name_create_enabled_fields': {'currency_id': False}, 'encoding': 'ascii', 'separator': ',', 'quoting': '"', 'date_format': '%Y-%m-%d', 'datetime_format': '', 'float_thousand_separator': ',', 'float_decimal_separator': '.', 'fields': [], 'bank_stmt_import': True}
        options['encoding'] = 'utf-8'
        results = import_wizard.with_context(**ctx).sudo().do(header, [], options, dryrun=False)
        _logger.info("------------ IDS results %s "%(results ) )
        _logger.info("------------ IDS %s "%(results.get("ids") ) )
        if results.get('ids'):
            for statement in results.get('messages') or []:
                statement_id = statement.get('statement_id') or False
                amount_total_txt = balance_end_txt = initial_txt = ''
                for st in bankstatement.browse( statement_id ):
                    amount_total = sum(st.line_ids.mapped('amount'))
                    amount_total_txt = "{0:,.2f}".format(amount_total)
                    last_line = st.line_ids.filtered(lambda l: '|SALDO ULTIMA TRANS' in l.note)
                    if len(last_line) > 1:
                        last_line = last_line[-1]
                    if len(last_line) == 1:
                        balance_end = last_line.amount
                        balance_end_txt = "{0:,.2f}".format(balance_end)
                        initial = (balance_end * 2) - amount_total
                        initial_txt = "{0:,.2f}".format(initial)
                        st.write({'balance_start':initial, 'balance_end_real':balance_end, 'name':'EXT/'+st.date.strftime('%Y-%m-%d')})
                        last_line.unlink()

            for statement in results.get('messages') or []:
                statement_id = statement.get('statement_id') or False
                for statement_id in bankstatement.browse( statement_id ):
                    _logger.info("----------- statement_id %s"%statement_id )
                    msg = """<strong>Importar Extracto Bancarios: </strong><br/>
                    Referencia:  <a data-oe-id=%s data-oe-model="account.bank.statement" href=#id=%s&model=account.bank.statement>%s</a><br/>
                    Fecha: %s <br/> Diario: %s <br/> Compañia: %s"""%(
                      statement_id.id,
                      statement_id.id,
                      statement_id.name or statement_id.journal_id.name, 
                      statement_id.date, 
                      statement_id.journal_id.name,
                      statement_id.company_id.name)
                    this.send_msg_channel(body=msg)

        return True