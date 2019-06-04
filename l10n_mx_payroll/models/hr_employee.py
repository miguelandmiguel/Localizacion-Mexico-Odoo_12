# -*- coding: utf-8 -*-

from datetime import datetime
from dateutil.relativedelta import relativedelta
import re

from odoo import api, fields, models, _

class HrCurriculum(models.Model):
    _name = 'hr.curriculum'
    _description = "Employee's Curriculum"
    _inherit = 'mail.thread'

    name = fields.Char('Name', required=True)
    employee_id = fields.Many2one('hr.employee', string='Employee', required=True)
    start_date = fields.Date('Start date')
    end_date = fields.Date('End date')
    description = fields.Text('Description')
    partner_id = fields.Many2one('res.partner', 'Partner', help="Employer, School, University, Certification Authority")
    location = fields.Char('Location', help="Location")
    expire = fields.Boolean('Expire', help="Expire", default=True)

class HrAcademic(models.Model):
    _name = 'hr.academic'
    _description = "Employee's Academic"
    _inherit = 'hr.curriculum'

    diploma = fields.Char('Diploma', translate=True)
    study_field = fields.Char('Field of study', translate=True)
    activities = fields.Text('Activities and associations', translate=True)

class HrCertification(models.Model):
    _name = 'hr.certification'
    _description = "Employee's Certification"
    _inherit = 'hr.curriculum'

    certification = fields.Char('Certification Number', help='Certification Number')
    category = fields.Selection([
            ('curso', 'Curso'),
            ('certificacion', 'Certificacion'),
            ('diplomado', 'Diplomado'),
            ('maestria', 'Maestria'),
        ], string='Category', required=True, default='curso', help='Category')

class HrExperience(models.Model):
    _name = 'hr.experience'
    _description = "Employee's Experience"
    _inherit = 'hr.curriculum'

    category = fields.Selection([
        ('professional', 'Professional'),
        ('academic', 'Academic'),
        ('certification', 'Certification')],
        string='Category', required=True, default='professional', help='Category')


class HrEmployeeDepends(models.Model):
    _name = "hr.employee.depends"
    _description = "Employee Dependents"
    _order = "employee_id,sequence,id"

    name = fields.Text(string='Name', required=True)
    sequence = fields.Integer(default=10, help="Gives the sequence of this line when displaying the employee.")
    birthday = fields.Date(string='Date of Birth', index=True, copy=False)
    type = fields.Selection([
            ('husband','Husband'),
            ('wife','Wife'),
            ('son','Son'),
            ('daughter','Daughter'),
            ('other','Other'),
        ], index=True, change_default=True,
        default=lambda self: self._context.get('type', 'wife'),
        track_visibility='always')
    employee_id = fields.Many2one('hr.employee', string='Employee Reference', ondelete='cascade', index=True)

class Employee(models.Model):
    _inherit = 'hr.employee'
    _name = 'hr.employee'
    # _rec_name = "nombre_completo"

    @api.model
    def _default_employee_code(self):
        if self.id:
            self.cfdi_code_emp = '%.*f' % (6, self.id)


    state_of_birth = fields.Many2one('res.country.state', 'Place of Birth (State)', oldname="state_id")
    marital = fields.Selection(selection_add=[('free_union', 'Free Union')])
    work_phone_ext = fields.Char(string='Work Phone Extension', oldname="work_extension_phone", help='Internal phone number.')

    cfdi_appat = fields.Char(string="Apellido Paterno", size=64, required=True, default="", oldname="appat")
    cfdi_apmat = fields.Char(string="Apellido Materno", size=64, required=True, default="", oldname="apmat")
    cfdi_code_emp = fields.Char(string="Codigo de Empleado", index=True, default=_default_employee_code, oldname="cod_emp")
    cfdi_payroll_card = fields.Char(string="Payroll Card", size=64, default="", oldname="tarjeta_nomina")
    
    cfdi_date_start = fields.Date(string="Start Date", oldname="fecha_alta")
    cfdi_date_end = fields.Date(string="End Date", oldname="fecha_baja")
    cfdi_anhos_servicio = fields.Integer(u"Años de servicio", oldname="anhos_servicio")

    cfdi_curp = fields.Char(string="CURP", size=18, default="", oldname="curp")
    cfdi_rfc = fields.Char(string="RFC", size=13, default="", oldname="rfc")
    cfdi_sar = fields.Char(string="SAR", size=64, default="", oldname="sar")
    cfdi_imss = fields.Char(string="No. IMSS", size=64, default="", oldname="imss")
    cfdi_sueldo_imss = fields.Float(string='Sueldo Integrado al IMSS', oldname="sueldo_imss")
    cfdi_ret_imss = fields.Float(string='Retencion IMSS', oldname="retencion_imss_fija")
    cfdi_imss_umf = fields.Char(string="Unidad de Medicina Familiar", default="", oldname="imss_umf")

    cfdi_infonavit = fields.Char(string="No. Infonavit", size=64, default="", oldname="infonavit")
    cfdi_sueldo_infonavit = fields.Float(string='Sueldo Integrado al Infonavit', oldname="sueldo_infonavit")
    cfdi_dto_fonacot = fields.Float(string='Descuento Fonacot', oldname="valor_descuento_fonacot")

    cfdi_dto_infonavit = fields.Float(string='Descuento Infonavit', oldname="valor_descuento_infonavit")
    cfdi_alta_infonavit = fields.Date(string="Alta Infonavit", oldname="fecha_alta_infonavit")
    cfdi_tipo_dto_infonavit_id = fields.Many2one("l10n_mx_payroll.tipodescuento", string="Tipo de Descuento", oldname="tipo_descuento_infonavit_id")
    cfdi_sueldo_diario = fields.Float(string='Sueldo Diario', track_visibility='onchange', oldname="sueldo_diario")
    cfdi_retiro_parcialidad = fields.Float(string="Retiro", oldname="retiro_parcialidad",
        help="Monto diario percibido por el trabajador por jubilación, pensión o retiro cuando el pago es en parcialidades")
    

    cfdi_ife_anverso = fields.Binary(string='IFE Anverso', filters='*.png,*.jpg,*.jpeg', attachment=True, oldname="ife_anverso")
    cfdi_ife_reverso = fields.Binary(string='IFE Reverso', filters='*.png,*.jpg,*.jpeg', attachment=True, oldname="ife_reverso")
    cfdi_ife_numero = fields.Char(string="Clave de Elector", size=64, default="", oldname="ife_numero")
    cfdi_licencia_anverso = fields.Binary(string='Lic. Anverso', filters='*.png,*.jpg,*.jpeg', attachment=True, oldname="licencia_anverso")
    cfdi_licencia_reverso = fields.Binary(string='Lic. Reverso', filters='*.png,*.jpg,*.jpeg', attachment=True, oldname="licencia_reverso")
    cfdi_licencia_numero = fields.Char(string="Numero", size=64, default="", oldname="licencia_numero")
    cfdi_licencia_vigencia = fields.Date(string="Vigencia", oldname="licencia_vigencia")

    cfdi_sindicalizado = fields.Boolean(string="Sindicalizado", oldname="sindicalizado")
    cfdi_tipojornada_id = fields.Many2one("l10n_mx_payroll.tipojornada", string="Tipo de Jornada", oldname="tipo_jornada_id")
    cfdi_escolaridad_id = fields.Many2one("l10n_mx_payroll.escolaridad", string="Escolaridad", oldname="escolaridad_id")
    cfdi_registropatronal_id = fields.Many2one("l10n_mx_payroll.regpat", string="Registro Patronal", oldname="registro_patronal_id")
    cfdi_tiposueldo_id = fields.Many2one("l10n_mx_payroll.tiposueldo", string="Tipo Sueldo", oldname="tipo_sueldo_id")
    cfdi_tipotrabajador_id = fields.Many2one("l10n_mx_payroll.tipotrabajador", string="Tipo Trabajador", oldname="tipo_trabajador_id")
    cfdi_zonasalario_id = fields.Many2one("l10n_mx_payroll.zonasalario", string="Zona Salario", oldname="zona_salario_id")
    cfdi_formapago_id = fields.Many2one("l10n_mx_payroll.formapago", string="Forma de Pago", oldname="forma_pago_id")
    cfdi_horasjornada = fields.Integer(string="Horas Jornada", oldname="horas_jornada")

    cfdi_med_actividad = fields.Text(string="Actividades", oldname="med_actividad",
        help="Actividad dentro de la Empresa")
    cfdi_med_antecedentes_1 = fields.Text(string="Antecedentes Heredo Familiares", oldname="med_antecedentes_1")
    cfdi_med_antecedentes_2 = fields.Text(string="Antecedentes no Patologicos", oldname="med_antecedentes_2")
    cfdi_med_antecedentes_3 = fields.Text(string="Antecedentes Patologicos", oldname="med_antecedentes_3")
    cfdi_med_padecimiento = fields.Text(string="Padecimento Actual", oldname="med_padecimiento")
    cfdi_med_exploracion = fields.Text(string="Exploracion Fisica", oldname="med_exploracion")
    cfdi_med_diagnostico = fields.Text(string="Diagnostico", oldname="med_diagnostico")
    cfdi_med_apto = fields.Boolean("Apto para el Puesto", oldname="med_apto")

    cfdi_age = fields.Integer(string='Age', readonly=True, compute='_compute_employee_age')
    cfdi_employee_dependent_ids = fields.One2many('hr.employee.depends', 'employee_id', string='Dependents', copy=False, oldname="employee_dependent_ids")
    cfdi_certification_ids = fields.One2many('hr.certification', 'employee_id', 'Certifications', oldname="certification_ids", help="Certifications")
    cfdi_academic_ids = fields.One2many('hr.academic', 'employee_id', 'Academic experiences', oldname="academic_ids", help="Academic experiences")
    cfdi_experience_ids = fields.One2many('hr.experience', 'employee_id', 'Professional Experiences', oldname="experience_ids", help='Professional Experiences')

    last_writedate_job_id = fields.Datetime(string='Latest Change Job', readonly=False, compute="_compute_last_writedate_job_id")
    last_writedate_sueldo_diario = fields.Datetime(string='Latest Change Salary', readonly=False, compute="_compute_last_writedate_sueldo_diario")

    @api.one
    @api.depends('birthday')
    def _compute_employee_age(self):
        if self.birthday:
            self.cfdi_age = relativedelta(
                fields.Date.from_string(fields.Date.today()),
                fields.Date.from_string(self.birthday)).years
        else:
            self.cfdi_age = 0

    @api.one
    @api.depends('job_id')
    def _compute_last_writedate_job_id(self):
        if self.job_id:
            self.last_writedate_job_id = fields.Datetime.now()

    @api.one
    @api.depends('cfdi_sueldo_diario')
    def _compute_last_writedate_sueldo_diario(self):
        if self.cfdi_sueldo_diario:
            self.last_writedate_sueldo_diario = fields.Datetime.now()


    @api.constrains('cfdi_rfc')
    def _check_rfc(self):
        for rec in self:
            if rec.address_home_id and rec.address_home_id.vat != rec.cfdi_rfc:
                raise ValidationError('El RFC "%s" no coincide con el del partner %s'%(rec.cfdi_rfc, rec.address_home_id.vat))
        return True

    _sql_constraints = [
        ('cfdi_code_emp_uniq', 'unique (cfdi_code_emp)', "Error! Ya hay un empleado con ese codigo."),
    ]


    @api.onchange('address_id')
    def _onchange_address(self):
        self.work_phone = self.address_id.phone
        self.mobile_phone = self.address_id.mobile
        self.work_location = self.address_id.name

    @api.onchange('user_id')
    def _onchange_user(self):
        if self.user_id:
            self.work_email = self.user_id.email or ''
            self.work_phone_ext = self.user_id.phone_ext or ''
            self.cfdi_curp = self.cfdi_curp or '' 
            self.image = self.user_id.image


    @api.onchange('cfdi_date_start', 'cfdi_date_end')
    def _onchange_cfdi_anhos_servicio(self):
        cfdi_date_start = self.cfdi_date_start or fields.Date.today()
        cfdi_date_end = self.cfdi_date_end or fields.Date.today()
        self.cfdi_anhos_servicio = relativedelta(
            fields.Date.from_string(cfdi_date_end),
            fields.Date.from_string(cfdi_date_start)).years


    @api.multi
    def name_get(self):
        result = []
        for inv in self:
            result.append((inv.id, "%s %s %s" % (inv.name, inv.cfdi_appat or '', inv.cfdi_apmat or '')))
        return result

    @api.model
    def name_search(self, name, args=None, operator='ilike', limit=100):
        args = args or []
        recs = self.browse()
        if name:
            cfdi_code_ids = self.search([('cfdi_code_emp', 'ilike', name)] + args, limit=limit)
            cfdi_appat_ids = self.search([('cfdi_appat', 'ilike', name)] + args, limit=limit)
            cfdi_apmat_ids = self.search([('cfdi_apmat', 'ilike', name)] + args, limit=limit)
            if cfdi_code_ids: recs += cfdi_code_ids
            if cfdi_appat_ids: recs += cfdi_appat_ids
            if cfdi_apmat_ids: recs += cfdi_apmat_ids

            search_domain = [('name', operator, name)]
            if recs.ids:
                search_domain.append(('id', 'not in', recs.ids))
            name_ids = self.search(search_domain + args, limit=limit)
            if name_ids: recs += name_ids

        if not recs:
            recs = self.search([('name', operator, name)] + args, limit=limit)
        return recs.name_get()


class HrPayslip(models.Model):
    _inherit = "hr.payslip"

    cfdi_code_emp = fields.Char(related='employee_id.cfdi_code_emp', store=True,  string=u"Codigo empleado", readonly=True)


class HrContract(models.Model):
    _inherit = "hr.contract"

    cfdi_total_days_worked = fields.Integer(string="Days Worked", compute='_compute_total_days_worked', oldname="total_days_worked")

    def _compute_total_days_worked(self):
        for contract in self:            
            date_start = contract.date_start
            date_end = contract.date_end if contract.date_end else fields.Date.today()

            # date_start = datetime.strptime(date_start, "%Y-%m-%d")
            # date_end = datetime.strptime(date_end, "%Y-%m-%d")
            delta = date_end - date_start
            contract.cfdi_total_days_worked = delta.days