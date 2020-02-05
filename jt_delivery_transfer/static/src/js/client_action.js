odoo.define('jt_delivery_transfer.DeliveryTransferMainMenu', function (require) {
"use strict";

var AbstractAction = require('web.AbstractAction');
var core = require('web.core');
var Dialog = require('web.Dialog');
var Session = require('web.session');

var _t = core._t;

var MainMenu = AbstractAction.extend({
    template: 'dt_main_menu',

    // Function to call on event fire
    events: {
        // Function to close barcode app and display apps dashboard
        "click .button_close": function(){
            this.mode = 'select';
            this.trigger_up('toggle_fullscreen');
            this.trigger_up('show_home_menu');
            core.bus.off('barcode_scanned', this, this._onBarcodeScannedHandler);
        },
        // Function to trigget internal transfer screen (After clicking user can scan package for internal transfer)
        "click .button_int_transfer": function(){
            $('#section_1').css({'display': 'none'});
            $('#section_2').css({'display': 'block'});
            $('.button_back').css({'display': 'inline'});
            this.mode = 'internal_transfer';
            core.bus.on('barcode_scanned', this, this._onBarcodeScannedHandler);
        },
        // Function to trigget stock delivery screen (After clicking user can scan package for stock delivery transfer)
        "click .button_stock_delivery": function(){
            this.mode = 'stock_delivery';
            $('#section_1').css({'display': 'none'});
            $('#section_2').css({'display': 'block'});
            $('.button_back').css({'display': 'inline'});
            this.mode = 'stock_delivery';
            core.bus.on('barcode_scanned', this, this._onBarcodeScannedHandler);
        },
        // Function to trigget delivery on request screen (After clicking user can scan package for delivery on request process)
        "click .button_delivery_on_request": function(){
            $('#section_1').css({'display': 'none'});
            $('#section_2').css({'display': 'block'});
            $('.button_back').css({'display': 'inline'});
            this.mode = 'delivery_on_request';
            core.bus.on('barcode_scanned', this, this._onBarcodeScannedHandler);
        },
        // Function to go back on "internal transfer and delivery" app dashboard
        "click .button_back": function(){
            $('#section_1').css({'display': 'block'});
            $('#section_2').css({'display': 'none'});
            $('.button_back').css({'display': 'none'});
            this.mode = 'select';
            core.bus.off('barcode_scanned', this, this._onBarcodeScannedHandler);
        },
    },

    // initialisation of global variable mode (for scanning mode like internal transfer, stock delviery, delivery on request, select mode )
    init: function(parent, action) {
        this._super.apply(this, arguments);
        this.mode = 'select';
    },

    // Main function to handle barcode scan (When user scan barcode this function call to handle scanned barcode and proceed for further)
    _onBarcodeScannedHandler: function (barcode) {

        var self = this;

        // Search scanned package using rpc
        var search_read_quants = function () {
            return self._rpc({
                model: 'stock.quant.package',
                method: 'search_read',
                domain: [['name', '=', barcode]],
                limit: 1,
            });
        };

        // Return screen to scanning process wizard for further calculation based on mode
        return search_read_quants().then(function (packages) {
            var flag = undefined

            var context = {}
            context['barcode'] = barcode

            // Prepare scan screen header based on scanning mode
            var name = undefined
            if (self.mode == 'internal_transfer'){
                name = 'Transferencia Interna';
            }
            if (self.mode == 'delivery_on_request'){
                name = 'Entrega de bajo pedido';
            }
            if (self.mode == 'stock_delivery'){
                name = 'Entrega de producto de stock';
            }

            // Prepare context to pass on wizard
            var action_transfer_wizard = {
                name: name,
                type: 'ir.actions.act_window',
                res_model: 'transfer.package.wizard',
                target: 'new',
                views: [[false, 'form']],
                context: context,
            }

            // Return to wizard (with context) if scanned package found
            if (packages.length) {
                flag = true
                context['package_id'] = packages[0].id
                context['package_name'] = packages[0].name
                context['mode'] = self.mode
                return self.do_action(action_transfer_wizard)
            }
            if (flag !== true){
                alert("Scanned barcode is not match with any package")
            }
        });
    },
});

core.action_registry.add('delivery_transfer_main_menu', MainMenu);

return {
    MainMenu: MainMenu,
};

});
