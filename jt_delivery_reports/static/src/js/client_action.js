odoo.define('jt_delivery_reports.delivery_report_client_action', function (require) {
"use strict";

var AbstractAction = require('web.AbstractAction');
var core = require('web.core');
var Dialog = require('web.Dialog');
var Session = require('web.session');
var _t = core._t;

var DeliveryAction = AbstractAction.extend({
    template: 'dt_main_menu_report',

    // Function to call on event fire
    events: {
        // Function to close barcode app and display apps dashboard
        "click .button_close": function(){
            this.trigger_up('toggle_fullscreen');
            this.trigger_up('show_home_menu');
        },
        "click .button_report_d_order": function(){
            var action_report_delivery_order = {
                name: "Order de Entrega" ,
                type: 'ir.actions.act_window',
                res_model: 'del.rep.wiz',
                target: 'new',
                views: [[false, 'form']],
            }
            return this.do_action(action_report_delivery_order)
        },
        "click .button_report_int_tra": function(){
            var action_report_int_transfer = {
                name: "Transferencias Internas",
                type: 'ir.actions.act_window',
                res_model: 'tran.rep.wiz',
                target: 'new',
                views: [[false, 'form']],
            }
            return this.do_action(action_report_int_transfer)
        },
    },    
});

core.action_registry.add('delivery_reports_main_menu', DeliveryAction);
return {
    DeliveryAction: DeliveryAction,
};

});
