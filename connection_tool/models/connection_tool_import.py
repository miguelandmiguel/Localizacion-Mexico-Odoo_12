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
from odoo.exceptions import AccessError, UserError
from odoo.tools.translate import _
from odoo.tools.mimetypes import guess_mimetype
from odoo.tools.safe_eval import safe_eval
from odoo.tools import config, DEFAULT_SERVER_DATE_FORMAT, DEFAULT_SERVER_DATETIME_FORMAT, pycompat
import csv
from odoo.tools import float_compare, float_is_zero

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


class AccountBankStatementLine(models.Model):
    _inherit = "account.bank.statement.line"

    def _prepare_reconciliation_move_line(self, move, amount):
        res = super(AccountBankStatementLine, self)._prepare_reconciliation_move_line(move, amount)
        if self._context.get("import_etl"):
            res["analytic_tag_ids"] = [self._context.get("tag_id")] # [(6, 0, self._context.get("tag_id"))]
            res["analytic_account_id"] = self._context.get("analytic_id")
        return res

    @api.multi
    def _prepare_move_line_for_currency(self, aml_dict, date):
        self.ensure_one()
        res = super(AccountBankStatementLine, self)._prepare_move_line_for_currency(aml_dict, date)
        if self._context.get("import_etl"):
            aml_dict["analytic_tag_ids"] = [self._context.get("tag_id")] # [(6, 0, self._context.get("tag_id"))]
            aml_dict["analytic_account_id"] = self._context.get("analytic_id")


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

    def import_calculation_wiz(self):
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
    ref_ir_value = fields.Many2one('ir.values', 'Sidebar Button', readonly=True, help="Sidebar button to open the sidebar action")
    ref_ir_menu = fields.Many2one('ir.ui.menu', 'Leftbar Menu', readonly=True, help="Leftbar menu to open the leftbar menu action")
    ref_menu_ir_act_window = fields.Many2one('ir.actions.act_window', 'Leftbar Menu Action', readonly=True,
             help="This is the action linked to leftbar menu.")
    
    export_file_encoding = fields.Selection([
            ('utf-8', 'UTF-8'),
            ('iso-8859-1', 'iso-8859-1 (ANSI)'),
        ], string='Export File Encodig', default='iso-8859-1', help="Export File Encodig")



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
                print("----rows_to_import", rows_to_import)
                rows_to_import = rows_to_import or []
                data = list(itertools.islice(rows_to_import, 0, None))
            elif imprt.type == 'txt':
                print("---------wiz_filenamewiz_filename", wiz_filename)
                # fp = io.open('wiz_filename')
                with open(wiz_filename, encoding=imprt.export_file_encoding) as fp:
                    for line in fp.readlines():
                        data.append(line)
                fp.close()
                # data = wiz_file
            print("---data", data)
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
        directory = "/tmp/tmpsftp%s"%(self.id)
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
        imprt.sudo()._run_import_files_log(use_new_cursor=use_new_cursor, msg=msg)
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
            'shutil': shutil
        }
        if self.source_python_script:
            try:
                safe_eval(self.source_python_script, localdict, mode='exec', nocopy=True)
            except Exception as e:
                _logger.info("--- Error en Python Source %s "%(str(e)) )
                self.sudo()._run_import_files_log(use_new_cursor=use_new_cursor, msg="<span>%s in macro</span><br />"%e)
                if use_new_cursor:
                    cr.commit()
                    cr.close()
                return None
            result = localdict.get('result',False)
            _logger.info("----- Result %s "%(result) )
            if result:
                header = result.get('header') or []
                body = result.get('body') or []
                onchange = result.get('onchange') or {}
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
                            # print("------------eeeeeeeeeee ", str(e))
                            self.sudo()._run_import_files_log(use_new_cursor=use_new_cursor, msg="<span>Error %s </span><br />"%e)
                            if use_new_cursor:
                                cr.commit()
                                cr.close()
                if procesados:
                    if import_wiz == False:
                        imprt = self.source_connector_id.with_context(imprt_id=self.id, directory=directory)                    
                        imprt._move_ftp_filename(files, automatic=True)
                    shutil.move(directory+'/'+files, directory+'/done/'+files)

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



    def process_bank_statement_line(self, statement_id):
        this = self

        Account = this.env["account.account"]
        LayoutLine = this.env['bank.statement.export.layout.line']
        statementLines = this.env['account.bank.statement.line']
        AccountMoveLine = this.env['account.move.line']
        Afiliation = this.env["account.bank.afiliation"]
        AccountAnalytic = this.env["account.analytic.account"]
        Tag = this.env["account.analytic.tag"]
        
        ctx = dict(this._context, force_price_include=False)
        for st_line in statementLines.search([('statement_id', '=', statement_id)]):
            st_line.statement_id._end_balance()
            folioOdoo = st_line.ref and st_line.ref[:10] or ''
            account_id = False

            res = False
            for layoutline_id in LayoutLine.search_read([('name', '=', folioOdoo)], ['id', 'name', 'cuenta_cargo', 'cuenta_abono', 'motivo_pago', 'referencia_numerica', 'layout_id', 'movel_line_ids', 'partner_id', 'importe']):
                movel_line_ids = layoutline_id.get('movel_line_ids') and layoutline_id['movel_line_ids'] or []
                move_lines = AccountMoveLine.browse(movel_line_ids)

                line_residual = st_line.currency_id and st_line.amount_currency or st_line.amount
                line_currency = st_line.currency_id or st_line.journal_id.currency_id or st_line.company_id.currency_id
                total_residual = move_lines and sum(aml.currency_id and aml.amount_residual_currency or aml.amount_residual for aml in move_lines) or 0.0
                balance = total_residual - line_residual

                open_balance_dicts = []
                counterpart_aml_dicts = []
                amount_total = abs(line_residual)
                payment_aml_rec = self.env['account.move.line']
                for aml in move_lines:
                    if aml.full_reconcile_id:
                        continue
                    if aml.account_id.internal_type == 'liquidity':
                        payment_aml_rec |= aml
                    else:
                        amount = aml.currency_id and aml.amount_residual_currency or aml.amount_residual
                        if amount_total >= abs(amount):
                            amount_total -= abs(amount)
                            counterpart_aml_dicts.append({
                                'name': aml.name if aml.name != '/' else aml.move_id.name,
                                'debit': amount < 0 and -amount or 0,
                                'credit': amount > 0 and amount or 0,
                                'move_line': aml,
                            })

                        else:
                            counterpart_aml_dicts.append({
                                'name': aml.name if aml.name != '/' else aml.move_id.name,
                                'debit': balance < 0 and -balance or 0,
                                'credit': balance > 0 and balance or 0,
                                'move_line': aml,
                            })

                res = st_line.with_context(ctx).process_reconciliation(counterpart_aml_dicts, payment_aml_rec, open_balance_dicts)
            if res:
                continue


            codigo = { "V02": "5990100", "V46": "5990100", "V40": "5990100", "V09": "5990100", "V41": "1200004", "V03": "1200004", "V10": "1200004", "W19": "5990100", "W20": "1200004", "W05": "5990100", "W06": "1200004", "W85": "5990100", "W83": "5990100", "W86": "1200004", "C19": "4900101" }
            transaccion = st_line.note.split("|")
            codigo_transaccion = transaccion and transaccion[0] or ""
            if (codigo_transaccion in codigo):
                for afiliation_id in Afiliation.search_read([("name", "ilike", st_line.name)], fields=["name", "description"], limit=1):
                    for tag_id in Tag.search_read([("afiliation_id", "=", afiliation_id.get("id"))], fields=["name", "code"]):
                        for account_id in Account.search_read([('code_alias', 'ilike', codigo[codigo_transaccion]), ('company_id', '=', st_line.company_id.id)], fields=["name"]):
                            analytic_id = AccountAnalytic.search([("code", "=", tag_id.get("code"))])
                            st_line.account_id = account_id.get("id")
                            ctx = {
                                "tag_id": tag_id.get("id"),
                                "analytic_id": analytic_id and analytic_id.id or False,
                                "import_etl": True
                            }
                            st_line.with_context(ctx).fast_counterpart_creation()



        return True


    def process_bank_statement(self, directory='', import_data=''):
        this = self
        Journal = this.env['account.journal']
        Layout = this.env['bank.statement.export.layout']
        LayoutLine = this.env['bank.statement.export.layout.line']
        bankstatement = this.env['account.bank.statement']

        # ["date","ref","partner_id/.id","name","amount","amount_currency","currency_id","balance"]
        result = {
            'header': [],
            'body': []
        }
        body = [
        ]
        journal_id = False
        output = io.BytesIO()
        openBalance = 0.0
        balance = 0.0
        for indx, line in enumerate(import_data):
            nocuenta = line[0:18].replace('/', '-')
            journal_ids = Journal.search_read([('name', 'ilike', nocuenta)], fields=["name", "company_id"])
            for journal in journal_ids:
                journal_id = journal.get("id")
                if indx == 0:
                    # last_bnk_stmt = bankstatement.search([('journal_id', '=', journal_id)], limit=1)
                    openBalance = 0.0 # last_bnk_stmt and last_bnk_stmt.balance_end or 0.0
                transaccion = "%s|%s"%(line[152:155], line[34:64])  
                fecha = line[130:140].replace('/', '-')
                referencia = line[93:123]
                folioBanco = line[28:34]
                amount = float(line[65:81] or '0.0')
                tipoOperacion = 1 if (line[64:65] in ['0', '2']) else -1
                folioOdoo = referencia[:10]
                partner_id = ''
                for layoutline_id in LayoutLine.search_read([('name', '=', folioOdoo)], ['id', 'name', 'cuenta_cargo', 'cuenta_abono', 'motivo_pago', 'referencia_numerica', 'layout_id', 'movel_line_ids', 'partner_id', 'importe']):
                    partner_id = layoutline_id.get('partner_id') and layoutline_id['partner_id'][0] or False
                    layout_id = layoutline_id.get('layout_id') and layoutline_id['layout_id'][0]

                balance += (openBalance + (amount * tipoOperacion))
                body_tmp = [
                    amount * tipoOperacion,
                    balance if indx == 0 else balance,
                    fecha,
                    referencia,
                    transaccion,
                    folioBanco,
                    partner_id,
                    journal.get("company_id") and journal["company_id"][0] or False
                ]
                body.append(body_tmp)
        external_id = '__export__.bank_stmt_import'
        writer = pycompat.csv_writer(output, quoting=1)
        for line in body:
            externalIdFile = open("%s/import/%s.csv"%(directory,external_id), 'a', newline='')
            if externalIdFile:
                wr = csv.writer(externalIdFile, dialect='excel')
                wr.writerow(line)
                writer.writerow(line)
            externalIdFile.close()

        filename = 'import.csv'
        ctx = dict(this.env.context)
        ctx['bank_stmt_import'] = True
        ctx['journal_id'] = journal_id
        import_wizard = this.env['base_import.import'].with_context(**ctx).sudo().create({
            'res_model': 'account.bank.statement.line',
            'file': output.getvalue(),
            'file_name': filename,
            'file_type': 'text/csv'
        })
        header =  ["amount","balance","date","ref","note","name","partner_id/.id", "company_id/.id"]
        options = {'headers': False, 'advanced': True, 'keep_matches': False, 'name_create_enabled_fields': {'currency_id': False}, 'encoding': 'ascii', 'separator': ',', 'quoting': '"', 'date_format': '%Y-%m-%d', 'datetime_format': '', 'float_thousand_separator': ',', 'float_decimal_separator': '.', 'fields': [], 'bank_stmt_import': True}
        results = import_wizard.with_context(**ctx).sudo().do(header, [], options, dryrun=False)
        for statement in results.get('messages') or []:
            statement_id = statement.get('statement_id') or False
            try:
                this.process_bank_statement_line(statement_id)
            except err1:
                try:
                    shutil.rmtree(directory)
                except err:
                    _logger.info("--- Error %s"%(err) )
                    pass
                # bankstatement.browse(statement_id).unlink()
            # {'ids': [85, 86, 87, 88, 89], 'messages': [{'statement_id': 25, 'type': 'bank_statement'}]}
        return True



