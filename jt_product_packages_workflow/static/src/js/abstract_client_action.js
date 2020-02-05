odoo.define('jt_product_packages_workflow.picking_client_action', function (require) {
'use strict';

    var ClientAction = require('stock_barcode.ClientAction');
    var PickingAction = require('stock_barcode.picking_client_action');

    var core = require('web.core');
    var LinesWidget = require('stock_barcode.LinesWidget');

    var _t = core._t;

    function isChildOf(locationParent, locationChild) {
        return _.str.startsWith(locationChild.parent_path, locationParent.parent_path);
    }

    var PickingClientAction = PickingAction.extend({

        _onBarcodeScanned: function (barcode) {
            var superr = this._super.apply(this, arguments);
            if (this.actionParams.model === 'stock.picking') {
                this.$('.o_barcode_summary_location_src').toggleClass('o_barcode_summary_location_highlight', false);
                this.$('.o_barcode_summary_location_dest').toggleClass('o_barcode_summary_location_highlight', false);
                this.linesWidget._toggleScanMessage('scan_products');
            }
            return superr
        },

        _endBarcodeFlow: function() {
            this.location_barcode = undefined
            this.location_dest_barcode = undefined
            return this._super.apply(this, arguments);
        },

        start: function () {
            this._super.apply(this, arguments);
            if (this.actionParams.model === 'stock.picking') {
                this.$('.o_barcode_summary_location_src').toggleClass('o_barcode_summary_location_highlight', false);
                this.$('.o_barcode_summary_location_dest').toggleClass('o_barcode_summary_location_highlight', false);
                this.linesWidget._toggleScanMessage('scan_products');

                // To sore packages barcodes as global
                this.packages = []
                for(var i in this.currentState.package_ids){
                    for(var j in this.currentState.package_ids[i]){
                        if (j == 'name'){
                            this.packages.push(this.currentState.package_ids[i][j])
                        }
                    }
                }
            }
        },

        _incrementLines: function (params) {
            var line = this._findCandidateLineToIncrement(params);
            var isNewLine = false;
            if (line) {
                // Update the line with the processed quantity.
                if (params.product.tracking === 'none' ||
                    params.lot_id ||
                    params.lot_name
                    ) {
                    if (this.actionParams.model === 'stock.picking') {
                        line.qty_done += params.product.qty || 1;
                    } else if (this.actionParams.model === 'stock.inventory') {
                        line.product_qty += params.product.qty || 1;
                    }
                }
            } else {
                isNewLine = true;
                // Create a line with the processed quantity.
                if (params.product.tracking === 'none' ||
                    params.lot_id ||
                    params.lot_name
                    ) {
                    line = this._makeNewLine(params.product, params.barcode, params.product.qty || 1, params.package_id, params.result_package_id);
                } else {
                    line = this._makeNewLine(params.product, params.barcode, 0, params.package_id, params.result_package_id);
                }
                this._getLines(this.currentState).push(line);
                this.pages[this.currentPageIndex].lines.push(line);
            }
            if (this.actionParams.model === 'stock.picking') {
                if (params.lot_id) {
                    line.lot_id = [params.lot_id];
                }
                if (params.lot_name) {
                    line.lot_name = params.lot_name;
                }
            } else if (this.actionParams.model === 'stock.inventory') {
                if (params.lot_id) {
                    line.prod_lot_id = [params.lot_id, params.lot_name];
                }
            }
            return {
                'id': line.id,
                'virtualId': line.virtual_id,
                'lineDescription': line,
                'isNewLine': isNewLine,
            };
        },

        _step_source: function(barcode, linesActions) {
            this.currentStep = 'source';
            var errorMessage;

            // Set default source and location barcode
            this.location_barcode = this.currentState['location_id']['barcode']
            this.location_dest_barcode = this.currentState['location_dest_id']['barcode']

            // Set default source location (Automatically scan source location)
            var sourceLocation = this.locationsByBarcode[barcode];
            if (this.actionParams.model == 'stock.picking'){
                sourceLocation = this.locationsByBarcode[this.location_barcode];
            }

            /* Bypass this step in the following cases:
               - the picking is a receipt
               - the multi location group isn't active
            */
            if (sourceLocation  && ! (this.mode === 'receipt' || this.mode === 'no_multi_locations')) {
                if (! isChildOf(this.currentState.location_id, sourceLocation)) {
                    errorMessage = _t('This location is not a child of the main location.');
                    return $.Deferred().reject(errorMessage);
                } else {
                    linesActions.push([this.linesWidget.highlightLocation, [true]]);
                    if (this.actionParams.model === 'stock.picking') {
                        linesActions.push([this.linesWidget.highlightDestinationLocation, [false]]);
                    }
                    this.scanned_location = sourceLocation;
                    this.currentStep = 'product';
                    if (this.actionParams.model == 'stock.picking'){
                        return this._step_product(barcode, linesActions);
                        // return this._step_package(barcode, linesActions);
                    }
                    return $.when({linesActions: linesActions});
                }
            }
            /* Implicitely set the location source in the following cases:
                - the user explicitely scans a product
                - the user explicitely scans a lot
                - the user explicitely scans a package
            */
            // We already set the scanned_location even if we're not sure the
            // following steps will succeed. They need scanned_location to work.
            this.scanned_location = {
                id: this.pages ? this.pages[this.currentPageIndex].location_id : this.currentState.location_id.id,
                display_name: this.pages ? this.pages[this.currentPageIndex].location_name : this.currentState.location_id.display_name,
            };
            linesActions.push([this.linesWidget.highlightLocation, [true]]);
            if (this.actionParams.model === 'stock.picking') {
                linesActions.push([this.linesWidget.highlightDestinationLocation, [false]]);
            }

            return this._step_product(barcode, linesActions).then(function (res) {
                return $.when({linesActions: res.linesActions});
            }, function (specializedErrorMessage) {
                delete this.scanned_location;
                this.currentStep = 'source';
                if (specializedErrorMessage){
                    return $.Deferred().reject(specializedErrorMessage);
                }
                var errorMessage = _t('You are expected to scan a source location.');
                return $.Deferred().reject(errorMessage);
            });
        },

        _step_product: function(barcode, linesActions) {
            var self = this;

            this.currentStep = 'product';
            var errorMessage;

            var context = {}
            context['default_picking_id'] = this.actionParams.pickingId

            var action_backorder_wizard = {
                name: 'Create Partial Delivery?',
                type: 'ir.actions.act_window',
                res_model: 'barcode.deliver.products.wizard',
                target: 'new',
                views: [[false, 'form']],
                context: context,
            }

            var product = this._isProduct(barcode);
            if (product) {
                if (product.tracking !== 'none') {
                    this.currentStep = 'lot';
                }

                var line = undefined;
                if (this.actionParams.model === 'stock.picking'){
                    line = this._findCandidateLineToIncrement({'product': product, 'barcode': barcode});
                    if (!line){
                        return $.Deferred().reject(_t('This product is not a part of this order.'));
                    }
                }
                var res = this._incrementLines({'product': product, 'barcode': barcode});

                if (res.isNewLine) {
                    if (this.actionParams.model === 'stock.inventory') {
                        // FIXME sle: add owner_id, prod_lot_id, owner_id, product_uom_id
                        return this._rpc({
                            model: 'product.product',
                            method: 'get_theoretical_quantity',
                            args: [
                                res.lineDescription.product_id.id,
                                res.lineDescription.location_id.id,
                            ],
                        }).then(function (theoretical_qty) {
                            res.lineDescription.theoretical_qty = theoretical_qty;
                            linesActions.push([self.linesWidget.addProduct, [res.lineDescription, self.actionParams.model]]);
                            self.scannedLines.push(res.id || res.virtualId);
                            return $.when({linesActions: linesActions});
                        });
                    } else {
                        return $.Deferred().reject(_t('This product is not a part of this order.'));
                        // linesActions.push([this.linesWidget.addProduct, [res.lineDescription, this.actionParams.model]]);
                    }
                } else {
                    // Set default source location (Automatically scan source location)
                    var product_uom_qty = res['lineDescription']['product_uom_qty'];
                    var qty_done = (res['lineDescription']['qty_done']) - 1;

                    if (product.tracking === 'none') {
                        if (this.actionParams.model === 'stock.picking'){
                            if (qty_done < product_uom_qty){
                                this.do_action(action_backorder_wizard);
                                linesActions.push([this.linesWidget.incrementProduct, [res.id || res.virtualId, product.qty || 1, this.actionParams.model]]);

                                if (res['lineDescription']['qty_done'] == product_uom_qty){
                                    return this._step_destination(this.location_dest_barcode, linesActions);
                                }
                            }
                            else{
                                return this._step_destination(this.location_dest_barcode, linesActions);
                            }
                        }
                        else{
                            this.do_action(action_backorder_wizard);
                            linesActions.push([this.linesWidget.incrementProduct, [res.id || res.virtualId, product.qty || 1, this.actionParams.model]]);
                        }

                    } else {
                        if (this.actionParams.model === 'stock.picking'){
                            if (qty_done < product_uom_qty){
                                this.do_action(action_backorder_wizard);
                                linesActions.push([this.linesWidget.incrementProduct, [res.id || res.virtualId, 0, this.actionParams.model]]);

                                if (res['lineDescription']['qty_done'] == product_uom_qty){
                                    return this._step_destination(this.location_dest_barcode, linesActions);
                                }
                            }
                            else{
                                return this._step_destination(this.location_dest_barcode, linesActions);
                            }
                        }
                        else{
                            linesActions.push([this.linesWidget.incrementProduct, [res.id || res.virtualId, 0, this.actionParams.model]]);
                        }
                    }
                }
                this.scannedLines.push(res.id || res.virtualId);
                return $.when({linesActions: linesActions});
            } else {
                var success = function (res) {
                    return $.when({linesActions: res.linesActions});
                };
                var fail = function (specializedErrorMessage) {
                    this.currentStep = 'product';
                    if (specializedErrorMessage){
                        return $.Deferred().reject(specializedErrorMessage);
                    }
                    if (! self.scannedLines.length) {
                        if (self.groups.group_tracking_lot) {
                            errorMessage = _t("You are expected to scan one or more products or a package available at the picking's location");
                        } else {
                            errorMessage = _t('You are expected to scan one or more products.');
                        }
                        return $.Deferred().reject(errorMessage);
                    }

                    var destinationLocation = self.locationsByBarcode[barcode];
                    if (destinationLocation) {
                        return self._step_destination(barcode, linesActions);
                    } else {
                        errorMessage = _t('You are expected to scan more products or a destination location.');
                        return $.Deferred().reject(errorMessage);
                    }
                };
                return self._step_lot(barcode, linesActions).then(success, function () {
                    return self._step_package(barcode, linesActions).then(success, fail);
                });
            }
        },

        _step_package: function (barcode, linesActions) {
            // search stock.quant.packe location_id child_of main location ; name barcode
            // then make a search on quants package_id chilf of barcode
            // call a `_packageMakeNewLines` methode overriden by picking and inventory or increment the existing lines
            // fill linesActions + scannedLines
            // if scannedLines isn't set, the caller will warn

            var context = {}
            context['default_picking_id'] = this.actionParams.pickingId

            var action_backorder_wizard = {
                name: 'Create Partial Delivery?',
                type: 'ir.actions.act_window',
                res_model: 'barcode.deliver.products.wizard',
                target: 'new',
                views: [[false, 'form']],
                context: context,
            }

            if (! this.groups.group_tracking_lot) {
                return $.Deferred().reject();
            }
            this.currentStep = 'product';
            var destinationLocation = this.locationsByBarcode[barcode];
            if (destinationLocation) {
                return $.Deferred().reject();
            }

            var self = this;
            var search_read_quants = function () {
                return self._rpc({
                    model: 'stock.quant.package',
                    method: 'search_read',
                    domain: [['name', '=', barcode], ['location_id', 'child_of', self.scanned_location.id]],
                    limit: 1,
                });
            };
            var read_products = function (product) {
                return self._rpc({
                    model: 'product.product',
                    method: 'read',
                    args: [product],
                    limit: 1,
                });
            };
            var get_contained_quants = function (package_id) {
                return self._rpc({
                    model: 'stock.quant',
                    method: 'search_read',
                    domain: [['package_id', '=', package_id]],
                });
            };
            var package_already_scanned = function (package_id, quants) {
                // FIXME: to improve, at the moment we consider that a package is already scanned if
                // there are as many lines having result_package_id set to the concerned package in
                // the current page as there should be if the package was scanned.
                var expectedNumberOfLines = quants.length;
                var currentNumberOfLines = 0;

                var currentPage = self.pages[self.currentPageIndex];
                for (var i=0; i < currentPage.lines.length; i++) {
                    var currentLine = currentPage.lines[i];
                    // FIXME sle: float_compare?
                    if (currentLine.package_id && currentLine.package_id[0] === package_id && currentLine.qty_done > 0) {
                        currentNumberOfLines += 1;
                    }
                }
                return currentNumberOfLines === expectedNumberOfLines;
            };
            return search_read_quants().then(function (packages) {
                if (packages.length) {
                    if (! self.packages.includes(barcode)){
                        return $.Deferred().reject(_t('You are not allowed to add different package than order.'));
                    }
                    else{
                        return self.do_action(action_backorder_wizard);
                    }

                    self.lastScannedPackage = packages[0].name;
                    return get_contained_quants(packages[0].id).then(function (quants) {
                        var packageAlreadyScanned = package_already_scanned(packages[0].id, quants);
                        if (packageAlreadyScanned) {
                            return $.Deferred().reject(_t('This package is already scanned.'));
                        }
                        var products_without_barcode = _.map(quants, function (quant) {
                            if (! (quant.product_id[0] in self.productsByBarcode)) {
                                return quant.product_id[0];
                            }
                        });
                        return read_products(products_without_barcode).then(function (products_without_barcode) {
                            _.each(quants, function (quant) {
                                // FIXME sle: not optimal
                                var product_barcode = _.findKey(self.productsByBarcode, function (product) {
                                    return product.id === quant.product_id[0];
                                });
                                var product = self.productsByBarcode[product_barcode];
                                if (! product) {
                                    var product_key = _.findKey(products_without_barcode, function (product) {
                                        return product.id === quant.product_id[0];
                                    });
                                    product = products_without_barcode[product_key];
                                }
                                product.qty = quant.quantity;

                                var res = self._incrementLines({
                                    product: product,
                                    barcode: product_barcode,
                                    product_barcode: product_barcode,
                                    package_id: [packages[0].id, packages[0].display_name],
                                    result_package_id: [packages[0].id, packages[0].display_name],
                                    lot_id: quant.lot_id[0],
                                    lot_name: quant.lot_id[1]
                                });
                                self.scannedLines.push(res.lineDescription.virtual_id);
                                if (! self.show_entire_packs) {
                                    if (res.isNewLine) {
                                        linesActions.push([self.linesWidget.addProduct, [res.lineDescription, self.actionParams.model, true]]);
                                    } else {
                                        linesActions.push([self.linesWidget.incrementProduct, [res.id || res.virtualId, quant.quantity, self.actionParams.model, true]]);
                                    }
                                }
                            });
                            return $.when({linesActions: linesActions});
                        });
                    });
                } else {
                    return $.Deferred().reject();
                }
            });
        },

        _validate: function () {
            var self = this;
            this.mutex.exec(function () {
                return self._save().then(function () {
                    var context = {}
                    context['from_barcode_screen'] = true
                    return self._rpc({
                        'model': self.actionParams.model,
                        'method': 'button_validate',
                        'args': [[self.actionParams.pickingId]],
                        'context': context,
                    }).then(function (res) {
                        var def = $.when();
                        var exitCallback = function (infos) {
                            if (infos !== 'special') {
                                self.do_notify(_t("Success"), _t("The transfer has been validated"));
                                self.trigger_up('exit');
                            }
                            core.bus.on('barcode_scanned', self, self._onBarcodeScannedHandler);
                        };
                        if (_.isObject(res)) {
                            var options = {
                                on_close: exitCallback,
                            };
                            return def.then(function () {
                                core.bus.off('barcode_scanned', self, self._onBarcodeScannedHandler);
                                return self.do_action(res, options);
                            });
                        } else {
                            return def.then(function () {
                                return exitCallback();
                            });
                        }
                    });
                });
            });
        },
    });

    core.action_registry.add('stock_barcode_picking_client_action', PickingClientAction);

    // return PickingClientAction;

});