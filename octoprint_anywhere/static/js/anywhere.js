/*
 * View model for OctoPrint-Anywhere
 *
 * Author: Kenneth Jiang
 * License: AGPLv3
 */

(function () {
'use strict';

function AnywhereViewModel(parameters) {
    var self = this;

    self.regUrl = ko.observable('');
    self.registered = ko.observable(false);
    self.premiumEligible = ko.observable(false);
    self.premiumVideoEnabled= ko.observable(false);
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

    var setConfigVars = function(configResp) {
        self.regUrl(configResp.reg_url);
        self.registered(configResp.registered);
        self.premiumEligible(configResp.premium_eligible);
        self.premiumVideoEnabled(configResp.premium_video_enabled);
    };

    var notifyUser = function(text, type) {
        new PNotify({
                title: "OctoPrint Anywhere",
                text: text,
                type: type,
                hide: false,
            });
    }

    apiCommand({command: 'get_config'}, setConfigVars);

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

    self.enablePremiumVideoClicked = function(event) {
        apiCommand({command: 'enable_premium_video'}, function(result) {
            setConfigVars(result);
            notifyUser("OctoPrint settings changed successfully. Premium video streaming is now enabled. Enjoy!", "success");
        });
    };

    self.disablePremiumVideoClicked = function(event) {
        apiCommand({command: 'disable_premium_video'}, function(result) {
            setConfigVars(result);
            notifyUser("OctoPrint settings resotred successfully. Premium video streaming is now disabled.", "warn");
        });
    };
}


// view model class, parameters for constructor, container to bind to
OCTOPRINT_VIEWMODELS.push([
    AnywhereViewModel,

    // e.g. loginStateViewModel, settingsViewModel, ...
    [],

    // e.g. #settings_plugin_slicer, #tab_plugin_slicer, ...
    [ "#settings_plugin_anywhere", "#wizard_plugin_anywhere" ]
]);
}());
