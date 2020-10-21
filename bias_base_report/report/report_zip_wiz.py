# -*- coding: utf-8 -*-

import logging
from odoo import models
import datetime

_logger = logging.getLogger(__name__)

class ReportZip(models.AbstractModel):
    _name = 'report.bias_base_report.report_zip_wiz'
    _inherit = 'report.report_zip.abstract'

    def __init__(self, pool, cr):
        self.sheet_header = None

    def generate_zip_report(self, file_data, data, objects):
        report = objects
        company_id = self.env.user.company_id
        name = report.name

        for line in report.report_file_ids:
            file_data.writestr(line.name, line.filereport)
            _logger.info('------------ line %s '%(line.filereport) )