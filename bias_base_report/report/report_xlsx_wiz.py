# -*- coding: utf-8 -*-

from odoo import models
import datetime

class ReportXlsx(models.AbstractModel):
    _name = 'report.bias_base_report.report_xlsx_wiz'
    _inherit = 'report.report_xlsx.abstract'

    def __init__(self, pool, cr):
        self.sheet_header = None

    def generate_xlsx_report(self, workbook, data, objects):
        report = objects
        company_id = self.env.user.company_id        
        name = report.name
        header = report.with_header
        freeze_panes = report.freeze_panes
        datas = eval(report.xlsx_datas)
        columns = eval(report.xlsx_columns)
        formats = eval(report.xlsx_formats)

        worksheet = workbook.add_worksheet( name )
        worksheet.hide_gridlines(2)

        workbook_format = {
            'title_company': workbook.add_format({'font_name':'Arial', 'font_size':18, 'bold':1, 'align':'center', 'valign':'vcenter', 'color':'#032C46'}),
            'header_format': workbook.add_format({'font_name':'Arial', 'font_size':12, 'bold':1, 'italic':0, 'align':'center', 'valign':'vcenter', 'fg_color':'#AAAAAA', 'color':'#FFFFFF', 'bottom': 2, 'bottom_color':'#AAAAAA', 'top': 2, 'top_color':'#AAAAAA' }),
            'string_center': workbook.add_format({'font_name':'Trebuchet MS', 'font_size':10, 'align':'center', 'valign':'vcenter', 'fg_color':'white', 'bottom': 4, 'bottom_color':'#D9D9D9'}),
            'string_left': workbook.add_format({'font_name':'Trebuchet MS', 'font_size':10, 'align':'left', 'valign':'vcenter', 'fg_color':'white', 'bottom': 4, 'bottom_color':'#D9D9D9'}),
            'string_rigth': workbook.add_format({'font_name':'Trebuchet MS', 'font_size':10, 'align':'right', 'valign':'vcenter', 'fg_color':'white', 'bottom': 4, 'bottom_color':'#D9D9D9'}),

            'string_center_bold': workbook.add_format({'font_name':'Trebuchet MS', 'font_size':10, 'bold':1, 'align':'center', 'valign':'vcenter', 'fg_color':'white', 'bottom': 4, 'bottom_color':'#D9D9D9'}),
            'string_left_bold': workbook.add_format({'font_name':'Trebuchet MS', 'font_size':10, 'bold':1, 'align':'left', 'valign':'vcenter', 'fg_color':'white', 'bottom': 4, 'bottom_color':'#D9D9D9'}),
            'string_rigth_bold': workbook.add_format({'font_name':'Trebuchet MS', 'font_size':10, 'bold':1, 'align':'right', 'valign':'vcenter', 'fg_color':'white', 'bottom': 4, 'bottom_color':'#D9D9D9'}),

            'percent': workbook.add_format({ 'font_name':'Trebuchet MS', 'font_size':10, 'align':'right', 'valign':'vcenter', 'num_format':'0.00%', 'fg_color':'white', 'bottom':4, 'bottom_color':'#D9D9D9' }),
            'percent_left': workbook.add_format({ 'font_name':'Trebuchet MS', 'font_size':10, 'align':'right', 'valign':'vcenter', 'num_format':'0.00%', 'fg_color':'white', 'bottom':4, 'bottom_color':'#D9D9D9' }),
            'percent_right': workbook.add_format({ 'font_name':'Trebuchet MS', 'font_size':10, 'align':'right', 'valign':'vcenter', 'num_format':'0.00%', 'fg_color':'white', 'bottom':4, 'bottom_color':'#D9D9D9'}),

            'money_format': workbook.add_format({'font_name':'Trebuchet MS', 'font_size':10, 'align':'right', 'valign':'vcenter', 'num_format':'$#,##0.00;[RED]-$#,##0.00', 'fg_color':'white', 'bottom': 4, 'bottom_color':'#D9D9D9'}),
            'integer_format': workbook.add_format({'font_name':'Trebuchet MS', 'font_size':10, 'align':'right', 'valign':'vcenter', 'num_format':'#,##0.00;[RED]-#,##0.00', 'fg_color':'white', 'bottom': 4, 'bottom_color':'#D9D9D9'}),
            'datetime': workbook.add_format({ 'font_name':'Trebuchet MS', 'font_size':10, 'align':'right', 'valign':'vcenter', 'num_format':'yyyy-mm-dd hh:mm:ss', 'fg_color':'white', 'bottom': 4, 'bottom_color':'#D9D9D9' }),
            'date': workbook.add_format({ 'font_name':'Trebuchet MS', 'font_size':10, 'align':'center', 'valign':'vcenter', 'num_format':'yyyy-mm-dd', 'fg_color':'white', 'bottom': 4, 'bottom_color':'#D9D9D9' }),
        }

        for column in columns:
            if len(column) == 2:
                worksheet.set_column(column[0], column[1])

        row = 1
        if header:
            worksheet.merge_range('A1:F1', company_id.name, workbook_format.get('title_company'))
            worksheet.merge_range('A3:F3', name, workbook_format.get('title_company'))
            row = 5
        
        if len(datas):
            if freeze_panes:
                worksheet.freeze_panes(row, 0)

            header = datas[0]
            body = datas[1:]
            worksheet.write_row('A%s'%(row), header, workbook_format.get('header_format'))
            row += 1

            datas_list = []
            for i, d in enumerate(body):
                datas_list.append(list(d))
            datas_list = zip(*datas_list)
            for i, d in enumerate(datas_list):
                try:
                    formato = workbook_format.get(formats[i], 'string_left')
                except:
                    formato = workbook_format.get('string_left')
                worksheet.write_column(row-1, i, d, formato)