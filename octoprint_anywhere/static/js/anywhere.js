/*
 * View model for OctoPrint-Anywhere
 *
 * Author: Kenneth Jiang
 * License: AGPLv3
 */

(function () {
'use strict';

PNotify.prototype.options.confirm.buttons = [];

function AnywhereViewModel(parameters) {
    var self = this;

    self.regUrl = ko.observable('');
    self.registered = ko.observable(false);
    self.tokenReset = ko.observable(false);
    self.sending = ko.observable(false);

    var apiCommand = function(cmd, callback, errorCallback) {
        $.ajax('/api/plugin/anywhere', {
            method: "POST",
            contentType: 'application/json',
            data: JSON.stringify(cmd),
            success: callback,
            error: errorCallback
        });
    };

    var setConfigVars = function(configResp) {
        self.regUrl(configResp.reg_url);
        self.registered(configResp.registered);
        var picameraErrorAcked = localStorage.getItem("octoprint_anywhere.picameraErrorAcked");
        if (configResp.picamera_error && !picameraErrorAcked) {
            new PNotify({
                title: "OctoPrint Anywhere",
                text: "<p>Failed to detect and turn on Pi Camera. Webcam feed will be streaming at 3 FPS. If you want 24 FPS streaming, please make sure Pi Camera is plugged in correctly.</p><a href='https://www.getanywhere.io/assets/oa10.html#picamera'>Learn more >>></a>",
                type: "warning",
                hide: false,
                confirm: {
                    confirm: true,
                    buttons: [
                        {
                            text: "Ignore",
                            click: function(notice) {
                                localStorage.setItem("octoprint_anywhere.picameraErrorAcked", true);
                                notice.remove();
                            }
                        },
                    ]
                },
                buttons: {
                    closer: false,
                    sticker: false
                },
            });
        }
    };

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
