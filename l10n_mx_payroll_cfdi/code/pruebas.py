# -*- coding: utf-8 -*-




"""
Control de Cambios.
1. Nominas C99=0 cambiarlas a Done. 												OK
2. Nominas Especiales. No permitir crear dos veces el mismo registro.(Excel).		OK
3. Envio de Correos. Que no se envie a los seguidores.
4. Cambios PDF.
4. Envio de Correos. --- Campo Status send_email.
5. Envio de correos. --- Hacer Commit.


3. Crear opcion Generar dispersión de pagos. Seleccionar empleados
3. Nomina para empleados inactivos... Finiquitos
3. Enviar Mensajes al calcular la nomina.
4. Enviar Mensajes al Confirmar la nomina
5. Correr la nomina con OdooBot

# http://omawww.sat.gob.mx/tramitesyservicios/Paginas/documentos/GuiaNomina11102019.pdf

            # now1 = datetime.now()
            # self._actualizar_user(use_new_cursor=use_new_cursor, run_id=run_id)
            # self._enviar_msg(use_new_cursor=use_new_cursor, run_id=run_id, message_type='Inicia Calculo ', message_post='%s '%( now1.strftime("%Y-%m-%d %H:%M:%S") )  )
            # self._enviar_msg(use_new_cursor=use_new_cursor, run_id=run_id, message_type='Termina Calculo ', message_post='%s '%( now2.strftime("%Y-%m-%d %H:%M:%S") )  )



    #---------------------------------------
    #  Caclular Nominas
    #---------------------------------------
    @api.model
    def _compute_sheet_run_task_payslip(self, use_new_cursor=False, active_id=False):
        if use_new_cursor:
            cr = registry(self._cr.dbname).cursor()
            self = self.with_env(self.env(cr=cr))
            _logger.info('------ Calcular Nomina %s '%(active_id) )
            payslipModel = self.env['hr.payslip'].browse(active_id).compute_sheet()
            if use_new_cursor:
                cr.commit()
        return {}
    @api.model
    def _compute_sheet_run_task(self, use_new_cursor=False, active_id=False):
        try:
            if use_new_cursor:
                cr = registry(self._cr.dbname).cursor()
                self = self.with_env(self.env(cr=cr))  # TDE FIXME
            runModel = self.env['hr.payslip.run']
            payslipModel = self.env['hr.payslip']
            for run_id in runModel.browse(active_id):
                # Prueba escribir chat
                # run_id.write_msg(use_new_cursor=use_new_cursor, active_id=run_id.id)
                for payslip in payslipModel.search([('state', '=', 'draft'), ('payslip_run_id', '=', run_id.id)]):
                    run_id._compute_sheet_run_task_payslip(use_new_cursor=use_new_cursor, active_id=payslip.id)
                # run_id.sendMsgChannel(body='Finaliza proceso Calcular %s '%( run_id.name ) )
        finally:
            if use_new_cursor:
                try:
                    self._cr.close()
                except Exception:
                    pass
        return {}
    def _compute_sheet_run_threading(self, active_id):
        with api.Environment.manage():
            new_cr = self.pool.cursor()
            self = self.with_env(self.env(cr=new_cr))
            self.env['hr.payslip.run']._compute_sheet_run_task(use_new_cursor=self._cr.dbname, active_id=active_id)
            new_cr.close()
        return {}
    @api.multi
    def cumpute_sheet_run(self):
        for run_id in self:
            threaded_calculation = threading.Thread(target=self._compute_sheet_run_threading, args=(run_id.id, ), name='calcularrunid_%s'%run_id.id)
            threaded_calculation.start()
        return {}



    #---------------------------------------
    #  Confirmar Nominas
    #---------------------------------------
    @api.model
    def _confirm_sheet_run_task(self, use_new_cursor=False, active_id=False):
        try:
            if use_new_cursor:
                cr = registry(self._cr.dbname).cursor()
                self = self.with_env(self.env(cr=cr))  # TDE FIXME
            runModel = self.env['hr.payslip.run']
            payslipModel = self.env['hr.payslip']
            for run_id in runModel.browse(active_id):
                for payslip in payslipModel.search([('state', 'in', ['draft','verify']), ('payslip_run_id', '=', run_id.id)]):
                    try:
                        _logger.info('------- Payslip Done %s '%(payslip.id) )
                        payslip.with_context(without_compute_sheet=True).action_payslip_done()
                    except Exception as e:
                        payslip.message_post(body='Error Al timbrar la Nomina: %s '%( e ) )
                        _logger.info('------ Error Al timbrar  la Nomina %s '%( e ) )
                    if use_new_cursor:
                        self._cr.commit()
        finally:
            if use_new_cursor:
                try:
                    self._cr.close()
                except Exception:
                    pass
        return {}
    def _confirm_sheet_run_threading(self, active_id):
        with api.Environment.manage():
            new_cr = self.pool.cursor()
            self = self.with_env(self.env(cr=new_cr))
            self.env['hr.payslip.run']._confirm_sheet_run_task(use_new_cursor=self._cr.dbname, active_id=active_id)
            new_cr.close()
        return {}
    @api.multi
    def confirm_sheet_run(self):
        for run_id in self:
            threaded_calculation = threading.Thread(target=run_id._confirm_sheet_run_threading, args=([run_id.id]), name='timbrarrunid_%s'%run_id.id)
            threaded_calculation.start()
        return {}



    #---------------------------------------
    #  Enviar Nominas
    #---------------------------------------
    @api.model
    def _enviar_nomina_threading_task(self, use_new_cursor=False, active_id=False):
        try:
            if use_new_cursor:
                cr = registry(self._cr.dbname).cursor()
                self = self.with_env(self.env(cr=cr))  # TDE FIXME
            ctx = self._context.copy()
            template = self.env.ref('l10n_mx_payroll_cfdi.email_template_payroll', False)
            runModel = self.env['hr.payslip.run']
            payslipModel = self.env['hr.payslip']
            mailModel = self.env['mail.compose.message']
            for run_id in runModel.browse(active_id):
                for payslip in payslipModel.search([('state', '=', 'done'), ('payslip_run_id', '=', run_id.id)]):
                    try:
                        if payslip.l10n_mx_edi_cfdi_uuid and payslip.employee_id.address_home_id.email:
                            _logger.info('------- Payslip Email %s '%(payslip.id) )
                            ctx.update({
                                'default_model': 'hr.payslip',
                                'default_res_id': payslip.id,
                                'default_use_template': bool(template),
                                'default_template_id': template.id,
                                'default_composition_mode': 'comment',
                                'mail_create_nosubscribe': True
                            })
                            vals = mailModel.onchange_template_id(template.id, 'comment', 'hr.payslip', payslip.id)
                            mail_message  = mailModel.with_context(ctx).create(vals.get('value',{}))
                            mail_message.action_send_mail()
                    except Exception as e:
                        payslip.message_post(body='Error Al enviar Email Nomina: %s '%( e ) )
                        _logger.info('------ Error Al enviar Email Nomina %s '%( e ) )
                    if use_new_cursor:
                        self._cr.commit()
        finally:
            if use_new_cursor:
                try:
                    self._cr.close()
                except Exception:
                    pass
        return {}
    def _enviar_nomina_threading(self, active_id):
        with api.Environment.manage():
            new_cr = self.pool.cursor()
            self = self.with_env(self.env(cr=new_cr))
            self.env['hr.payslip.run']._enviar_nomina_threading_task(use_new_cursor=self._cr.dbname, active_id=active_id)
            new_cr.close()
        return {}
    @api.multi
    def enviar_nomina(self):
        for run_id in self:
            threaded_calculation = threading.Thread(target=self._enviar_nomina_threading, args=(run_id.id, ), name='enviarnominarunid_%s'%run_id.id)
            threaded_calculation.start()
        return {}




    #---------------------------------------
    #  Generar Nominas
    #---------------------------------------
    @api.model
    def _run_compute_sheet_tasks(self, use_new_cursor=False, active_id=False, from_date=False, to_date=False, credit_note=False, employee_ids=[]):
        try:
            if use_new_cursor:
                cr = registry(self._cr.dbname).cursor()
                self = self.with_env(self.env(cr=cr))  # TDE FIXME
            payslipModel = self.env['hr.payslip']
            payslips = []
            for employees_chunk in split_every(20, employee_ids):
                _logger.info('--- Nomina Procesando Employees %s', employees_chunk )
                for employee in self.env['hr.employee'].browse(employees_chunk):
                    slip_data = payslipModel.onchange_employee_id(from_date, to_date, employee.id, contract_id=False)
                    res = {
                        'employee_id': employee.id,
                        'name': slip_data['value'].get('name'),
                        'struct_id': slip_data['value'].get('struct_id'),
                        'contract_id': slip_data['value'].get('contract_id'),
                        'payslip_run_id': active_id,
                        'input_line_ids': [(0, 0, x) for x in slip_data['value'].get('input_line_ids')],
                        'worked_days_line_ids': [(0, 0, x) for x in slip_data['value'].get('worked_days_line_ids')],
                        'date_from': from_date,
                        'date_to': to_date,
                        'credit_note': credit_note,
                        'company_id': employee.company_id.id,
                        'cfdi_source_sncf': slip_data['value'].get('cfdi_source_sncf'),
                        'cfdi_amount_sncf': slip_data['value'].get('cfdi_amount_sncf'),
                        'cfdi_tipo_nomina': slip_data['value'].get('cfdi_tipo_nomina'),
                        'cfdi_tipo_nomina_especial': slip_data['value'].get('cfdi_tipo_nomina_especial')
                    }
                    payslip_id = payslipModel.create(res)
                    payslips.append(payslip_id.id)
                    if use_new_cursor:
                        self._cr.commit()
            _logger.info('--- Nomina payslips %s ', len(payslips) )
            for slip_chunk in split_every(5, payslips):
                _logger.info('--- Nomina payslip_ids %s ', slip_chunk )
                try:
                    payslipModel.with_context(slip_chunk=True).browse(slip_chunk).compute_sheet()
                    if use_new_cursor:
                        self._cr.commit()
                except:
                    pass
            if use_new_cursor:
                self._cr.commit()

        finally:
            if use_new_cursor:
                try:
                    self._cr.close()
                except Exception:
                    pass
        return {}
    def _compute_sheet_threading(self, active_id, from_date=False, to_date=False, credit_note=False, employee_ids=[]):
        with api.Environment.manage():
            new_cr = self.pool.cursor()
            self = self.with_env(self.env(cr=new_cr))
            self.env['hr.payslip.employees']._run_compute_sheet_tasks(
                use_new_cursor=self._cr.dbname,
                active_id=active_id, from_date=from_date, to_date=to_date, credit_note=credit_note, employee_ids=employee_ids)
            new_cr.close()
            return {}
    @api.multi
    def compute_sheet(self):
        [data] = self.read()
        if not data['employee_ids']:
            employees = self.with_context(active_test=False).employee_ids
            data['employee_ids'] = employees.ids
        active_id = self.env.context.get('active_id')
        if active_id:
            [run_data] = self.env['hr.payslip.run'].browse(active_id).read(['date_start', 'date_end', 'credit_note'])
        from_date = run_data.get('date_start')
        to_date = run_data.get('date_end')
        if not data['employee_ids']:
            raise UserError(_("You must select employee(s) to generate payslip(s)."))
        threaded_calculation = threading.Thread(target=self._compute_sheet_threading, args=( active_id, from_date, to_date, run_data.get('credit_note'), data['employee_ids'] ))
        threaded_calculation.start()
        return {'type': 'ir.actions.act_window_close'}



    #---------------------------------------
    #  Dispersion Nominas Banorte
    #---------------------------------------

            #---------------
            # Header Data 
            #---------------
            banco_header = run_id.company_id.clave_emisora or ''
            run_id.application_date_banorte or 'AAAAMMDD'
            date1 = run_id.application_date_banorte.strftime("%Y%m%d")
            indx = 0
            monto_banco = 0.0
            # ---------------
            # Detalle
            # ---------------
            res_banco_header, res_banco = [], []
            p_ids = run_id.slip_ids.filtered(lambda r: r.layout_nomina == 'banorte')
            _logger.info('---------- Layout Banorte %s '%( len(p_ids) ) )
            for slip in p_ids:
                total = slip.get_salary_line_total('C99')
                if total <= 0:
                    continue
                employee_id = slip.employee_id or False
                bank_account_id = employee_id.bank_account_id and slip.employee_id.bank_account_id or False
                if not bank_account_id:
                    continue
                bank_number = bank_account_id and bank_account_id.bank_id.bic or ''
                if not bank_number:
                    continue
                indx += 1
                bank_type = '01'
                if bank_number != '072':
                    bank_type = '40'
                cuenta = bank_account_id and bank_account_id.acc_number or ''
                cuenta = cuenta[ : len(cuenta) -1 ]
                cuenta = cuenta[-10:]
                monto_banco += total
                pp_total = '%.2f'%(total)
                pp_total = str(pp_total).replace('.', '')
                res_banco.append((
                    'D',
                    '%s'%( date1 ),
                    '%s'%( str( employee_id.cfdi_code_emp or '' ).rjust(10, "0") ),
                    '%s'%( str(' ').rjust(40, " ") ),
                    '%s'%( str(' ').rjust(40, " ") ),
                    '%s'%( pp_total.rjust(15, "0") ),
                    '%s'%( bank_number ),
                    '%s'%( bank_type ),
                    '%s'%( cuenta.rjust(18, "0") ),
                    '0',
                    ' ',
                    '00000000',
                    '%s'%( str(' ').rjust(18, " ") ),
                ))
            if res_banco:
                monto_banco = '%.2f'%(monto_banco)
                monto_banco = str(monto_banco).replace('.', '')
                res_banco_header = [(
                    'H',
                    'NE',
                    '%s'%( banco_header ),
                    '%s'%( date1 ),
                    '01',
                    '%s'%( str(indx).rjust(6, "0") ),
                    '%s'%( monto_banco.rjust(15, "0") ),
                    '000000',
                    '000000000000000',
                    '000000',
                    '000000000000000',
                    '000000',
                    '0',
                    '%s'%( str(' ').rjust(77, " ") )
                )]
            banco_datas = self._save_txt(res_banco_header + res_banco)
            return banco_datas


    #---------------------------------------
    #  Dispersion Nominas BBVA
    #---------------------------------------
    def dispersion_bbva_datas(self):
        for run_id in self:
            res_banco = []
            indx = 1
            p_ids = run_id.slip_ids.filtered(lambda r: r.layout_nomina == 'bbva')
            _logger.info('---------- Layout BBVA %s '%( len(p_ids) ) )
            for slip in p_ids:
                employee_id = slip.employee_id or False
                total = slip.get_salary_line_total('C99')
                if total <= 0:
                    _logger.info('---- Dispersion BBVA NO total=0 %s %s %s '%( slip.id, slip.number, employee_id.id ) )
                    continue
                bank_account_id = employee_id.bank_account_id and slip.employee_id.bank_account_id or False
                if not bank_account_id:
                    _logger.info('---- Dispersion BBVA NO bank_account_id %s %s %s '%( slip.id, slip.number, employee_id.id ) )
                    continue
                bank_number = bank_account_id and bank_account_id.bank_id.bic or ''
                cuenta = bank_account_id and bank_account_id.acc_number or ''
                if not cuenta:
                    _logger.info('---- Dispersion BBVA NO CUENTA%s %s %s '%( slip.id, slip.number, employee_id.id ) )
                    continue

                pp_total = '%.2f'%(total)
                pp_total = str(pp_total).replace('.', '')
                rfc = '%s'%('0').rjust(16, "0")
                # nombre = employee_id.cfdi_complete_name[:40]
                nombre = '%s %s %s'%( employee_id.cfdi_appat, employee_id.cfdi_apmat, employee_id.name )
                nombre = remove_accents(nombre[:40])
                res_banco.append((
                    '%s'%( str(indx).rjust(9, "0") ),
                    rfc,
                    '%s'%( '99' if bank_number == '012' else '40' ),
                    '%s'%( cuenta.ljust(20, " ") ),
                    '%s'%( pp_total.rjust(15, "0") ),
                    '%s'%( nombre.ljust(40, " ") ),
                    '001',
                    '001'
                ))
                indx += 1
            banco_datas = self._save_txt(res_banco)
            return banco_datas











http://0.0.0.0:8069/report/html/l10n_mx_payroll_cfdi.report_hr_payslip_mx/2





                        <!--
                        <tr>
                            <td style="text-align: right; "><b>Rfc Patron Origen: &amp;nbsp;</b></td>
                            <td style="text-align: left; margin-left: 5px; font-style: italic;">&amp;nbsp;<span t-esc="rec.get('RfcPatronOrigen')"/></td>
                            <td style="text-align: right; "><b>Origen Recurso: &amp;nbsp;</b></td>
                            <td style="text-align: left; margin-left: 5px; font-style: italic;">&amp;nbsp;<span t-esc="rec.get('OrigenRecurso')"/></td>
                            <td style="text-align: right; "><b>Monto Recurso Propio: &amp;nbsp;</b></td>
                            <td style="text-align: left; margin-right: 5px; font-style: italic;"><span t-esc="rec.get('MontoRecursoPropio')"/></td>
                        </tr>

                            <td style="text-align: right; "><b>Riesgo de puesto: &amp;nbsp;</b></td>
                            <td style="text-align: left; margin-left: 5px; font-style: italic;">&amp;nbsp;<span t-esc="rec.get('RiesgoPuesto')"/></td>
                            <td style="text-align: right; "><b>Tipo de contrato: &amp;nbsp;</b></td>
                            <td style="text-align: left; margin-left: 5px; font-style: italic;">&amp;nbsp;<span t-esc="rec.get('TipoContrato')"/></td>

                            <td style="text-align: right; "><b>Sindicalizado: &amp;nbsp;</b></td>
                            <td style="text-align: left; margin-left: 5px; font-style: italic;">&amp;nbsp;<span t-esc="rec.get('Sindicalizado')"/></td>
                            <td style="text-align: right; "><b>Tipo de jornada: &amp;nbsp;</b></td>
                            <td style="text-align: left; margin-left: 5px; font-style: italic;">&amp;nbsp;<span t-esc="rec.get('TipoJornada')"/></td>

                            <td style="text-align: right; "><b>Antigüedad: &amp;nbsp;</b></td>
                            <td style="text-align: left; margin-left: 5px; font-style: italic;">&amp;nbsp;<span t-esc="rec.get('Antiguedad')"/></td>

                            <td style="text-align: right; "><b>Inicio de la relación laboral: &amp;nbsp;</b></td>
                            <td style="text-align: left; margin-left: 5px; font-style: italic;">&amp;nbsp;<span t-esc="rec.get('FechaInicioRelLaboral')"/></td>

                            <td style="text-align: right; "><b>Salario Diario Integrado: &amp;nbsp;</b></td>
                            <td style="text-align: left; margin-left: 5px; font-style: italic;">&amp;nbsp;<span t-esc="rec.get('SalarioDiarioIntegrado')"/></td>

                            <td style="text-align: right; "><b>Clave Entidad Federativa: &amp;nbsp;</b></td>
                            <td style="text-align: left; margin-left: 5px; font-style: italic;">&amp;nbsp;<span t-esc="rec.get('ClaveEntFed')"/></td>

                            <td style="text-align: right; "><b>SalarioBaseCotApor: &amp;nbsp;</b></td>
                            <td style="text-align: left; margin-left: 5px; font-style: italic;">&amp;nbsp;<span t-esc="rec.get('SalarioBaseCotApor')"/></td>

                            <td style="text-align: right; "><b>Banco: &amp;nbsp;</b></td>
                            <td style="text-align: left; margin-left: 5px; font-style: italic;">&amp;nbsp;<span t-esc="rec.get('Banco')"/></td>
                            <td style="text-align: right; "><b>Cuenta Bancaria: &amp;nbsp;</b></td>
                            <td style="text-align: left; margin-left: 5px; font-style: italic;">&amp;nbsp;<span t-esc="rec.get('CuentaBancaria')"/></td>

                        -->

        <template id="report_hr_payslip_mx_document_old">
            <t t-call="l10n_mx_payroll_cfdi.nomina_external_layout">
                <div class="page">
                    <t t-set="rec" t-value="o and o.getDatasXmlPayslip() or {}"/>
                    <br />
                    <table class="info" style="width: 100%; font-size: 10px;">
                        <tr>
                            <td style="background-color: #EEE !important;"><span>Lugar de expedición: &amp;nbsp;</span></td>
                            <td style="text-align: left;">&amp;nbsp;<span t-esc="rec.get('LugarExpedicion')"/></td>
                            <td style="background-color: #EEE !important;"><span>Método de pago: &amp;nbsp;</span></td>
                            <td style="text-align: left;">&amp;nbsp;<span t-esc="rec.get('MetodoPago')"/></td>
                            <td style="background-color: #EEE !important;"><span>No. de Certificado: &amp;nbsp;</span></td>
                            <td style="text-align: left;">&amp;nbsp;<span t-esc="rec.get('NoCertificado')"/></td>
                        </tr>
                        <tr>
                            <td style="background-color: #EEE !important;"><span>Fecha de expedición: &amp;nbsp;</span></td>
                            <td style="text-align: left;">&amp;nbsp;<span t-esc="rec.get('Fecha')"/></td>
                            <td style="background-color: #EEE !important;"><span>Forma de Pago: &amp;nbsp;</span></td>
                            <td style="text-align: left;">&amp;nbsp;<span t-esc="rec.get('FormaPago')"/></td>
                            <td style="background-color: #EEE !important;"><span>Serie y Folio: &amp;nbsp;</span></td>
                            <td style="text-align: left;">&amp;nbsp;<span t-esc="rec.get('Serie')"/> <span t-esc="rec.get('Folio')"/> </td>
                        </tr>
                        <tr>
                            <td style="background-color: #EEE !important;"><span>RFC: &amp;nbsp;</span></td>
                            <td style="text-align: left;">&amp;nbsp;<span t-esc="rec.get('EmisorRfc')"/></td>
                            <td style="background-color: #EEE !important;"><span>Régimen fiscal: &amp;nbsp;</span></td>
                            <td style="text-align: left;">&amp;nbsp;<span t-esc="rec.get('RegimenFiscal', '')"/></td>
                            <td style="background-color: #EEE !important;"><span> &amp;nbsp;</span></td>
                            <td style="text-align: left;">&amp;nbsp; </td>
                        </tr>
                    </table>
                    <table class="info" style="width: 100%; font-size: 10px;">
                        <tr>
                            <td colspan="6"><span style="font-size: 12px;"><b>RECIBO DE NÓMINA</b></span></td>
                        </tr>
                        <tr>
                            <td style="text-align: right; "><b>Nombre del Empleado: &amp;nbsp;</b></td>
                            <td colspan="5" style="text-align: left; margin-right: 5px; font-style: italic;">&amp;nbsp;<span t-esc="o.employee_id.cfdi_complete_name" /></td>
                        </tr>
                        <tr>
                            <td style="text-align: right; "><b>RFC: &amp;nbsp;</b></td>
                            <td style="text-align: left; margin-right: 5px; font-style: italic;">&amp;nbsp;<span t-esc="rec.get('ReceptorRfc', '')"/></td>
                            <td style="text-align: right; "><b>CURP: &amp;nbsp;</b></td>
                            <td style="text-align: left; margin-right: 5px; font-style: italic;">&amp;nbsp;<span t-esc="rec.get('ReceptorCurp')"/></td>
                            <td style="text-align: right; "><b>Registro patronal: &amp;nbsp;</b></td>
                            <td style="text-align: left; margin-right: 5px; font-style: italic;">&amp;nbsp;<span t-esc="rec.get('RegistroPatronal')"/></td>
                        </tr>

                        <tr>
                            <td style="text-align: right; "><b>Número de empleado: &amp;nbsp;</b></td>
                            <td style="text-align: left; margin-left: 5px; font-style: italic;">&amp;nbsp;<span t-esc="rec.get('NumEmpleado')"/></td>
                            <td style="text-align: right; "><b>Tipo de régimen: &amp;nbsp;</b></td>
                            <td style="text-align: left; margin-left: 5px; font-style: italic;">&amp;nbsp;<span t-esc="rec.get('TipoRegimen')"/></td>
                            <td style="text-align: right; "><b>Departamento: &amp;nbsp;</b></td>
                            <td style="text-align: left; margin-left: 5px; font-style: italic;">&amp;nbsp;<span t-esc="rec.get('Departamento')"/></td>
                        </tr>
                        <tr>
                            <td style="text-align: right; "><b>Fecha de pago: &amp;nbsp;</b></td>
                            <td style="text-align: left; margin-left: 5px; font-style: italic;">&amp;nbsp;<span t-esc="rec.get('FechaPago')"/></td>
                            <td style="text-align: right; "><b>Fecha inicial de pago: &amp;nbsp;</b></td>
                            <td style="text-align: left; margin-left: 5px; font-style: italic;">&amp;nbsp;<span t-esc="rec.get('FechaInicialPago')"/></td>
                            <td style="text-align: right; "><b>Fecha final de pago: &amp;nbsp;</b></td>
                            <td style="text-align: left; margin-left: 5px; font-style: italic;">&amp;nbsp;<span t-esc="rec.get('FechaFinalPago')"/></td>
                        </tr>
                        <tr>
                            <td style="text-align: right; "><b>Total Percepciones: &amp;nbsp;</b></td>
                            <td style="text-align: left; margin-left: 5px; font-style: italic;">&amp;nbsp;<span t-esc="rec.get('TotalPercepciones')"/></td>
                            <td style="text-align: right; "><b>Total Deducciones: &amp;nbsp;</b></td>
                            <td style="text-align: left; margin-left: 5px; font-style: italic;">&amp;nbsp;<span t-esc="rec.get('TotalDeducciones')"/></td>
                            <td style="text-align: right; "><b>Total Otros Pagos: &amp;nbsp;</b></td>
                            <td style="text-align: left; margin-left: 5px; font-style: italic;">&amp;nbsp;<span t-esc="rec.get('TotalOtrosPagos')"/></td>
                        </tr>
                        <tr>
                            <td style="text-align: right; "><b>Puesto: &amp;nbsp;</b></td>
                            <td style="text-align: left; margin-left: 5px; font-style: italic;">&amp;nbsp;<span t-esc="rec.get('Puesto')"/></td>
                            <td style="text-align: right; "><b>Número de días pagados: &amp;nbsp;</b></td>
                            <td style="text-align: left; margin-left: 5px; font-style: italic;">&amp;nbsp;<span t-esc="rec.get('NumDiasPagados')"/></td>
                            <td style="text-align: right; "><b>Periodicidad de pago: &amp;nbsp;</b></td>
                            <td style="text-align: left; margin-left: 5px; font-style: italic;">&amp;nbsp;<span t-esc="rec.get('PeriodicidadPago')"/></td>
                        </tr>
                        <tr>
                            <td style="text-align: right; "><b>NSS: &amp;nbsp;</b></td>
                            <td style="text-align: left; margin-left: 5px; font-style: italic;">&amp;nbsp;<span t-esc="rec.get('NumSeguridadSocial')"/></td>
                            <td style="text-align: right; "><b>Tipo Nomina: &amp;nbsp;</b></td>
                            <td style="text-align: left; margin-left: 5px; font-style: italic;">&amp;nbsp;<span t-esc="rec.get('TipoNomina')"/></td>
                            <td><span> </span></td>
                            <td><span> </span></td>
                        </tr>
                    </table>
                    <table class="info" style="width: 100%; font-size: 10px;">
                        <tr>
                            <td colspan="7"><span style="font-size: 14px;"><strong>Percepciones:</strong></span></td>
                        </tr>
                        <tr style="background-color: #EEE !important;">
                            <td style="text-align: center; vertical-align:top; border-left: 1px solid #BDBDBD !important; border-top: 1px solid #BDBDBD !important; border-bottom: 1px solid #BDBDBD !important; ">
                                <strong>No.</strong>
                            </td>
                            <td style="text-align: center; vertical-align:top; border-top: 1px solid #BDBDBD !important; !important; border-bottom: 1px solid #BDBDBD !important;">
                                <strong>Tipo de percepción.</strong>
                            </td>
                            <td style="text-align: center; vertical-align:top; border-top: 1px solid #BDBDBD !important; !important; border-bottom: 1px solid #BDBDBD !important;">
                                <strong>Clave.</strong>
                            </td>
                            <td style="text-align: center; vertical-align:top; border-top: 1px solid #BDBDBD !important; !important; border-bottom: 1px solid #BDBDBD !important;">
                                <strong>Concepto.</strong>
                            </td>
                            <td style="text-align: center; vertical-align:top; border-top: 1px solid #BDBDBD !important; !important; border-bottom: 1px solid #BDBDBD !important;">
                                <strong>Sueldos.</strong>
                            </td>
                            <td style="text-align: center; vertical-align:top; border-top: 1px solid #BDBDBD !important; !important; border-bottom: 1px solid #BDBDBD !important;">
                                <strong>Gravado.</strong>
                            </td>
                            <td style="text-align: center; vertical-align:top; border-right: 1px solid #BDBDBD !important; border-top: 1px solid #BDBDBD !important; border-bottom: 1px solid #BDBDBD !important;">
                                <strong>Exento.</strong>
                            </td>
                        </tr>
                        <t t-set="pl" t-value="rec.get('Percepciones') and rec['Percepciones'].get('Lines') or [] "/>
                        <t t-set="TotalSueldos" t-value="rec.get('Percepciones') and rec['Percepciones'].get('TotalSueldos') or 0.0 "/>
                        <t t-set="TotalGravado" t-value="rec.get('Percepciones') and rec['Percepciones'].get('TotalGravado') or 0.0 "/>
                        <t t-set="TotalExento" t-value="rec.get('Percepciones') and rec['Percepciones'].get('TotalExento') or 0.0 "/>
                        <t t-foreach="pl" t-as="l">
                            <tr>
                                <td style="vertical-align:top; border-left: 1px solid #BDBDBD !important;">&amp;nbsp;<span t-esc="l.get('indx')"/></td>
                                <td>&amp;nbsp;<span t-esc="l.get('TipoPercepcion')"/></td>
                                <td>&amp;nbsp;<span t-esc="l.get('Clave')"/></td>
                                <td>&amp;nbsp;<span t-esc="l.get('Concepto')"/></td>
                                <td>&amp;nbsp; </td>
                                <td style="vertical-align:top; text-align: center;">
                                    &amp;nbsp;<span t-esc="l.get('ImporteGravado')" t-options='{"widget": "monetary", "display_currency": o.currency_id}'/>
                                </td>
                                <td style="vertical-align:top; border-right: 1px solid #BDBDBD !important; text-align: center;">
                                    &amp;nbsp;<span t-esc="l.get('ImporteExento')" t-options='{"widget": "monetary", "display_currency": o.currency_id}'/>
                                </td>
                            </tr>
                        </t>
                        <tr>
                            <td style="vertical-align:top; border-left: 1px solid #BDBDBD !important; border-top: 1px solid #BDBDBD !important; border-bottom: 1px solid #BDBDBD !important; ">
                                &amp;nbsp;
                            </td>
                            <td style="border-top: 1px solid #BDBDBD !important; border-bottom: 1px solid #BDBDBD !important; ">
                                &amp;nbsp;
                            </td>
                            <td style="border-top: 1px solid #BDBDBD !important; border-bottom: 1px solid #BDBDBD !important; ">
                                &amp;nbsp;
                            </td>
                            <td style="border-top: 1px solid #BDBDBD !important; border-bottom: 1px solid #BDBDBD !important; ">
                                &amp;nbsp;
                            </td>
                            <td style="text-align: center; border-top: 1px solid #BDBDBD !important; border-bottom: 1px solid #BDBDBD !important; ">
                                &amp;nbsp;<b t-esc="float(TotalSueldos)" t-options='{"widget": "monetary", "display_currency": o.currency_id}'/>
                            </td>
                            <td style="text-align: center; border-top: 1px solid #BDBDBD !important; border-bottom: 1px solid #BDBDBD !important; ">
                                &amp;nbsp;<b t-esc="float(TotalGravado)" t-options='{"widget": "monetary", "display_currency": o.currency_id}'/>
                            </td>
                            <td style="vertical-align:top; text-align: center; border-right: 1px solid #BDBDBD !important; border-top: 1px solid #BDBDBD !important; border-bottom: 1px solid #BDBDBD !important; ">
                                &amp;nbsp;<b t-esc="float(TotalExento)" t-options='{"widget": "monetary", "display_currency": o.currency_id}'/>
                            </td>
                        </tr>
                    </table>
                    <br />
                    <table class="info" style="width: 100%; font-size: 10px;">
                        <tr>
                            <td colspan="7"><span style="font-size: 14px;"><strong>Deducciones:</strong></span></td>
                        </tr>
                        <tr style="background-color: #EEE !important;">
                            <td style="text-align: center; vertical-align:top; border-left: 1px solid #BDBDBD !important; border-top: 1px solid #BDBDBD !important; border-bottom: 1px solid #BDBDBD !important; ">
                                <strong>Tipo de deducción.</strong>
                            </td>
                            <td style="text-align: center; vertical-align:top; border-top: 1px solid #BDBDBD !important; !important; border-bottom: 1px solid #BDBDBD !important; ">
                                <strong>Clave.</strong>
                            </td>
                            <td style="text-align: center; vertical-align:top; border-top: 1px solid #BDBDBD !important; !important; border-bottom: 1px solid #BDBDBD !important; ">
                                <strong>Concepto.</strong>
                            </td>
                            <td style="text-align: center; vertical-align:top; border-top: 1px solid #BDBDBD !important; !important; border-bottom: 1px solid #BDBDBD !important; ">
                                <strong>Importe.</strong>
                            </td>
                            <td style="text-align: center; vertical-align:top; border-top: 1px solid #BDBDBD !important; !important; border-bottom: 1px solid #BDBDBD !important; ">
                                <strong>Otras Deduc.</strong>
                            </td>
                            <td style="text-align: center; vertical-align:top; border-right: 1px solid #BDBDBD !important; border-top: 1px solid #BDBDBD !important; border-bottom: 1px solid #BDBDBD !important; ">
                                <strong>Impuestos Ret.</strong>
                            </td>
                        </tr>
                        <t t-set="dl" t-value="rec.get('Deducciones') and rec['Deducciones'].get('Lines') or [] "/>
                        <t t-set="TotalOtrasDeducciones" t-value="rec.get('Deducciones') and rec['Deducciones'].get('TotalOtrasDeducciones') or 0.0 "/>
                        <t t-set="TotalImpuestosRetenidos" t-value="rec.get('Deducciones') and rec['Deducciones'].get('TotalImpuestosRetenidos') or 0.0 "/>
                        <t t-set="TotalImporte" t-value="rec.get('Deducciones') and rec['Deducciones'].get('TotalImporte') or 0.0 "/>
                        <t t-foreach="dl" t-as="d">
                            <tr>
                                <td style="vertical-align:top; border-left: 1px solid #BDBDBD !important;">
                                    &amp;nbsp;<span t-esc="d.get('TipoDeduccion')"/>
                                </td>
                                <td>
                                    &amp;nbsp;<span t-esc="d.get('Clave')"/>
                                </td>
                                <td>
                                    &amp;nbsp;<span t-esc="d.get('Concepto')"/>
                                </td>
                                <td style="text-align: center; vertical-align:top; ">
                                    &amp;nbsp;<span t-esc="d.get('Importe')" t-options='{"widget": "monetary", "display_currency": o.currency_id}'/>
                                </td>
                                <td>&amp;nbsp;</td>
                                <td style="vertical-align:top; border-right: 1px solid #BDBDBD !important;">
                                    &amp;nbsp;
                                </td>
                            </tr>
                        </t>
                        <tr>
                            <td style="vertical-align:top; border-left: 1px solid #BDBDBD !important; border-top: 1px solid #BDBDBD !important; border-bottom: 1px solid #BDBDBD !important; ">
                                &amp;nbsp;
                            </td>
                            <td style="vertical-align:top; border-top: 1px solid #BDBDBD !important; !important; border-bottom: 1px solid #BDBDBD !important; ">
                                &amp;nbsp;
                            </td>
                            <td style="vertical-align:top; border-top: 1px solid #BDBDBD !important; !important; border-bottom: 1px solid #BDBDBD !important; ">
                                &amp;nbsp;
                            </td>
                            <td style="text-align: center; vertical-align:top; border-top: 1px solid #BDBDBD !important; !important; border-bottom: 1px solid #BDBDBD !important; ">
                                &amp;nbsp;<b t-esc="TotalImporte" t-options='{"widget": "monetary", "display_currency": o.currency_id}'/>
                            </td>
                            <td style="text-align: center; vertical-align:top; border-top: 1px solid #BDBDBD !important; !important; border-bottom: 1px solid #BDBDBD !important; ">
                                &amp;nbsp;<b t-esc="TotalOtrasDeducciones" t-options='{"widget": "monetary", "display_currency": o.currency_id}'/>
                            </td>
                            <td style="text-align: center; vertical-align:top; border-right: 1px solid #BDBDBD !important; border-top: 1px solid #BDBDBD !important; border-bottom: 1px solid #BDBDBD !important; ">
                                &amp;nbsp;<b t-esc="TotalImpuestosRetenidos" t-options='{"widget": "monetary", "display_currency": o.currency_id}'/>
                            </td>
                        </tr>
                    </table>
                    <br />
                    <table class="info" style="width: 100%; font-size: 10px;">
                        <tr>
                            <td colspan="7"><span style="font-size: 14px;"><strong>Otros Pagos:</strong></span></td>
                        </tr>
                        <tr style="background-color: #EEE !important;">
                            <td style="text-align: center; vertical-align:top; border-left: 1px solid #BDBDBD !important; border-top: 1px solid #BDBDBD !important; border-bottom: 1px solid #BDBDBD !important; ">
                                <strong>No.</strong>
                            </td>
                            <td style="text-align: center; vertical-align:top; border-top: 1px solid #BDBDBD !important; !important; border-bottom: 1px solid #BDBDBD !important; ">
                                <strong>Tipo.</strong>
                            </td>
                            <td style="text-align: center; vertical-align:top; border-top: 1px solid #BDBDBD !important; !important; border-bottom: 1px solid #BDBDBD !important; ">
                                <strong>Clave.</strong>
                            </td>
                            <td style="text-align: center; vertical-align:top; border-top: 1px solid #BDBDBD !important; !important; border-bottom: 1px solid #BDBDBD !important; ">
                                <strong>Concepto.</strong>
                            </td>
                            <td style="text-align: center; vertical-align:top; border-right: 1px solid #BDBDBD !important; border-top: 1px solid #BDBDBD !important; border-bottom: 1px solid #BDBDBD !important; ">
                                <strong>Importe.</strong>
                            </td>
                        </tr>
                        <t t-set="ol" t-value="rec.get('OtrosPagos') and rec['OtrosPagos'] or [] "/>
                        <t t-foreach="ol" t-as="l">
                            <tr>
                                <td style="vertical-align:top; border-left: 1px solid #BDBDBD !important; border-bottom: 1px solid #BDBDBD !important;">
                                    &amp;nbsp;<span t-esc="l.get('indx')"/>
                                </td>
                                <td style="border-bottom: 1px solid #BDBDBD !important;">
                                    &amp;nbsp;<span t-esc="l.get('TipoOtroPago')"/>
                                </td>
                                <td style="border-bottom: 1px solid #BDBDBD !important;">
                                    &amp;nbsp;<span t-esc="l.get('Clave')"/>
                                </td>
                                <td style="border-bottom: 1px solid #BDBDBD !important;">
                                    &amp;nbsp;<span t-esc="l.get('Concepto')"/>
                                </td>                                
                                <td style="text-align: center; vertical-align:top; border-right: 1px solid #BDBDBD !important; border-bottom: 1px solid #BDBDBD !important;">
                                    &amp;nbsp;<strong t-esc="l.get('Importe', 0.0)" t-options='{"widget": "monetary", "display_currency": o.currency_id}'/>
                                </td>
                            </tr>
                        </t>
                    </table>
                    <table class="info" style="width: 100%; font-size: 10px;">
                        <tr>
                            <td><span style="font-size: 10px;"><strong>Incapacidades:</strong>  <span t-esc="rec.get('Incapacidad', 0.0)" t-options='{"widget": "monetary", "display_currency": o.currency_id}'/></span></td>
                        </tr>
                    </table>
                    <table class="info" style="width: 100%; font-size: 10px;">
                        <tr>
                            <td style="width: 80%; vertical-align:top;">
                                <table class="info" style="width: 100%; font-size: 10px;">
                                    <tr>
                                        <td colspan="4">
                                            <span><strong>IMPORTE CON LETRAS:</strong></span> <span t-esc="rec.get('AmountText')" />
                                        </td>
                                    </tr>
                                    <tr>
                                        <td>Folio Fiscal:</td>
                                        <td><span t-esc="rec.get('UUID')" /></td></tr>
                                    <tr>
                                        <td>Fecha y hora de certificación:</td>
                                        <td><span t-esc="rec.get('FechaTimbrado')" /></td>
                                    </tr>
                                </table>
                            </td>
                            <td style="width: 20%; vertical-align:top;">
                                <table class="info" style="width: 100%; font-size: 10px;">
                                    <tr>
                                        <td><strong>Subtotal</strong></td>
                                        <td>
                                            &amp;nbsp;<span t-esc="rec.get('SubTotal', 0.0)" t-options='{"widget": "monetary", "display_currency": o.currency_id}'/>
                                        </td>
                                    </tr>
                                    <tr>
                                        <td><strong>Descuento</strong></td>
                                        <td>
                                            &amp;nbsp;<span t-esc="rec.get('Descuento', 0.0)" t-options='{"widget": "monetary", "display_currency": o.currency_id}'/>
                                        </td>
                                    </tr>
                                    <tr>
                                        <td><strong>Total</strong></td>
                                        <td>
                                            &amp;nbsp;<span t-esc="rec.get('Total', 0.0)" t-options='{"widget": "monetary", "display_currency": o.currency_id}'/>
                                        </td>
                                    </tr>
                                </table>
                            </td>
                        </tr>
                    </table>
                    <div class="row" id='complement'>
                        <div class="barcode col-3">
                            <div class="barcode" t-if="o.l10n_mx_edi_cfdi_uuid">
                                <t t-set="sello" t-value="rec.get('Sello')"/>
                                <img style="height: 180px; width: 180px;" alt="Barcode" t-att-src="'/report/barcode/?type=QR&amp;value=%s' % quote_plus(
                                    'https://verificacfdi.facturaelectronica.sat.gob.mx/default.aspx?' + keep_query(
                                        re=o.l10n_mx_edi_cfdi_supplier_rfc, rr=o.l10n_mx_edi_cfdi_customer_rfc,
                                        tt='%.*f' % (o.currency_id.decimal_places, rec.get('Total')), id=o.l10n_mx_edi_cfdi_uuid)
                                        + '&amp;fe=%s' % quote_plus(
                                            sello, 'utf-8', 'strict', '=/').replace('%2B', '+'))"/>
                            </div>
                        </div>
                        <div class="complement-details col-9">
                            <div class="digital-stamp" t-if="rec.get('SelloCFDI')">
                                <span>Sello</span>
                            </div>
                            <div class="digital-stamp-content">
                                <span t-esc="rec.get('SelloCFDI')"/>
                            </div>
                            <div class="digital-stamp" t-if="rec.get('SelloSAT')">
                                <span>Sello SAT</span>
                            </div>
                            <div class="digital-stamp-content">
                                <span t-esc="rec.get('SelloSAT')"/>
                            </div>
                            <div class="digital-stamp" t-if="rec.get('CadenaOriginal')">
                                <span>Cadena Original</span>
                            </div>
                            <div class="digital-stamp-content">
                                <span class="nowrap" t-esc="rec.get('CadenaOriginal')"/>
                            </div>
                            <div class="digital-stamp-content text-center" t-if="o.l10n_mx_edi_cfdi_uuid">
                                <strong>This document is a printed representation of a CFDI</strong>
                            </div>
                        </div>
                    </div>
                </div>
            </t>
        </template>



















































import odoorpc

odoo = odoorpc.ODOO('localhost', port=8089)
odoo.login('odoo12_repNom', 'admin', 'admin')



user_data = odoo.execute('hr.payslip.run', 'dispersion_banorte_datas', [8])
print('----------- user_data ', user_data)






H					| 01 - 01 - Tipo de Registro
NE 					| 02 - 02 - NE
77869 				| 05 - 05 - Numero de Emisora
20201230			| 06 - 08 - Fecha de Proceso
01					| 07 - 02 - Consecutivo
000010 				| 08 - 06 - No. total de registros
000000000001000 	| 09 - 15 - Importe Total de Registros Enviados
000000 				| 10 - 06 - No. Altas
000000000000000 	| 11 - 15 - Importe Total de Altas (13 Enterios, 2 Decimales)
000000 				| 12 - 06 - No Bajas
000000000000000 	| 13 - 15 - Importe Bajas
000000 				| 14 - 06 - No. Total Cuentas a verificar
0 					| 15 - 01 - Accion
0
0000000000002043875580000000000000000000000000000000000000000000000000000000


D
20201222
0000000002
000000000301899
014
40
014778605515738535
0

00000000                  

D 					| 01 - 01 - D
20201230			| 02 - 08 - Fecha Aplicacion
0000050428 			| 03 - 10 - No. Empleado
                                         			| 04 - 40 - Referencia del Servicio
                                         			| 05 - 40 - Referencia Leyenda del Ordenante
000000000000100 	| 06 - 15 - Importe
072 				| 07 - 03 - No. Banco Receptor
01 					| 08 - 02 - Tipo de Cuenta (01 - Cheques - 03 - Tarjeta de Debito - 40 - Clabe)
072180002128093188 	| 09 - 18 - Numero de Cuenta
0 					| 10 - 01 - Tipo de Movimiento
 					| 11 - 01 - Accion 
00000000 			| 12 - 08 - Importe IVA
                  	| 13 - 18 - Filler


D
20201222
0000000001                                                                                000000000819498127401272250011675462160 00000000                  


D202012300000050434                                                                                000000000000100 012 40 012180027599518570 0 00000000                  
D202012300000050610                                                                                000000000000100 002 40 002441700739887464 0 00000000                  
D202012300000050667                                                                                000000000000100 072 01 072180004583807276 0 00000000                  
D202012300000050697                                                                                000000000000100 014 40 014180570051634845 0 00000000                  
D202012300000050706                                                                                000000000000100 002 40 002180019760860978 0 00000000                  
D202012300000050729                                                                                000000000000100 072 01 072180003661719452 0 00000000                  
D202012300000050761                                                                                000000000000100 072 01 072180010329154504 0 00000000                  
D202012300000050783                                                                                000000000000100 012 40 012180029403688141 0 00000000                  
D202012300000050788                                                                                000000000000100 014 40 014180605821488345 0 00000000                  



"""