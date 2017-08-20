/*
 * View model for OctoPrint-Anywhere
 *
 * Author: Kenneth Jiang
 * License: AGPLv3
 */

'use strict';

function AnywhereViewModel(parameters) {
    var self = this;

    self.regUrl = ko.observable('');
    self.registered = ko.observable(false);
    self.tokenReset = ko.observable(false);
    self.sending = ko.observable(false);

    var apiCommand = function(cmd, callback) {
        $.ajax('/api/plugin/anywhere', {
            method: "POST",
            contentType: 'application/json',
            data: JSON.stringify(cmd),
            success: callback
        });
    };

    apiCommand({command: 'get_config'}, function(result) {
        self.regUrl(result.reg_url);
        self.registered(result.registered);
    });

    self.resetButtonClicked = function(event) {
        self.sending(true);
        apiCommand({command: 'reset_config'}, function(result) {
            setTimeout(function() {
                self.regUrl(result.reg_url);
                self.registered(result.registered);
                self.tokenReset(true);
                self.sending(false);
            }, 500);
        });
    };
}


// view model class, parameters for constructor, container to bind to
OCTOPRINT_VIEWMODELS.push([
    AnywhereViewModel,

    // e.g. loginStateViewModel, settingsViewModel, ...
    [],

    // e.g. #settings_plugin_slicer, #tab_plugin_slicer, ...
    [ "#settings_plugin_anywhere" ]
]);
