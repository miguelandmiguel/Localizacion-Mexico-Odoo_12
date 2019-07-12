# -*- coding: utf-8 -*-

from ftplib import FTP
import re

import io
from io import BytesIO
try:
    from StringIO import StringIO
except ImportError:
    from io import StringIO

from odoo import api, fields, models
from odoo.exceptions import AccessError, UserError
from odoo.tools.translate import _


class Conector(models.Model):
    _name = "connection_tool.connector"
    _description = "Connector to PostgrSQL, FTP"

    name = fields.Char(string='Name', required=True)
    host = fields.Char(string='Host Address', required=True)
    port = fields.Char(string='Port', size=5, required=True)
    user = fields.Char(string='User', required=True)
    password = fields.Char(string='Password', required=True)
    dbname = fields.Char(string='Data Base', readonly=True)
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


    # 
    # FTP
    # 
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
        ftp.rename(imprt.source_ftp_filename, './'+imprt.source_ftp_path_done+'/'+imprt.source_ftp_filename)
        ftp.quit()
        return False