# -*- coding: utf-8 -*-

import time, datetime
import os
import pysftp
import csv
import threading
import base64
import codecs, itertools, shutil
try:
    from StringIO import StringIO
except ImportError:
    from io import StringIO

from collections import namedtuple, OrderedDict, defaultdict
from dateutil.relativedelta import relativedelta
from psycopg2 import OperationalError

import odoo
from odoo.tools.misc import split_every
from odoo import api, fields, models, registry, SUPERUSER_ID, _
from odoo.osv import expression
from odoo.tools import DEFAULT_SERVER_DATETIME_FORMAT, float_compare, float_round
from odoo.exceptions import MissingError, UserError, ValidationError, AccessError
from odoo.tools.safe_eval import safe_eval, test_python_expr

try:
    import mimetypes
except ImportError:
    _logger.debug('Can not import mimetypes')


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
OPTIONS = {
    'headers': True, 'advanced': True, 'keep_matches': False, 
    'name_create_enabled_fields': {}, 'encoding': 'utf-8', 'separator': ',', 
    'quoting': '"', 'date_format': '%Y-%m-%d', 'datetime_format': '', 
    'float_thousand_separator': ',', 
    'float_decimal_separator': '.'
}

import logging
_logger = logging.getLogger(__name__)


class OdooFTP():
    def __init__(self, host='', port=21, username='', password='', path='', path_done='', security=True, file_ctrl=False, import_id=False):
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.path = path
        self.path_done = path_done
        self.security = security
        self.file_ctrl = file_ctrl
        self.import_id = import_id
        self.ftp = None
        self.file_ftp = ''

    def getFileDAT(self):
        try:
            cnopts = pysftp.CnOpts()
            cnopts.hostkeys = None  # ignore knownhosts
            cinfo = { 'host': self.host, 'port': self.port, 'username': self.username,  'password': self.password, 'cnopts': cnopts }
            with pysftp.Connection(**cinfo) as sftp:
                sftp.chdir(self.path)
                try:
                    if sftp.exists(self.file_ctrl):
                        _logger.info("------- CRON Import: Existe el archivo de control %s "%(self.file_ctrl) )
                        return {"error": "Existe el archivo de control %s "%(self.file_ctrl) }
                    encontro = False
                    for line in sftp.listdir():
                        if line.lower().endswith(".dat"):
                            encontro = True
                            output = StringIO()
                            sftp.putfo(output, self.file_ctrl)
                            _logger.info("------- CRON Import: Crea Archivo Control %s "%(self.file_ctrl) )
                            directory = "/tmp/tmpsftp_import_%s"%(self.import_id)
                            sftp.get(line, directory+'/'+line)
                            _logger.info("------- CRON Import: Descarga Archivo DAT %s "%(line) )
                            break
                    if(encontro==False):
                        _logger.info("------- CRON Import: No hay archivos DAT %s "%(line) )
                        return None
                except Exception as e:
                    _logger.info("------- CRON Import: Error %s"%e )
                    if sftp.exists(self.file_ctrl):
                        sftp.remove(self.file_ctrl)
                    _logger.info("------- CRON Import: Error en FTP %s "%(e) )
                    return None
        except Exception as e:
            _logger.info("------- CRON Import: Error en FTP %s "%(e) )
            return None
        return {}



class ConnectionToolImportWiz(models.TransientModel):
    _inherit = 'connection_tool.import.wiz'
    _description = 'Run Import Manually'

    def import_calculation_wiz(self):
        import_ctx_id = self._context.get("import_id")
        imprt = self.env['connection_tool.import'].browse(import_ctx_id)
        if imprt.type == 'csv':
            csv_file = 'import_data.csv'
        elif imprt.type == 'txt':
            csv_file = self.datas_fname
        csv_path = imprt.getCsvPath(is_wizard=self.id, datas_file=self.datas_file, datas_fname=self.datas_fname)
        datas = imprt.setFileCsvPath(is_wizard=self.id, csv_path=csv_path, datas_fname=self.datas_fname, imprt=imprt)
        ctx = {
            'is_wizard': True,
            'csv_file': csv_file,
            'csv_path': csv_path,
            'import_data': datas
        }
        res = imprt.with_context(**ctx).run()
        if res:
            try:
                print("--------------------------------")
                # shutil.rmtree(csv_path)
            except Exception as ee:
                pass


class ConnectionToolImport(models.Model):
    _inherit = 'connection_tool.import'

    def getFTPSource(self):
        imprt = self.source_connector_id
        ftp = OdooFTP(
            host=imprt.host,
            port=int(imprt.port),
            username=imprt.user,
            password=imprt.password,
            path=self.source_ftp_path,
            path_done=self.source_ftp_path_done,
            security=imprt.security,
            file_ctrl=self.source_ftp_write_control,
            import_id=self.id
        )
        return ftp


    def setFileCsvPath(self, is_wizard=False, csv_path=False, datas_fname=False, imprt=False):
        wiz_filename = '%s/%s'%(csv_path, datas_fname)
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
                    _logger.warn("Failed to read file '%s' (transient id %d) using guessed mimetype %s", datas_fname or '<unknown>', is_wizard, mimetype)
            rows_to_import = rows_to_import or []
            externalIdFile = open("%s/wiz/%s.csv"%(csv_path, 'import_data'), 'a', encoding="utf-8", newline='')
            row_datas = list(itertools.islice(rows_to_import, 0, None))
            for row in row_datas:
                wr = csv.writer(externalIdFile, dialect='excel', delimiter ='|')
                wr.writerow(row)
            externalIdFile.close()
        elif imprt.type == 'txt':
            with open(wiz_filename, 'rb') as fp:
                for cnt, line in enumerate(fp):
                    data.append(
                        line.decode(imprt.export_file_encoding)
                    )
        return data

    def getCsvPath(self, is_wizard=False, datas_file=False, datas_fname=False):
        if is_wizard:
            csv_path = "/tmp/wizard_tmpsftp_import_%s"%(is_wizard)
        else:
            csv_path = "/tmp/tmpsftp_import_%s"%(self.id)
        if not os.path.exists(csv_path):
            os.makedirs(csv_path)
            subdirectory = ['done', 'csv', 'tmpimport', 'import', 'wiz']
            for folder in subdirectory:
                if not os.path.exists(csv_path+'/'+folder):
                    os.makedirs(csv_path+'/'+folder)

            wiz_file = base64.decodestring(datas_file)
            wiz_filename = '%s/%s'%(csv_path, datas_fname)
            new_file = open(wiz_filename, 'wb')
            new_file.write(wiz_file)
            new_file.close()
        return csv_path

    @api.model
    def run_action_code_multi(self, action, eval_context=None):
        safe_eval(action.sudo().source_python_script.strip(), eval_context, mode="exec", nocopy=True)
        if 'result' in eval_context:
            return eval_context['result']

    @api.model
    def _get_eval_context(self, action=None):

        def processBankStatement(directory=False, import_data=False):
            return self.process_bank_statement(directory=directory, import_data=import_data)

        def sendMsgChannel(body=""):
            users = self.env.ref('base.user_admin')
            ch_obj = self.env['mail.channel']
            ch_partner = self.env['mail.channel.partner']
            if users:
                for user in users:
                    ch_name = user.name+', '+self.env.user.name
                    ch = ch_obj.sudo().search([('name', 'ilike', str(ch_name))])
                    if not ch:
                        ch = ch_obj.sudo().search([('name', 'ilike', str(self.env.user.name+', '+user.name))])
                    if not ch:
                        ch = ch_obj.sudo().create({
                            'name': user.name+', '+self.env.user.name,
                            'channel_type': 'chat',
                            'public': 'private'
                        })
                        ch_partner.sudo().create({
                            'partner_id': users.partner_id.id,
                            'channel_id': ch.id,
                        })
                        ch_partner.sudo().create({
                            'partner_id': self.env.user.partner_id.id,
                            'channel_id': ch.id,
                            'fold_state': 'open',
                            'is_minimized': False,
                        })
                ch.message_post(
                    attachment_ids=[],
                    body=body,
                    content_subtype='html',
                    message_type='comment',
                    partner_ids=[],
                    subtype='mail.mt_comment',
                    email_from=self.env.user.partner_id.email,
                    author_id=self.env.user.partner_id.id
                )

        def runCopySQLCSV(csv_path, csv_header):
            _logger.info("------- Start Copy %s " % time.ctime() )
            csv_file = open(csv_path, 'r', encoding="utf-8")
            res = self._cr.copy_expert(
                """COPY account_move_line(%s)
                   FROM STDIN WITH DELIMITER '|' """%csv_header, csv_file)
            _logger.info("------- End Copy %s " % time.ctime() )

        def loadDataCSV(csv_path, header):
            csvfile = open(csv_path, 'r', encoding="utf-8")
            reader = csv.reader(csvfile, dialect='excel', delimiter='|')
            if reader:
                if header==False:
                    header = next(reader)
                reader = list(reader)
            csvfile.close()
            return reader

        def log(message, level="info"):
            with self.pool.cursor() as cr:
                cr.execute("""
                    INSERT INTO ir_logging(create_date, create_uid, type, dbname, name, level, message, path, line, func)
                    VALUES (NOW() at time zone 'UTC', %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """, (self.env.uid, 'server', self._cr.dbname, __name__, level, message, "action", action.id, action.name))

        eval_context = {}
        model_name = action.model_id.sudo().model
        model = self.env[model_name]
        eval_context.update({
            'csv': csv,
            'open': open,
            'time': time,
            'datetime': datetime,
            '_logger': _logger,
            'next': next,
            'env': self.env,
            'model': model,
            'Warning': odoo.exceptions.Warning,
            'log': log,
            'loadDataCSV': loadDataCSV,
            'runCopySQLCSV': runCopySQLCSV,
            'sendMsgChannel': sendMsgChannel,
            'processBankStatement': processBankStatement,
            'layout_id': action.id,

        })
        return eval_context


    @api.one
    def run(self):
        ctx = dict(self.env.context)
        res = False
        eval_context = self._get_eval_context(self)
        eval_context['is_wizard'] = ctx.get('is_wizard') or False
        eval_context['csv_file'] = ctx.get('csv_file') or ''
        eval_context['csv_path'] = ctx.get('csv_path') or ''
        eval_context['import_data'] = ctx.get('import_data') or ''
        run_self = self.with_context(eval_context['env'].context)
        func = getattr(run_self, 'run_action_%s_multi' % 'code')
        res = func(self, eval_context=eval_context)
        return res

















    def _run_action_datasetl(self, use_new_cursor=False):
        if use_new_cursor:
            cr = registry(self._cr.dbname).cursor()
            self = self.with_env(self.env(cr=cr))

        options = {}
        _logger.info("------- CRON Import: Inicia Proceso %s " % time.ctime() )
        directory = "/tmp/tmpsftp_import_%s"%(self.id)
        # Si existe directorio no hacer nada
        if os.path.exists(directory):
            _logger.info("------- CRON Import: Existe un archivo previo")
            _logger.info("------- CRON Import: Finaliza Proceso %s " % time.ctime() )
            if use_new_cursor:
                cr.commit()
                cr.close()
            return None

        try:
            # Crea directorio
            try:
                if not os.path.exists(directory):
                    os.makedirs(directory)
                    subdirectory = ['done', 'csv', 'tmpimport', 'import']
                    for folder in subdirectory:
                        if not os.path.exists(directory+'/'+folder):
                            os.makedirs(directory+'/'+folder)
                else:
                    for line in os.listdir(directory):
                        if line.lower().endswith(".dat"):
                            if use_new_cursor:
                                cr.commit()
                                cr.close()
                            _logger.info("------- CRON Import: Existe un archivo previo DAT")
                            _logger.info("------- CRON Import: Finaliza Proceso %s " % time.ctime() )
                            return None
                
                ftp = self.getFTPSource()
                res = ftp.getFileDAT()
                if res == None:
                    self.action_shutil_directory(directory)
                    if use_new_cursor:
                        cr.commit()
                        cr.close()
                    _logger.info("------- CRON Import: Finaliza Proceso %s " % time.ctime() )
                    return res

                imprt = self.source_connector_id.with_context(imprt_id=self.id, directory=directory)
                for line in os.listdir(directory):
                    if line.lower().endswith(".dat"):
                        res = None
                        try:
                            res = self.get_source_python_script(use_new_cursor=use_new_cursor, files=line, import_data=[], options=options, import_wiz=False, directory=directory)
                        except Exception as e:
                            self.sudo()._run_import_files_log(use_new_cursor=use_new_cursor, msg="<span>%s in macro</span><br />"%e)
                            imprt = self.source_connector_id.with_context(imprt_id=self.id, directory=directory)
                            imprt._delete_ftp_filename(self.source_ftp_write_control, automatic=True)

                            try:
                                shutil.rmtree(directory)
                            except Exception as ee:
                                pass

                            if use_new_cursor:
                                cr.commit()
                                cr.close()
                            _logger.info("---- CRON Import: Error Python %s"%(e) )
                            return None
                # time.sleep( 360 )
            except Exception as e:
                try:
                    shutil.rmtree(directory)
                except Exception as ee:
                    pass
                _logger.info("---- CRON Import: Error Error %s"%(e) )
                return None          

        except Exception as e:
            _logger.info("---- CRON Import: Error Error %s"%(e) )
            try:
                shutil.rmtree(directory)
            except Exception as ee:
                pass
        
        _logger.info("------- Finaliza Proceso %s " % time.ctime() )
        if use_new_cursor:
            cr.commit()
            cr.close()

        return {}


    @api.model
    def _run_import_datasetl(self, use_new_cursor=False, company_id=False):
        for imprt in self.search([('recurring_import','=', True)]):
            imprt._run_action_datasetl(use_new_cursor=use_new_cursor)
            if use_new_cursor:
                self._cr.commit()
        if use_new_cursor:
            self._cr.commit()

    @api.model
    def run_importdata(self, use_new_cursor=False, company_id=False):
        """ Call the scheduler in order to check the running procurements (super method), to check the minimum stock rules
        and the availability of moves. This function is intended to be run for all the companies at the same time, so
        we run functions as SUPERUSER to avoid intercompanies and access rights issues. """
        try:
            if use_new_cursor:
                cr = registry(self._cr.dbname).cursor()
                self = self.with_env(self.env(cr=cr))  # TDE FIXME
            self._run_import_datasetl(use_new_cursor=use_new_cursor, company_id=company_id)
        finally:
            if use_new_cursor:
                try:
                    self._cr.close()
                except Exception:
                    pass
        return {}


    @api.multi
    def run_loaddata_filesdat(self, use_new_cursor=False, csv_path=False, csv_header=""):
        _logger.info("------- Start Copy %s " % time.ctime() )
        csv_file = open(csv_path, 'r', encoding="utf-8")
        res = self._cr.copy_expert(
            """COPY account_move_line(%s)
               FROM STDIN WITH DELIMITER '|' """%csv_header, csv_file)
        _logger.info("------- End Copy %s " % time.ctime() )
        return True


    @api.one
    def send_msg_channel(self, body=""):
        users = self.env.ref('base.user_admin')
        ch_obj = self.env['mail.channel']
        ch_partner = self.env['mail.channel.partner']
        if users:
            for user in users:
                ch_name = user.name+', '+self.env.user.name
                ch = ch_obj.sudo().search([('name', 'ilike', str(ch_name))])
                if not ch:
                    ch = ch_obj.sudo().search([('name', 'ilike', str(self.env.user.name+', '+user.name))])
                if not ch:
                    ch = ch_obj.sudo().create({
                        'name': user.name+', '+self.env.user.name,
                        'channel_type': 'chat',
                        'public': 'private'
                    })
                    ch_partner.sudo().create({
                        'partner_id': users.partner_id.id,
                        'channel_id': ch.id,
                    })
                    ch_partner.sudo().create({
                        'partner_id': self.env.user.partner_id.id,
                        'channel_id': ch.id,
                        'fold_state': 'closed',
                        'is_minimized': False,
                    })
            ch.message_post(
                attachment_ids=[],
                body=body,
                message_type='comment',
                partner_ids=[],
                subtype='mail.mt_comment',
                email_from=self.env.user.partner_id.email,
                author_id=self.env.user.partner_id.id
            )
        return True








"""
# -*- coding: utf-8 -*-
import odoorpc
this = odoorpc.ODOO('localhost', port=8079)
this.login('odoo12_donde_pruebas', 'eduardo.bayardo@bias.com.mx', 'Bias4972')
ToolImport = this.env['connection_tool.import']
for timpr_id in ToolImport.browse([7]):
    print("timpr_id", timpr_id)
    timpr_id.send_to_channel('<p>run_extract_filesdat Bienvenidos</p>', "")

no procesar descuadrados

"""