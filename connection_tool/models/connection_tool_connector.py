# -*- coding: utf-8 -*-
import shutil
import base64
import pysftp
from ftplib import FTP
import re
import logging
import io
from io import BytesIO
try:
    from StringIO import StringIO
except ImportError:
    from io import StringIO

import logging
import threading
from odoo import api, fields, models, registry, _, SUPERUSER_ID
from odoo.exceptions import AccessError, UserError
from odoo.tools.translate import _

_logger = logging.getLogger(__name__)

OPTIONS = {'headers': True, 'quoting': '"', 'separator': ',', 'encoding': 'utf-8'}
FIELD_TYPES = [(key, key) for key in sorted(fields.Field.by_type)]

class OdooFTP():
    def __init__(self, host='', port=21, username='', password='', path='', path_done='', security=False):
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.path = path
        self.path_done = path_done
        self.security = security
        self.ftp = None
        self.file_ftp = ''


    def get_connection(self):
        logging.info("CRON _import - Inicia ")
        if self.security:
            cnopts = pysftp.CnOpts()
            cnopts.hostkeys = None  # ignore knownhosts
            self.ftp = pysftp.Connection(
                host=self.host,
                port=self.port,
                username=self.username,
                password=self.password,
                cnopts=cnopts
            )
            return self.ftp
        else:
            self.ftp = FTP()
            self.ftp.connect(self.host, self.port)
            self.ftp.login(self.username, self.password)
            self.ftp.cwd(self.path)
            return self.ftp

    def _getFTPData(self, imprt):
        if self.security:
            return self._getSFTPData(imprt)
        else:
            print("--0000000")
        return ''

    def _getSFTPData(self, imprt):
        self.ftp = self.get_connection()
        self.ftp.chdir(self.path)

        # Archivo de Control
        exists = self.ftp.exists(imprt.source_ftp_write_control)
        if exists:
            logging.info("CRON _import Security %s - Existe archivo Control %s "%(self.security, imprt.source_ftp_write_control) )
            return None
        output = StringIO()
        print("imprt.source_ftp_write_control", imprt.source_ftp_write_control)
        self.ftp.putfo(output, imprt.source_ftp_write_control)
        logging.info("CRON _import Security %s - File Control %s "%(self.security, imprt.source_ftp_write_control) )

        directory = "/tmp/tmpsftp%s"%(imprt.id)
        regex = re.compile(imprt.source_ftp_refilename)
        # Busca archivo en el servidor
        file_ftp = ''
        listdir = self.ftp.listdir()
        for line in listdir:
            validate = regex.match(line) and True or False
            if validate:
                self.ftp.get(line, directory+'/'+line)
                logging.info("CRON _import Security %s - File Transer %s "%(self.security, line))
                file_ftp += line+'|'
        if not file_ftp:
            return None
        logging.info("CRON _import Security %s - Files %s "%(self.security, file_ftp) )
        # imprt.source_ftp_filenamedatas = file_ftp

        self.ftp.close()
        return True

    def _get_dirfile(self, file_re):
        self.ftp = self.get_connection()
        regex = re.compile(file_re)
        file_ftp = ''
        listdir = []
        if self.security:
            self.ftp.chdir(self.path)
            listdir = self.ftp.listdir()
            self.ftp.close()
            for line in listdir:
                validate = regex.match(line) and True or False
                if validate:
                    file_ftp = line
                    break
                else:
                    file_ftp = ''
        else:
            self.ftp.dir(listdir.append)
            self.ftp.quit()

            for line in listdir:
                ll = line[29:].strip().split(' ')
                file_ftp = ll[ -1 ]
                validate = regex.match(file_ftp) and True or False
                if validate:
                    break
                else:
                    file_ftp = ''
        logging.info("CRON _import Security %s - Files %s "%(self.security, file_ftp) )
        return file_ftp

    def get_file_exist(self, filename):
        self.ftp = self.get_connection()
        res = False
        if self.security:
            self.ftp.chdir(self.path)
            res = self.ftp.exists(filename)
            self.ftp.close()
        else:
            if filename in self.ftp.nlst():
                res = True
            self.ftp.quit()
        logging.info("CRON _import Security %s - File Exists %s "%(self.security, res) )
        return res

    def get_file_push(self, filename):
        self.ftp = self.get_connection()
        output = StringIO()
        if self.security:
            self.ftp.chdir(self.path)
            self.ftp.putfo(output, filename)
            self.ftp.close()
        else:
            self.ftp.storbinary('STOR ' + filename, output)
            self.ftp.quit()
        output.close()
        logging.info("CRON _import Security %s - File Push %s "%(self.security, filename) )
        return True

    def get_file_read(self, filename):
        self.ftp = self.get_connection()
        info = ""
        flo = io.BytesIO()
        if self.security:
            self.ftp.chdir(self.path)
            self.ftp.getfo(filename, flo)
            self.ftp.close()
        else:
            self.ftp.retrbinary('RETR %s'%(filename), flo.write)
            self.ftp.quit()
        info = flo.getvalue()
        flo.close()
        logging.info("CRON _import Security %s - File Read %s "%(self.security, '') )
        return info

    def get_file_delete(self, filename):
        self.ftp = self.get_connection()
        if self.security:
            self.ftp.chdir(self.path)
            res = self.ftp.exists(filename)
            if res:
                self.ftp.remove(filename)
            self.ftp.close()
        else:
            if filename in self.ftp.nlst():
                self.ftp.delete(filename)
            self.ftp.quit()
        logging.info("CRON _import Security %s - File Delete %s "%(self.security, filename) )
        return True

    def get_file_move(self, filename):
        self.ftp = self.get_connection()
        if self.security:
            self.ftp.chdir(self.path_done)
            if self.ftp.exists(filename):
                self.ftp.remove(filename)
            self.ftp.chdir(self.path)
            self.ftp.rename(filename, self.path_done+'/'+filename)
            self.ftp.close()
        else:
            self.ftp.rename(filename, self.path_done+'/'+filename)
            self.ftp.quit()
        logging.info("CRON _import Security %s - File Delete %s "%(self.security, filename) )
        return True            



class Conector(models.Model):
    _name = "connection_tool.connector"
    _description = "Connector to PostgrSQL, FTP"

    name = fields.Char(string='Name', required=True)
    host = fields.Char(string='Host Address', required=True)
    port = fields.Char(string='Port', size=5, required=True)
    user = fields.Char(string='User', required=True)
    password = fields.Char(string='Password', required=True)
    dbname = fields.Char(string='Data Base', readonly=True)
    security = fields.Boolean(string='Security', default=False)
    type = fields.Selection([
            ('sql','PostgreSQL'),
            ('ftp','FTP'),
            ('ws','XML-RPC')
        ], string='Conecction Type', default="ftp")


    @api.multi
    def name_get(self):
        result = []
        for rec in self:
            result.append((rec.id, "[%s] %s" % (rec.type, rec.name or '')))
        return result

    def getFTP(self, imprt):
        ftp = OdooFTP(
            host=self.host,
            port=int(self.port),
            username=self.user,
            password=self.password,
            path=imprt.source_ftp_path,
            path_done=imprt.source_ftp_path_done,
            security=self.security
        )
        return ftp

    def getFTData(self):
        imprt = self._context.get('imprt') or False
        ftp = self.getFTP(imprt)
        res = ftp._getFTPData(imprt)
        return res

    def _get_ftp_dirfile(self, filename='', automatic=False):
        imprt = self._context.get('imprt') or False
        file_re = imprt.source_ftp_refilename or ''
        ftp = self.getFTP(imprt)
        filename = ftp._get_dirfile(file_re)
        if filename:
            imprt.source_ftp_filename = filename
            return True
        else:
            return None

    def _get_ftp_check_filename_exist(self, filename='', automatic=False):
        imprt = self._context.get('imprt') or False
        ftp = self.getFTP(imprt)
        exists = ftp.get_file_exist(filename)
        return exists

    def _push_to_ftp(self, filename='', automatic=False):
        imprt = self._context.get('imprt') or False
        ftp = self.getFTP(imprt)
        ftp.get_file_push(filename)
        return True

    def _read_ftp_filename(self, filename='', automatic=False):
        imprt = self._context.get('imprt') or False
        ftp = self.getFTP(imprt)
        info = ftp.get_file_read(filename)
        if not info:
            return None
        return info

    def _delete_ftp_filename(self, filename='', automatic=False):
        imprt = self._context.get('imprt') or False
        ftp = self.getFTP(imprt)
        ftp.get_file_delete(filename)
        return True


    def _move_ftp_filename(self, filename='', automatic=False):
        imprt = self._context.get('imprt') or False
        ftp = self.getFTP(imprt)
        ftp.get_file_move(filename)
        return True








        """



            if files != 'done':
                _logger.info("CRON: import_data %s "%(files))
                info = open(directory+'/'+files, "r")
                # Model.with_env(new_env).datas_file = base64.b64encode(info.read().encode("utf-8"))
                # Model.with_env(new_env).source_ftp_filename = files
                Model.write({
                    'datas_file': base64.b64encode(info.read().encode("utf-8")),
                    'source_ftp_filename': files
                })
                if new_cr:
                    new_cr.commit()
                    new_cr.close()
                if Model.source_python_script:
                    options = {
                        'headers': Model.with_header
                    }
                    if Model.type == 'csv':
                        if not Model.quoting and Model.separator:
                            raise UserError(_("Set Quoting and Separator fields before load CSV File."))
                        options = OPTIONS
                        options['quoting'] = Model.quoting or OPTIONS['quoting']
                        options['separator'] = Model.separator or OPTIONS['separator']
                    import_data, import_fields = Model._convert_import_data(options)
                    print("import_data", import_data)
                    lendatas = len(import_data)
                    if not lendatas:
                        return None
                    res = Model.get_source_python_script(import_data, import_fields, flag_imp=flag_imp, automatic=automatic)
                    print("ressss", res)
                    if res == True:
                        shutil.move(directory+'/'+files, directory+'/done/'+files)
                        new_imprt._move_ftp_filename(files, automatic=automatic)

            if new_cr:
                new_cr.commit()
                new_cr.close()
        return True
        """



    """
    @api.multi
    def _get_ftp(self, automatic=False):
        self.ensure_one()
        imprt = self._context.get('imprt') or False
        host = str(self.host)
        port = int(self.port)
        user = str(self.user)
        password = str(self.password)
        path = str(imprt.source_ftp_path)
        ftp = FTP()
        try:
            ftp.connect(host, port)
        except Exception as e:
            if automatic:
                self._cr.rollback()
                _logger.exception(_('Connection error with host: %s, port %s. Error: %s.')%(host, port, e))
            else:
                raise UserError(_('Connection error with host: %s, port %s. Error: %s.')%(host, port, e))
        try:
            ftp.login(user, password)
        except Exception as e:
            if automatic:
                self._cr.rollback()
                _logger.exception(_('Login error with user: %s, password: ****. Error: %s')%(user, e))
            else:
                raise UserError(_('Login error with user: %s, password: ****. Error: %s')%(user, e))
        if path:
            try:
                ftp.cwd(path)
            except Exception as e:
                if automatic:
                    self._cr.rollback()
                    _logger.exception(_('Path error with path: %s. Error: %s')%(path, e))
                else:
                    raise UserError(_('Path error with path: %s. Error: %s')%(path, e))
        return ftp
    

    @api.multi
    def _get_ftp_dirfile(self, filename, automatic=False):
        self.ensure_one()
        imprt = self._context.get('imprt') or False

        if not imprt.source_ftp_re:
            return imprt.source_ftp_filename

        vat_re = r"%s"%(imprt.source_ftp_refilename)
        regex = re.compile(vat_re)

        ftp = self._get_ftp(automatic=automatic)
        dir_file = ''
        dir_list = []
        ftp.dir(dir_list.append)
        ftp.quit()
        for line in dir_list:
            ll = line[29:].strip().split(' ')
            dir_file = ll[ -1 ]
            validate = regex.match(dir_file) and True or False
            if validate:
                break
            else:
                dir_file = ''
        _logger.info("CRON: file ftp %s"%dir_file )
        imprt.source_ftp_filename = dir_file


    @api.multi
    def _get_ftp_check_filename_exist(self, filename='', automatic=False):
        self.ensure_one()
        imprt = self._context.get('imprt') or False
        ftp = self._get_ftp(automatic=automatic)
        res = False
        if filename in ftp.nlst():
            res = True
        ftp.quit()
        return res

    @api.multi
    def _push_to_ftp(self, filename, output, automatic=False):
        self.ensure_one()
        imprt = self._context.get('imprt') or False
        ftp = self._get_ftp(automatic=automatic)
        try:
            ftp.storbinary('STOR ' + filename, output)
        except Exception as e:
            if automatic:
                self._cr.rollback()
                _logger.exception(_('Write file error with file: %s, path: %s. Error: %s')%(filename, imprt.source_ftp_path, e))
            else:
                raise UserError(_('Write file error with file: %s, path: %s. Error: %s')%(filename, imprt.source_ftp_path, e))
        ftp.quit()
        return True

    @api.multi
    def _read_ftp_filename(self, filename, automatic=False):
        self.ensure_one()
        imprt = self._context.get('imprt') or False
        ftp = self._get_ftp(automatic=automatic)
        info = ""
        try:
            r = io.BytesIO()
            ftp.retrbinary('RETR %s'%(filename), r.write)
            info = r.getvalue() # .decode()
        except Exception as e:
            if automatic:
                self._cr.rollback()
                _logger.exception(_('Read file error with file: %s, path: %s. Error: %s')%(filename, imprt.source_ftp_path, e))
            else:
                raise UserError(_('Read file error with file: %s, path: %s. Error: %s')%(filename, imprt.source_ftp_path, e))
        ftp.quit()
        r.close()
        return info

    @api.multi
    def _delete_ftp_filename(self, filename, automatic=False):
        self.ensure_one()
        imprt = self._context.get('imprt') or False
        ftp = self._get_ftp(automatic=automatic)
        if filename in ftp.nlst():
            ftp.delete(filename)
        ftp.quit()
        return False

    @api.multi
    def _move_ftp_filename(self, filename, automatic=False):
        self.ensure_one()
        imprt = self._context.get('imprt') or False
        ftp = self._get_ftp(automatic=automatic)
        ftp.rename(imprt.source_ftp_filename, imprt.source_ftp_path_done+'/'+imprt.source_ftp_filename)
        ftp.quit()
        return False

    """