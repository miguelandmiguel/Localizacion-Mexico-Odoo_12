# -*- coding: utf-8 -*-
import logging

from io import BytesIO
from zipfile import ZipFile

from odoo import models

_logger = logging.getLogger(__name__)


class ReportZipAbstract(models.AbstractModel):
    _name = 'report.report_zip.abstract'
    _description = 'Abstract ZIP Report'

    def _get_objs_for_report(self, docids, data):
        if docids:
            ids = docids
        elif data and 'context' in data:
            ids = data["context"].get('active_ids', [])
        else:
            ids = self.env.context.get('active_ids', [])
        return self.env[self.env.context.get('active_model')].browse(ids)

    def create_zip_report(self, docids, data):
        objs = self._get_objs_for_report(docids, data)
        in_memory = BytesIO()
        zf = ZipFile(in_memory, mode="w")
        self.generate_zip_report(zf, data, objs)
        zf.close()
        in_memory.seek(0)
        return in_memory.read(), 'zip'

    def generate_zip_report(self, file_data, data, objs):
        raise NotImplementedError()


