# -*- coding: utf-8 -*-






"""
Control de Cambios.
1. Nominas C99=0 cambiarlas a Done. 												OK
2. Nominas Especiales. No permitir crear dos veces el mismo registro.(Excel).		OK

3. Crear opcion Generar dispersión de pagos. Seleccionar empleados
3. Nomina para empleados inactivos... Finiquitos
3. Enviar Mensajes al calcular la nomina.
4. Enviar Mensajes al Confirmar la nomina
5. Correr la nomina con OdooBot






Caclular nomina
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