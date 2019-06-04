# -*- coding: utf-8 -*-

from odoo import api, fields, models, _

class TipoPensionados(models.Model):
    _name = 'l10n_mx_payroll.tipopensionados'
    _description = 'Tipo Pensionados'
    
    name = fields.Char(string="Name", size=64, required=True, default="")
    code = fields.Char(string="Code", required=True, default="")

    @api.multi
    def name_get(self):
        result = []
        for rec in self:
            result.append((rec.id, "[%s] %s" % (rec.code, rec.name or '')))
        return result

    @api.model
    def name_search(self, name, args=None, operator='ilike', limit=100):
        recs = super(TipoPensionados, self).name_search(name, args=args, operator=operator, limit=limit)
        args = args or []
        recs = self.browse()
        if name:
            recs = self.search([('code', operator, name)] + args, limit=limit)
        if not recs:
            recs = self.search([('name', operator, name)] + args, limit=limit)
        return recs.name_get()


class TipoDescuento(models.Model):
    _name = 'l10n_mx_payroll.tipodescuento'
    _description = 'Tipo de descuento Infonavit (Tipo de Credito)'
    
    name = fields.Char(string="Name", size=64, required=True, default="")
    code = fields.Char(string="Code", required=True, default="")

    @api.multi
    def name_get(self):
        result = []
        for rec in self:
            result.append((rec.id, "[%s] %s" % (rec.code, rec.name or '')))
        return result

    @api.model
    def name_search(self, name, args=None, operator='ilike', limit=100):
        recs = super(TipoDescuento, self).name_search(name, args=args, operator=operator, limit=limit)
        args = args or []
        recs = self.browse()
        if name:
            recs = self.search([('code', operator, name)] + args, limit=limit)
        if not recs:
            recs = self.search([('name', operator, name)] + args, limit=limit)
        return recs.name_get()


class TipoTrabajador(models.Model):
    _name = 'l10n_mx_payroll.tipotrabajador'
    _description = 'Tipo Trabajador'
    
    name = fields.Char(string="Name", size=64, required=True, default="")
    code = fields.Char(string="Code", required=True, default="")

    @api.multi
    def name_get(self):
        result = []
        for rec in self:
            result.append((rec.id, "[%s] %s" % (rec.code, rec.name or '')))
        return result

    @api.model
    def name_search(self, name, args=None, operator='ilike', limit=100):
        recs = super(TipoTrabajador, self).name_search(name, args=args, operator=operator, limit=limit)
        args = args or []
        recs = self.browse()
        if name:
            recs = self.search([('code', operator, name)] + args, limit=limit)
        if not recs:
            recs = self.search([('name', operator, name)] + args, limit=limit)
        return recs.name_get()

class TipoSueldo(models.Model):
    _name = 'l10n_mx_payroll.tiposueldo'
    _description = 'Tipo de Sueldo'
    
    name = fields.Char(string="Name", size=64, required=True, default="")
    code = fields.Char(string="Code", required=True, default="")

    @api.multi
    def name_get(self):
        result = []
        for rec in self:
            result.append((rec.id, "[%s] %s" % (rec.code, rec.name or '')))
        return result

    @api.model
    def name_search(self, name, args=None, operator='ilike', limit=100):
        recs = super(TipoSueldo, self).name_search(name, args=args, operator=operator, limit=limit)
        args = args or []
        recs = self.browse()
        if name:
            recs = self.search([('code', operator, name)] + args, limit=limit)
        if not recs:
            recs = self.search([('name', operator, name)] + args, limit=limit)
        return recs.name_get()

class TipoJornada(models.Model):
    _name = "l10n_mx_payroll.tipojornada"
    _description = 'Tipo de Jornada'

    name = fields.Char(string="Name", size=64, required=True, default="")
    code = fields.Char(string="Code", required=True, default="")

    @api.multi
    def name_get(self):
        result = []
        for rec in self:
            result.append((rec.id, "[%s] %s" % (rec.code, rec.name or '')))
        return result

    @api.model
    def name_search(self, name, args=None, operator='ilike', limit=100):
        recs = super(TipoJornada, self).name_search(name, args=args, operator=operator, limit=limit)
        args = args or []
        recs = self.browse()
        if name:
            recs = self.search([('code', operator, name)] + args, limit=limit)
        if not recs:
            recs = self.search([('name', operator, name)] + args, limit=limit)
        return recs.name_get()

class ZonaSalario(models.Model):
    _name = 'l10n_mx_payroll.zonasalario'
    _description = 'Zona de Salario'

    name = fields.Char(string="Name", size=64, required=True, default="")
    code = fields.Char(string="Code", default="")
    description = fields.Char(string="Description", size=64, default="")

    @api.multi
    def name_get(self):
        result = []
        for rec in self:
            result.append((rec.id, "[%s] %s" % (rec.code, rec.name or '')))
        return result

    @api.model
    def name_search(self, name, args=None, operator='ilike', limit=100):
        recs = super(ZonaSalario, self).name_search(name, args=args, operator=operator, limit=limit)
        args = args or []
        recs = self.browse()
        if name:
            recs = self.search([('code', operator, name)] + args, limit=limit)
        if not recs:
            recs = self.search([('name', operator, name)] + args, limit=limit)
        return recs.name_get()

class FormaPago(models.Model):
    _name = 'l10n_mx_payroll.formapago'
    _description = 'Forma de Pago'
    
    name = fields.Char(string="Name", size=64, required=True, default="")
    code = fields.Char(string="Code", required=True, default="")
    description = fields.Char(string="Description", size=64, default="")

    @api.multi
    def name_get(self):
        result = []
        for rec in self:
            result.append((rec.id, "[%s] %s" % (rec.code, rec.name or '')))
        return result

    @api.model
    def name_search(self, name, args=None, operator='ilike', limit=100):
        recs = super(FormaPago, self).name_search(name, args=args, operator=operator, limit=limit)
        args = args or []
        recs = self.browse()
        if name:
            recs = self.search([('code', operator, name)] + args, limit=limit)
        if not recs:
            recs = self.search([('name', operator, name)] + args, limit=limit)
        return recs.name_get()

class RegistroPatronal(models.Model):
    _name = 'l10n_mx_payroll.regpat'
    _description = 'Registro Patronal'
    
    name = fields.Char(string="Name", size=64, required=True, default="")
    company_id = fields.Many2one('res.company', string='Company', change_default=True,
        default=lambda self: self.env['res.company']._company_default_get('l10n_mx_payroll.regpat'))

class Escolaridad(models.Model):
    _name = "l10n_mx_payroll.escolaridad"
    _description = 'Escolaridad'

    name = fields.Char(string="Name", size=64, required=True, default="")
    code = fields.Char(string="Code", required=True, default="")
    description = fields.Char(string="Description", size=64, required=True, default="")

    @api.multi
    def name_get(self):
        result = []
        for rec in self:
            result.append((rec.id, "%s" % (rec.name or '')))
        return result

    @api.model
    def name_search(self, name, args=None, operator='ilike', limit=100):
        recs = super(Escolaridad, self).name_search(name, args=args, operator=operator, limit=limit)
        args = args or []
        recs = self.browse()
        if name:
            recs = self.search([('code', operator, name)] + args, limit=limit)
        if not recs:
            recs = self.search([('name', operator, name)] + args, limit=limit)
        return recs.name_get()





class PeriodicidadPago(models.Model):
    _name = "l10n_mx_payroll.periodicidad_pago"
    _description = "Periodicidad Pago"

    name = fields.Char(string="Nombre", required=True)
    code = fields.Char(string=u"Codigo Catalogo SAT", required=True)

    @api.multi
    def name_get(self):
        result = []
        for rec in self:
            result.append((rec.id, "[%s] %s" % (rec.code, rec.name or '')))
        return result

    @api.model
    def name_search(self, name, args=None, operator='ilike', limit=100):
        recs = super(PeriodicidadPago, self).name_search(name, args=args, operator=operator, limit=limit)
        args = args or []
        recs = self.browse()
        if name:
            recs = self.search([('code', operator, name)] + args, limit=limit)
        if not recs:
            recs = self.search([('name', operator, name)] + args, limit=limit)
        return recs.name_get()


class OrigenRecurso(models.Model):
    _name = "l10n_mx_payroll.origen_recurso"
    _description = "Origen recurso"

    name = fields.Char(string="Nombre", required=True)
    code = fields.Char(string=u"Codigo Catalogo SAT", required=True)

    @api.multi
    def name_get(self):
        result = []
        for rec in self:
            result.append((rec.id, "[%s] %s" % (rec.code, rec.name or '')))
        return result

    @api.model
    def name_search(self, name, args=None, operator='ilike', limit=100):
        recs = super(OrigenRecurso, self).name_search(name, args=args, operator=operator, limit=limit)
        args = args or []
        recs = self.browse()
        if name:
            recs = self.search([('code', operator, name)] + args, limit=limit)
        if not recs:
            recs = self.search([('name', operator, name)] + args, limit=limit)
        return recs.name_get()



class RegimenContratacion(models.Model):
    _name = "l10n_mx_payroll.regimen_contratacion"
    _description = "Regimen contratacion"
    
    name = fields.Char(string="Descripcion", required=True)
    code = fields.Char(string=u"Codigo Catalogo SAT", required=True)

    @api.multi
    def name_get(self):
        result = []
        for rec in self:
            result.append((rec.id, "[%s] %s" % (rec.code, rec.name or '')))
        return result

    @api.model
    def name_search(self, name, args=None, operator='ilike', limit=100):
        recs = super(RegimenContratacion, self).name_search(name, args=args, operator=operator, limit=limit)
        args = args or []
        recs = self.browse()
        if name:
            recs = self.search([('code', operator, name)] + args, limit=limit)
        if not recs:
            recs = self.search([('name', operator, name)] + args, limit=limit)
        return recs.name_get()


class ClaseRiesgo(models.Model):
    _name = "l10n_mx_payroll.riesgo_puesto"
    _description = "Clase Riesgo"
    
    name = fields.Char(string="Descripcion", required=True)
    code = fields.Char(string=u"Codigo Catalogo SAT", required=True)

    @api.multi
    def name_get(self):
        result = []
        for rec in self:
            result.append((rec.id, "[%s] %s" % (rec.code, rec.name or '')))
        return result

    @api.model
    def name_search(self, name, args=None, operator='ilike', limit=100):
        recs = super(ClaseRiesgo, self).name_search(name, args=args, operator=operator, limit=limit)
        args = args or []
        recs = self.browse()
        if name:
            recs = self.search([('code', operator, name)] + args, limit=limit)
        if not recs:
            recs = self.search([('name', operator, name)] + args, limit=limit)
        return recs.name_get()

class TipoRegla(models.Model):
    _name = "l10n_mx_payroll.tipo"
    _description = "Tipo de Regla"
    
    name = fields.Char(string="Tipo", required=True)


class CodigoAgrupador(models.Model):
    _name = "l10n_mx_payroll.codigo_agrupador"
    _description = "Codigo Agrupador"

    name = fields.Char(string="Nombre", required=True)
    code = fields.Char(string=u"Codigo Catalogo SAT", required=True)
    cfdi_tipo_id = fields.Many2one("l10n_mx_payroll.tipo", string="Tipo", required=True, oldname="tipo_id")

    @api.multi
    def name_get(self):
        result = []
        for rec in self:
            result.append((rec.id, "[%s] %s" % (rec.code, rec.name or '')))
        return result

    @api.model
    def name_search(self, name, args=None, operator='ilike', limit=100):
        recs = super(CodigoAgrupador, self).name_search(name, args=args, operator=operator, limit=limit)
        args = args or []
        recs = self.browse()
        if name:
            recs = self.search([('code', operator, name)] + args, limit=limit)
        if not recs:
            recs = self.search([('name', operator, name)] + args, limit=limit)
        return recs.name_get()
    

class TipoHoras(models.Model):
    _name = "l10n_mx_payroll.tipo_horas"
    _description = "Tipo horas"

    name = fields.Char(string="Nombre", required=True)
    code = fields.Char(string=u"Codigo Catalogo SAT", required=True)

    @api.multi
    def name_get(self):
        result = []
        for rec in self:
            result.append((rec.id, "[%s] %s" % (rec.code, rec.name or '')))
        return result

    @api.model
    def name_search(self, name, args=None, operator='ilike', limit=100):
        recs = super(TipoHoras, self).name_search(name, args=args, operator=operator, limit=limit)
        args = args or []
        recs = self.browse()
        if name:
            recs = self.search([('code', operator, name)] + args, limit=limit)
        if not recs:
            recs = self.search([('name', operator, name)] + args, limit=limit)
        return recs.name_get()


class TipoIncapacidad(models.Model):
    _name = "l10n_mx_payroll.tipo_incapacidad"
    _description = "Tipo incapacidad"

    name = fields.Char(string="Nombre", required=True)
    code = fields.Char(string=u"Codigo Catalogo SAT", required=True)

    @api.multi
    def name_get(self):
        result = []
        for rec in self:
            result.append((rec.id, "[%s] %s" % (rec.code, rec.name or '')))
        return result

    @api.model
    def name_search(self, name, args=None, operator='ilike', limit=100):
        recs = super(TipoIncapacidad, self).name_search(name, args=args, operator=operator, limit=limit)
        args = args or []
        recs = self.browse()
        if name:
            recs = self.search([('code', operator, name)] + args, limit=limit)
        if not recs:
            recs = self.search([('name', operator, name)] + args, limit=limit)
        return recs.name_get()

class TipoDeduccion(models.Model):
    _name = "l10n_mx_payroll.tipo_deduccion"
    _description = "Tipo deduccion"

    name = fields.Char(string="Nombre", required=True)
    code = fields.Char(string=u"Codigo Catalogo SAT", required=True)

    @api.multi
    def name_get(self):
        result = []
        for rec in self:
            result.append((rec.id, "[%s] %s" % (rec.code, rec.name or '')))
        return result

    @api.model
    def name_search(self, name, args=None, operator='ilike', limit=100):
        recs = super(TipoDeduccion, self).name_search(name, args=args, operator=operator, limit=limit)
        args = args or []
        recs = self.browse()
        if name:
            recs = self.search([('code', operator, name)] + args, limit=limit)
        if not recs:
            recs = self.search([('name', operator, name)] + args, limit=limit)
        return recs.name_get()


class TipoJornada(models.Model):
    _name = "l10n_mx_payroll.tipo_jornada"
    _description = "Tipo jornada"

    name = fields.Char(string="Nombre", required=True)
    code = fields.Char(string=u"Codigo Catalogo SAT", required=True)

    @api.multi
    def name_get(self):
        result = []
        for rec in self:
            result.append((rec.id, "[%s] %s" % (rec.code, rec.name or '')))
        return result

    @api.model
    def name_search(self, name, args=None, operator='ilike', limit=100):
        recs = super(TipoJornada, self).name_search(name, args=args, operator=operator, limit=limit)
        args = args or []
        recs = self.browse()
        if name:
            recs = self.search([('code', operator, name)] + args, limit=limit)
        if not recs:
            recs = self.search([('name', operator, name)] + args, limit=limit)
        return recs.name_get()

class TipoOtroPago(models.Model):
    _name = "l10n_mx_payroll.tipo_otro_pago"
    _description = "Tipo Otro Pago"

    name = fields.Char(string="Nombre", required=True)
    code = fields.Char(string=u"Codigo Catalogo SAT", required=True)

    @api.multi
    def name_get(self):
        result = []
        for rec in self:
            result.append((rec.id, "[%s] %s" % (rec.code, rec.name or '')))
        return result

    @api.model
    def name_search(self, name, args=None, operator='ilike', limit=100):
        recs = super(TipoOtroPago, self).name_search(name, args=args, operator=operator, limit=limit)
        args = args or []
        recs = self.browse()
        if name:
            recs = self.search([('code', operator, name)] + args, limit=limit)
        if not recs:
            recs = self.search([('name', operator, name)] + args, limit=limit)
        return recs.name_get()

class TipoPercepcion(models.Model):
    _name = "l10n_mx_payroll.tipo_percepcion"
    _description = "Tipo Percepcion"

    name = fields.Char(string="Nombre", required=True)
    code = fields.Char(string=u"Codigo Catalogo SAT", required=True)

    @api.multi
    def name_get(self):
        result = []
        for rec in self:
            result.append((rec.id, "[%s] %s" % (rec.code, rec.name or '')))
        return result

    @api.model
    def name_search(self, name, args=None, operator='ilike', limit=100):
        recs = super(TipoPercepcion, self).name_search(name, args=args, operator=operator, limit=limit)
        args = args or []
        recs = self.browse()
        if name:
            recs = self.search([('code', operator, name)] + args, limit=limit)
        if not recs:
            recs = self.search([('name', operator, name)] + args, limit=limit)
        return recs.name_get()


class TablaSubsidio(models.Model):
    _name = "l10n_mx_payroll.hr_tabla_subsidio"
    _description = "Tabla Subsidio"

    name = fields.Char(string=u"Año", required=True)
    limite_inferior = fields.Float(string=u"Limite inferior", required=True)
    limite_superior = fields.Float(string=u"Limite superior", required=True)
    subsidio = fields.Float(string="Subsidio", required=True)

class TablaIsr(models.Model):
    _name = "l10n_mx_payroll.hr_tabla_isr"
    _description = "Tabla ISR"
    
    name = fields.Char(string=u"Año", required=True)
    limite_inferior = fields.Float(string=u"Limite inferior", required=True)
    limite_superior = fields.Float(string=u"Limite superior", required=True)
    cuota_fija = fields.Float(string="Cuota fija", required=True)
    tasa = fields.Float(string="Tasa (%)", required=True)

    @api.multi
    def calcular_isr(self, ingreso, name):
        tabla_id = self.search([('name', '=', name)], order='limite_inferior asc')
        if not tabla_id:
            raise UserError("Error \n\nNo hay tabla de ISR definida para el año %s"%name)
        rows = self.browse(tabla_id)
        r = rows[0]
        for row in rows:
            if row.limite_superior < 0:
                row.limite_superior = float("inf")
            if row.limite_inferior <= ingreso <= row.limite_superior:
                break
            r = row
        base = ingreso - r.limite_inferior
        isr_sin_subsidio = base * (r.tasa / 100.0) + r.cuota_fija
        
        tabla_s_obj = self.env['l10n_mx_payroll.hr_tabla_subsidio']
        tabla_id = tabla_s_obj.search([('name', '=', name)], order='limite_inferior asc')
        if not tabla_id:
            raise UserError("Error \n\nNo hay tabla de subsidio al empleo definida para el año %s"%name)
        rows = tabla_s_obj.browse(tabla_id)
        r = rows[0]
        for row in rows:
            if row.limite_superior < 0:
                row.limite_superior = float("inf")
            if row.limite_inferior <= ingreso <= row.limite_superior:
                break
            r = row
        isr = isr_sin_subsidio - r.subsidio
        return ingreso - isr