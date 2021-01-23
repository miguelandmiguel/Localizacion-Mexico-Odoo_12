# -*- coding: utf-8 -*-

from odoo.addons.web.controllers import main as report
from odoo.http import content_disposition, route, request

import json

class ReportController(report.ReportController):
    @route()
    def report_routes(self, reportname, docids=None, converter=None, **data):
        if converter not in ['xlsx', 'txt', 'zip']:
            return super(ReportController, self).report_routes(
                reportname, docids, converter, **data
            )
        report = request.env['ir.actions.report']._get_report_from_name(reportname)
        context = dict(request.env.context)
        if docids:
            docids = [int(i) for i in docids.split(',')]
        if data.get('options'):
            data.update(json.loads(data.pop('options')))
        if data.get('context'):
            data['context'] = json.loads(data['context'])
            if data['context'].get('lang'):
                del data['context']['lang']
            context.update(data['context'])

        if converter == 'xlsx':
            body = report.with_context(context).render_xlsx(
                docids, data=data
            )[0]
            bodyhttpheaders = [
                ('Content-Type', 'application/vnd.openxmlformats-'
                                 'officedocument.spreadsheetml.sheet'),
                ('Content-Length', len(body)),
                (
                    'Content-Disposition',
                    content_disposition(report.report_file + '.xlsx')
                )
            ]
        elif converter == 'txt':
            report_name = report.render_txt_name(docids, data=data) or '%s.txt'%( report.report_file )
            body = report.with_context(context).render_txt(
                docids, data=data
            )[0]
            bodyhttpheaders = [
                ('Content-Type', 'text/plain'),
                ('Content-Length', len(body)),
                (
                    'Content-Disposition',
                    content_disposition( report_name )
                )
            ]
        elif converter == 'zip':
            body = report.with_context(context).render_zip(
                docids, data=data
            )[0]
            bodyhttpheaders = [
                ('Content-Type', 'application/octet-stream'),
                ('Content-Length', len(body)),
                (
                    'Content-Disposition',
                    content_disposition(report.report_file + '.zip')
                )
            ]
        return request.make_response(body, headers=bodyhttpheaders)

        """
        if converter == 'xlsx':
            report = request.env['ir.actions.report']._get_report_from_name(
                reportname)
            context = dict(request.env.context)
            if docids:
                docids = [int(i) for i in docids.split(',')]
            if data.get('options'):
                data.update(json.loads(data.pop('options')))
            if data.get('context'):
                data['context'] = json.loads(data['context'])
                if data['context'].get('lang'):
                    del data['context']['lang']
                context.update(data['context'])
            xlsx = report.with_context(context).render_xlsx(
                docids, data=data
            )[0]
            xlsxhttpheaders = [
                ('Content-Type', 'application/vnd.openxmlformats-'
                                 'officedocument.spreadsheetml.sheet'),
                ('Content-Length', len(xlsx)),
                (
                    'Content-Disposition',
                    content_disposition(report.report_file + '.xlsx')
                )
            ]
            return request.make_response(xlsx, headers=xlsxhttpheaders)
        elif converter == 'txt':
            report = request.env['ir.actions.report']._get_report_from_name(
                reportname)
            context = dict(request.env.context)
            if docids:
                docids = [int(i) for i in docids.split(',')]
            if data.get('options'):
                data.update(json.loads(data.pop('options')))
            if data.get('context'):
                data['context'] = json.loads(data['context'])
                if data['context'].get('lang'):
                    del data['context']['lang']
                context.update(data['context'])
            txt = report.with_context(context).render_txt(
                docids, data=data
            )[0]
            txthttpheaders = [
                ('Content-Type', 'text/plain'),
                ('Content-Length', len(txt)),
                (
                    'Content-Disposition',
                    content_disposition(report.report_file + '.txt')
                )
            ]
            return request.make_response(txt, headers=txthttpheaders)
        elif converter == 'zip':
            report = request.env['ir.actions.report']._get_report_from_name(
                reportname)
            context = dict(request.env.context)
            if docids:
                docids = [int(i) for i in docids.split(',')]
            if data.get('options'):
                data.update(json.loads(data.pop('options')))
            if data.get('context'):
                data['context'] = json.loads(data['context'])
                if data['context'].get('lang'):
                    del data['context']['lang']
                context.update(data['context'])
            txt = report.with_context(context).render_txt(
                docids, data=data
            )[0]
            txthttpheaders = [
                ('Content-Type', 'text/plain'),
                ('Content-Length', len(txt)),
                (
                    'Content-Disposition',
                    content_disposition(report.report_file + '.txt')
                )
            ]
            return request.make_response(txt, headers=txthttpheaders)
        return super(ReportController, self).report_routes(
            reportname, docids, converter, **data
        )
        """
