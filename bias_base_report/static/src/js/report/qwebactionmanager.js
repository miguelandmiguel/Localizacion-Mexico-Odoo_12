odoo.define('bias_base_report.report', function(require){
'use strict';

    var ActionManager = require('web.ActionManager');
    var core = require('web.core');
    var crash_manager = require('web.crash_manager');
    var framework = require('web.framework');
    var session = require('web.session');

    var ActionManager = require('web.ActionManager');
    ActionManager.include({

        _downloadReport: function (url) {
            var url_report = url;
            var report_type = url.split('/')[2];
            if (report_type === 'xlsx') {
                framework.blockUI();
                var def = $.Deferred();
                var type = '' + url.split('/')[2];
                var blocked = !session.get_file({
                    url: url_report,
                    data: {
                        data: JSON.stringify([url, type]),
                    },
                    success: def.resolve.bind(def),
                    error: function () {
                        crash_manager.rpc_error.apply(crash_manager, arguments);
                        def.reject();
                    },
                    complete: framework.unblockUI,
                });
                if (blocked) {
                    var message = _t('A popup window with your report was blocked. You ' +
                                     'may need to change your browser settings to allow ' +
                                     'popup windows for this page.');
                    this.do_warn(_t('Warning'), message, true);
                }
                return def;
            }else{
                return this._super.apply(this, arguments);
            }
        },

        _executeReportAction: function (action, options) {
            if (action.report_type === 'xlsx') {
                return this._triggerDownload(action, options, 'xlsx');
            }
            else {
                return this._super.apply(this, arguments);
            }
        },

        _makeReportUrls: function (action) {
            if (action.report_type === 'xlsx') {
                var reportUrls = {
                    xlsx: '/report/xlsx/' + action.report_name,
                };
                if (_.isUndefined(action.data) || _.isNull(action.data) ||
                    (_.isObject(action.data) && _.isEmpty(action.data))) {
                    if (action.context.active_ids) {
                        var activeIDsPath = '/' + action.context.active_ids.join(',');
                        reportUrls = _.mapObject(reportUrls, function (value) {
                            return value += activeIDsPath;
                        });
                    }
                } else {
                    var serializedOptionsPath = '?options=' + encodeURIComponent(JSON.stringify(action.data));
                    serializedOptionsPath += '&context=' + encodeURIComponent(JSON.stringify(action.context));
                    reportUrls = _.mapObject(reportUrls, function (value) {
                        return value += serializedOptionsPath;
                    });
                }
                return reportUrls;
            }else{
                return this._super.apply(this, arguments);
            }

        },

    });
});