# -*- coding: utf-8 -*-
import logging

from io import BytesIO
from odoo import models

_logger = logging.getLogger(__name__)


class ReportTxtAbstract(models.AbstractModel):
    _name = 'report.report_txt.abstract'
    _description = 'Abstract TXT Report'

    def _get_objs_for_report(self, docids, data):
        if docids:
            ids = docids
        elif data and 'context' in data:
            ids = data["context"].get('active_ids', [])
        else:
            ids = self.env.context.get('active_ids', [])
        return self.env[self.env.context.get('active_model')].browse(ids)

    def create_txt_report(self, docids, data):
        objs = self._get_objs_for_report(docids, data)
        file_data = BytesIO()
        self.generate_txt_report(file_data, data, objs)
        file_data.seek(0)
        return file_data.read(), 'txt'

    def generate_txt_report(self, file_data, data, objs):
        raise NotImplementedError()


