# -*- coding: utf-8 -*-

import time
import os
import pysftp

try:
    from StringIO import StringIO
except ImportError:
    from io import StringIO

from collections import namedtuple, OrderedDict, defaultdict
from dateutil.relativedelta import relativedelta
from odoo.tools.misc import split_every
from psycopg2 import OperationalError

from odoo import api, fields, models, registry, SUPERUSER_ID, _
from odoo.osv import expression
from odoo.tools import DEFAULT_SERVER_DATETIME_FORMAT, float_compare, float_round

from odoo.exceptions import UserError

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
                        return None
                except Exception as e:
                    _logger.info("------- CRON Import: Error %s"%e )
                    if sftp.exists(self.file_ctrl):
                        sftp.remove(self.file_ctrl)
                    return None
        except Exception as e:
            print("--- error")
            return None
        return {}





class Configure(models.Model):
    _inherit = 'connection_tool.import'

    #####################
    #
    # Ejecuta procesos
    #
    #####################

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

    def _run_action_datasetl(self, use_new_cursor=False):
        if use_new_cursor:
            cr = registry(self._cr.dbname).cursor()
            self = self.with_env(self.env(cr=cr))

        _logger.info("------- Start %s " % time.ctime() )

        directory = "/tmp/tmpsftp_import_%s"%(self.id)
        # Si existe directorio no hacer nada
        if os.path.exists(directory):
            _logger.info("------- CRON Import: Existe un archivo previo")
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
                            return None
                
                ftp = self.getFTPSource()
                res = ftp.getFileDAT()
                print("------------res-getFileDAT", res)
                if res == None:
                    self.action_shutil_directory(directory)
                    if use_new_cursor:
                        cr.commit()
                        cr.close()
                    return res

                imprt = self.source_connector_id.with_context(imprt_id=self.id, directory=directory)
                for line in os.listdir(directory):
                    if line.lower().endswith(".dat"):
                        print("----------", line)
                        try:
                            self.import_files_datas(use_new_cursor=use_new_cursor, files=line, directory=directory, imprt=imprt, import_wiz=False)
                            if use_new_cursor:
                                cr.commit()
                        except Exception as e:
                            print("--------- error 002", e)
                            # print("------------eeeeeeeeeee ", str(e))
                            self.sudo()._run_import_files_log(use_new_cursor=use_new_cursor, msg="<span>Error %s </span><br />"%e)
                            if use_new_cursor:
                                cr.commit()
                                cr.close()
                            return None
                # time.sleep( 360 )
            except Exception as e:
                print("--------- error 001", e)
                _logger.info("---- CRON Import: Error Error %s"%(e) )
                return None          

        except Exception as e:
            print("--------- error 000", e)
            try:
                shutil.rmtree(directory)
            except Exception as ee:
                pass

        
        _logger.info("------- End %s " % time.ctime() )
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

            _logger.info("------- Inicia Proceso RUN ")
            self._run_import_datasetl(use_new_cursor=use_new_cursor, company_id=company_id)
            _logger.info("------- Fin Proceso RUN ")

        finally:
            if use_new_cursor:
                _logger.info("------- Finally Inicia Proceso RUN ")
                try:
                    self._cr.close()
                except Exception:
                    pass
                _logger.info("------- Finally Fin Proceso RUN ")
        return {}

