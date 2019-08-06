# -*- coding: utf-8 -*-


# 2:22
import io
import functools
import base64

from lxml import etree
from lxml.objectify import fromstring
from suds.client import Client

import json
import logging
import requests

import werkzeug
import werkzeug.exceptions
import werkzeug.utils
import werkzeug.wrappers
import werkzeug.wsgi
from collections import OrderedDict
from werkzeug.urls import url_decode, iri_to_uri

import odoo
import odoo.modules.registry
from odoo.api import call_kw, Environment
from odoo.modules import get_resource_path
from odoo.tools import crop_image, topological_sort, html_escape, pycompat
from odoo.tools.mimetypes import guess_mimetype
from odoo.tools.translate import _
from odoo.tools.misc import str2bool, xlwt, file_open
from odoo.tools.safe_eval import safe_eval
from odoo import http
from odoo.http import content_disposition, route, dispatch_rpc, request, \
    serialize_exception as _serialize_exception, Response
from odoo.exceptions import AccessError, UserError, AccessDenied
from odoo.models import check_method_name
from odoo.service import db, security

from odoo import tools

from odoo.addons.web.controllers import main as attach

_logger = logging.getLogger(__name__)

def serialize_exception(f):
    @functools.wraps(f)
    def wrap(*args, **kwargs):
        try:
            return f(*args, **kwargs)
        except Exception as e:
            _logger.exception("An exception occured during an http request")
            se = _serialize_exception(e)
            error = {
                'code': 200,
                'message': "Odoo Server Error",
                'data': se
            }
            return werkzeug.exceptions.InternalServerError(json.dumps(error))
    return wrap


def copy_filelike_to_filelike(src, dst, bufsize=16384):
    while True:
        buf = src.read(bufsize)
        if not buf:
            break
        dst.write(buf)


class Binary(attach.Binary):
    @route()
    @serialize_exception
    def upload_attachment(self, callback, model, id, ufile):
        if model == 'hr.expense':
            out = """<script language="javascript" type="text/javascript">
                    var win = window.top.window;
                    win.jQuery(win).trigger(%s, %s);
                    </script>"""
            args = []
            Model = request.env[model]
            model_id = Model.browse(int(id))
            files = request.httprequest.files.copy()
            for ufile_tmp in files.getlist('ufile'):
                if ufile_tmp.content_type == 'text/xml':
                    filename = ufile_tmp.filename
                    if request.httprequest.user_agent.browser == 'safari':
                        filename = unicodedata.normalize('NFD', ufile_tmp.filename)
                    message_post = ""
                    myBytesIO = ufile_tmp.stream
                    try:
                        bxml = myBytesIO.getvalue()
                        cfdi = fromstring(bxml)
                        res = model_id.get_validate_xml_cfdi(cfdi)
                        if res.get('type') == None:
                            return super(Binary, self).upload_attachment(
                                callback, model, id, ufile
                            )
                        if res.get('type') == 'out':
                            return out % (json.dumps(callback), json.dumps(args))
                    except Exception as e:
                        message_post = """<span style="color:red;" ><b>NO SE PUDO CARGAR EL XML </b></span><br/><span><b>Error: </b> %s</span><br />"""%(e) + message_post
                        model_id.message_post(body='%s'%message_post )
                        model_id.cfdi_uuid = None
                        return out % (json.dumps(callback), json.dumps(args))
                    else:
                        message_post = """<span style="color:red;" ><b>NO SE PUDO CARGAR EL XML </b></span><br/><span><b>Error: </b> %s</span><br />"""%(e) + message_post
                        model_id.message_post(body='%s'%message_post )
                        model_id.cfdi_uuid = None
                        return out % (json.dumps(callback), json.dumps(args))
                    ufile_tmp.stream = myBytesIO
        return super(Binary, self).upload_attachment(
            callback, model, id, ufile
        )