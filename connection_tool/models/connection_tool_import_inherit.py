# -*- coding: utf-8 -*-

import time
import os
import pysftp
import csv

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

        options = {}
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
                if res == None:
                    self.action_shutil_directory(directory)
                    if use_new_cursor:
                        cr.commit()
                        cr.close()
                    return res

                imprt = self.source_connector_id.with_context(imprt_id=self.id, directory=directory)
                for line in os.listdir(directory):
                    if line.lower().endswith(".dat"):
                        res = None
                        res = self.get_source_python_script(use_new_cursor=use_new_cursor, files=line, import_data=[], options=options, import_wiz=False, directory=directory)
                        print("---res", res)
                        try:
                            
                            print("---res", res)
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
                            return None

                        """
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
                        """
                # time.sleep( 360 )
            except Exception as e:
                print("--------- error 001", e)
                _logger.info("---- CRON Import: Error Error %s"%(e) )
                try:
                    shutil.rmtree(directory)
                except Exception as ee:
                    pass
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


    @api.multi
    def run_loaddata_filesdat(self, use_new_cursor=False, csv_path=False, csv_header=""):
        # name, debit, credit, balance, debit_cash_basis, credit_cash_basis, balance_cash_basis, company_currency_id, account_id, move_id, ref, reconciled, journal_id, date_maturity, date, analytic_account_id, company_id, user_type_id, analytic_tag3_id, analytic_tag4_id, analytic_tag5_id, analytic_tag6_id
        _logger.info("------- Start %s " % time.ctime() )
        csv_file = open(csv_path, 'r', encoding="utf-8")
        res = self._cr.copy_expert(
            """COPY account_move_line(%s)
               FROM STDIN WITH DELIMITER '|' """%csv_header, csv_file)
        _logger.info("------- End %s " % time.ctime() )
        return True


    @api.one
    def run_extract_filesdat(self, use_new_cursor=False, csv_path=False, csv_file=False):
        this = self

        csv_path = directory
        csv_file = file_name
        Journal = this.env['account.journal'].sudo()
        Analytic = this.env['account.analytic.tag'].sudo()
        AccountAnalytic = this.env['account.analytic.account'].sudo()
        Account = this.env['account.account'].sudo()
        Currency = this.env['res.currency'].sudo()
        AccountMove = this.env['account.move'].sudo()
        ResCompany = this.env['res.company'].sudo()

        journal_data = { '02': '__export__.account_journal_34_3002a5fc', '04': '__export__.account_journal_35_7a7055ee', }
        cia_data = {  '01': 'base.main_company',  '02': '__export__.res_company_2_9df76fa0',  '03': '__export__.res_company_3_7a5d5b4a',  '04': '__export__.res_company_2_b7dd0cb1', '05': '__export__.res_company_5_ff170c0f', '06': '__export__.res_company_7_36028222', '07': '__export__.res_company_4_7e1e7fda', '08': '__export__.res_company_8_b46133fd', '09': '__export__.res_company_9_44c3daad', }
        par_data = { '01': '__export__.res_partner_36468_fe2242c2', '02': '__export__.res_partner_8_395b6438', '03': '__export__.res_partner_7_c490012b', '04': '__export__.res_partner_10_ac021b07', '05': '__export__.res_partner_12_ccf4b46e', '06': '__export__.res_partner_9_c76b467b', '07': '__export__.res_partner_13_c4479a82', '08': '__export__.res_partner_14_16f00b8e'}
        tag5_data = { '01': '__export__.account_analytic_tag_S5_01', '02': '__export__.account_analytic_tag_S5_02', '03': '__export__.account_analytic_tag_S5_03', '04': '__export__.account_analytic_tag_S5_04', '05': '__export__.account_analytic_tag_S5_05', '06': '__export__.account_analytic_tag_S5_06', '07': '__export__.account_analytic_tag_S5_07', '08': '__export__.account_analytic_tag_S5_08', '09': '__export__.account_analytic_tag_S5_09' }
        meses = {'ene': '01','feb': '02','mar': '03','abr': '04','may': '05','jun': '06','jul': '07','ago': '08','sep': '09','oct': '10','nov': '11','dic': '12'}
        anio = {'17': '2017', '18': '2018', '2018': '2018', '19': '2019', '2019': '2019', '20': '2020', '2020': '2020', '21': '2021', '2021': '2021'}

        AnalyticIds, AccountAnalyticIds, AccountAccountIds, UserTypeIds = {}, {}, {}, {}
        for line in Analytic.search_read([], ['id', 'name', 'code']):
            AnalyticIds[line.get('code', '')] = line
        for line in AccountAnalytic.search_read([], ['id', 'name', 'code']):
            AccountAnalyticIds[line.get('code', '')] = line
        file_name = csv_file.replace(".dat", '').replace(".DAT", '')
        fileName = ""
        dictFile = {}
        fileTmp = None
        error_proceso = False
        cia_id = None

        resultFile = open("%s/%s"%(csv_path, csv_file), 'r', encoding="utf-8")
        for row_data in csv.reader(resultFile, delimiter='|'):
            fileNameTmp = "%s%s%s"%(file_name, row_data[6], row_data[2].replace('-', ''))
            if fileNameTmp != fileName:
                try:
                    cia_code = row_data[8].zfill(2)
                    cia_id = this.env.ref( cia_data.get( cia_code ))
                except:
                    error_proceso = True
                    break
                try:
                    journal_name = row_data[6]
                    journal_dict = Journal.search_read([('name', '=', '%s'%journal_name), ('company_id', '=', cia_id.id)], ['id', 'name', 'code'], limit=1)
                    result_journal_id = '%s'%(journal_dict and journal_dict[0].get('id') or '')
                except:
                    error_proceso = True
                    break
                fileName = fileNameTmp
                if fileTmp != None:
                    fileTmp.close()
                tmpimport = '%s/tmpimport/%s.csv'%(csv_path, fileName)
                fileTmp = open(tmpimport, 'a', encoding="utf-8", newline='')
                dictFile[fileNameTmp] = {
                    'file_name': file_name,
                    'file_dir': tmpimport,
                    'journal_name': journal_name,
                    'journal_id': result_journal_id,
                    'cia_code': cia_code,
                    'cia_id': cia_id.id,
                    'nolines': 0
                }
            try:
                cta_code = row_data and row_data[9] or ''
                if cta_code not in AccountAccountIds:
                    acc_id = Account.search_read([('deprecated', '=', False), ('company_id', '=', cia_id.id), ("code_alias", "=", cta_code)], fields=['id', 'name', 'code_alias', 'user_type_id'], limit=1)
                    if not acc_id:
                        AccountAccountIds = {}
                        error_proceso = True
                        break
                    else:
                        for acc in acc_id:
                            AccountAccountIds[ cta_code ] = acc
                            UserTypeIds[ acc.get("id") ] = acc.get('user_type_id') and acc['user_type_id'][0] or False
            except:
                error_proceso = True
                break
            debit = float(row_data and row_data[14] or '0.0')
            credit = float(row_data and row_data[15] or '0.0')
            if debit != 0.0 and credit != 0.0:
                dictFile[fileNameTmp]
                row_data_tmp = list(row_data)
                row_data_tmp[15] = '0.0'
                wr = csv.writer(fileTmp, dialect='excel', delimiter ='|')
                wr.writerow(row_data_tmp)
                row_data[14] = '0.0'
                dictFile[fileNameTmp]['nolines'] += 1
            wr = csv.writer(fileTmp, dialect='excel', delimiter ='|')
            wr.writerow(row_data)
            dictFile[fileNameTmp]['nolines'] += 1
        if fileTmp != None:
            fileTmp.close()
        resultFile.close()
        """
        dictFile = {
            'FRDGLIMPPOL20190417110050LAKIN05DIC19': {
                'file_name': 'FRDGLIMPPOL20190417110050', 
                'file_dir': '/tmp/mdm_tmpsftp_import_6/tmpimport/FRDGLIMPPOL20190417110050LAKIN05DIC19.csv', 
                'journal_name': 'LAKIN', 
                'journal_id': '51', 
                'cia_code': '01', 
                'cia_id': 1, 
                'nolines': 4
            }
        }
        """
        result = {
            'header': [],
            'body': [],
            'error_proceso': error_proceso
        }
        dict_datas = {}
        _logger.info("------- Error_Proceso %s"%error_proceso )
        if error_proceso == False:
            for fileName in dictFile:
                cia_id = dictFile[fileName].get('cia_id') or ''
                file_dir = dictFile[fileName].get('file_dir') or ''
                result_journal_id = dictFile[fileName].get('journal_id') or ''
                journal_name = dictFile[fileName].get('journal_name') or ''

                csvfile = open(file_dir, encoding="utf-8")
                spamreader = csv.reader(csvfile, delimiter='|')
                row_datas = list(spamreader)
                csvfile.close()
                if cia_id and result_journal_id and journal_name not in ['CREDENCIALBANCO']:
                    cia_id = ResCompany.browse(cia_id)
                    move_id = ""
                    for row_data in row_datas:
                        debit, credit = 0.0, 0.0
                        ledger_code = row_data and row_data[1] or ''
                        fecha = row_data and row_data[2] or ''
                        currency_code = row_data and row_data[3] or ''
                        journal_name_tmp = row_data and row_data[6] or ''
                        amount_currency = row_data and row_data[7] or ''
                        company_code = row_data and row_data[8] or '01'
                        cta_code = row_data and row_data[9] or ''
                        tag3 = row_data and row_data[10].zfill(4) or '0000'          # Localidad
                        tag4 = row_data and row_data[11].zfill(4) or '0000'          # Centro de Costos
                        tag5 = row_data and row_data[12].zfill(4) or '00'            # Interco
                        tag6 = row_data and row_data[13].zfill(4) or '0000'          # Futuro
                        cargos = float(row_data and row_data[14] or '0.0')
                        abonos = float(row_data and row_data[15] or '0.0')

                        if cargos == 0.0:
                            if abonos < 0.0:
                                debit = abs(abonos)
                        else:
                            if cargos > 0:
                                debit = cargos
                            else:
                                if cargos < 0:
                                    debit = 0
                        if abonos == 0.0:
                            if cargos < 0.0:
                                credit = abs(cargos)
                        else:
                            if abonos > 0.0:
                                credit = abonos
                            else:
                                if abonos < 0.0:
                                    credit = 0.0

                        analitica = 'C%s'%(tag4) if tag3 == '0000' else 'L%s'%(tag3)
                        tag3_id = AnalyticIds.get('L%s'%(tag3)) or {}
                        tag4_id = AnalyticIds.get('C%s'%(tag4)) or {}
                        tag6_id = AnalyticIds.get('F%s'%(tag6)) or {}
                        analitic_id = AccountAnalyticIds.get(analitica) or {}

                        result_name = row_data and row_data[16] or 'S/R'
                        result_ref =  '%s %s'%( (row_data and row_data[5]), (row_data and row_data[6]) )
                        result_linename = '%s'%(row_data and row_data[19] or '')
                        result_lineaccount_id = AccountAccountIds.get(cta_code) or '\\N'
                        result_linecurrency_id = '' if currency_code == 'MXN' else currency_code
                        result_lineamountcurrency = amount_currency if amount_currency.strip() != '' else ''
                        result_linedebit = '%s'%debit
                        result_linecredit = '%s'%credit
                        result_linetag3 = '%s'%(tag3_id.get('id') or '\\N')
                        result_linetag4 = '%s'%(tag4_id.get('id') or '\\N')
                        result_linetag5 = '%s'%(tag5_data.get( tag5 ) or '\\N')
                        result_linetag6 = '%s'%(tag6_id.get('id') or '\\N')
                        result_lineanalityc = '%s'%(analitic_id.get('id') or '\\N')
                        result_user_type_id = UserTypeIds.get( result_lineaccount_id.get('id') ) or '\\N'
                        string_date = fecha.lower().split('-')
                        if len(string_date[0])==4:
                            result_date = fecha
                        else:
                            result_date = '%s-%s-%s'%(anio.get(string_date[2]), meses.get(string_date[1]), string_date[0].zfill(2) )
                        result_linepartner = '' if tag5 == '00' else '%s'%cia_id.partner_id.id

                        indx = 0
                        external_id = '__export__.account_move_%s%s%s%s%s'%(result_date.replace('-', ''), company_code, result_name.replace('/', ''), ledger_code, journal_name)
                        if external_id not in dict_datas:
                            indx = 1
                            dict_datas[external_id] = {
                                'id': external_id,
                                'name': result_name,
                                'debit': 0.0,
                                'credit': 0.0,
                                'lines': []
                            }
                            move_header = ['id', 'name', 'date', 'ref', 'journal_id/.id']
                            move_body = [external_id, result_name, result_date, result_ref, result_journal_id]
                            res = AccountMove.load(move_header, [move_body])
                            _logger.info("----res %s "%res )
                            if res.get('ids'):
                                dict_datas[external_id]["db_id"] = res['ids'][0]
                                move_id = res['ids'][0]
                        dict_datas[external_id]['debit'] += debit
                        dict_datas[external_id]['credit'] += credit
                        lines_tmp = [
                            result_linename.replace("\\", "\\\\"),
                            result_linedebit,
                            result_linecredit,
                            (float(result_linedebit) - float(result_linecredit)),
                            result_linedebit,
                            result_linecredit,
                            (float(result_linedebit) - float(result_linecredit)),
                            cia_id.currency_id.id,
                            result_lineaccount_id.get("id"),
                            move_id,
                            result_ref,
                            0,
                            result_journal_id,
                            result_date,
                            result_date,
                            result_lineanalityc,
                            cia_id.id,
                            result_user_type_id,
                            result_linetag3 or '\\N',
                            result_linetag4 or '\\N',
                            result_linetag5 or '\\N',
                            result_linetag6 or '\\N',
                            result_linepartner or '\\N'
                        ]
                        dict_datas[external_id]['lines'] = lines_tmp
                        externalIdFile = open("%s/import/%s.csv"%(csv_path, external_id), 'a', encoding="utf-8", newline='')
                        if externalIdFile:
                            wr = csv.writer(externalIdFile, dialect='excel', delimiter ='|')
                            wr.writerow(lines_tmp)
                        externalIdFile.close()
                        _logger.info('Journal Items %s %s %s '%(external_id, file_name, result_linename) )
            for external_id in dict_datas:
                global_debit = dict_datas[external_id]['debit']
                global_credit = dict_datas[external_id]['credit']
                if global_debit != global_credit:
                    if global_debit > global_credit:
                        credit = round(abs(global_credit - global_debit), 2)
                        debit = 0.0
                    else:
                        debit = round(abs(global_debit - global_credit), 2)
                        credit = 0.0
                    line = dict_datas[external_id]['lines']
                    line_tmp = list(line)
                    line_tmp[0] = 'Ajuste Poliza'
                    line_tmp[1] = debit
                    line_tmp[2] = credit
                    line_tmp[3] = (float(debit) - float(credit))
                    line_tmp[4] = debit
                    line_tmp[5] = credit
                    line_tmp[6] = (float(debit) - float(credit))
                    line_tmp[8] = '%s'%(cia_id.account_import_id and cia_id.account_import_id.id or '')
                    line_tmp[15] = '\\N'
                    line_tmp[17] = cia_id.account_import_id.user_type_id.id
                    line_tmp[18] = '\\N'
                    line_tmp[19] = '\\N'
                    line_tmp[20] = '\\N'
                    line_tmp[21] = '\\N'
                    line_tmp[22] = '\\N'
                    externalIdFile = open("%s/import/%s.csv"%(csv_path, external_id), 'a', encoding="utf-8", newline='')
                    if externalIdFile:
                        wr = csv.writer(externalIdFile, dialect='excel', delimiter ='|')
                        wr.writerow(line_tmp)
                    externalIdFile.close()
                    _logger.info('Journal Items %s %s '%(file_name, 'Ajuste Poliza') )

                csv_path_file = "%s/import/%s.csv"%(csv_path, external_id)
                csv_header = "name, debit, credit, balance, debit_cash_basis, credit_cash_basis, balance_cash_basis, company_currency_id, account_id, move_id, ref, reconciled, journal_id, date_maturity, date, analytic_account_id, company_id, user_type_id, analytic_tag3_id, analytic_tag4_id, analytic_tag5_id, analytic_tag6_id, partner_id"
                this.run_loaddata_filesdat(use_new_cursor=use_new_cursor, csv_path=csv_path_file, csv_header=csv_header)






    """
    name, 
    debit, 
    credit, 
    balance, 
    debit_cash_basis, 
    credit_cash_basis, 
    balance_cash_basis, 
    company_currency_id, 
    account_id, 
    move_id, 
    ref, 
    reconciled, 
    journal_id, 
    date_maturity, 
    date, 
    analytic_account_id, 
    company_id, 
    user_type_id, 
    analytic_tag3_id, 
    analytic_tag4_id, 
    analytic_tag5_id, 
    analytic_tag6_id
    """