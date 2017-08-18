/*
 * View model for OctoPrint-Anywhere
 *
 * Author: Kenneth Jiang
 * License: AGPLv3
 */

'use strict';

function AnywhereViewModel(parameters) {
    self.settingsViewModel = parameters[2];

    $("#reset-re-register").click(function(event) {
        $.ajax('/api/plugin/anywhere', {
            method: "POST",
            contentType: 'application/json',
            data: JSON.stringify({ command: 'reset_config' })
        });
    });
}


// view model class, parameters for constructor, container to bind to
OCTOPRINT_VIEWMODELS.push([
    AnywhereViewModel,

    // e.g. loginStateViewModel, settingsViewModel, ...
    [ "printerStateViewModel", "printerProfilesViewModel", "settingsViewModel" ],

    // e.g. #settings_plugin_slicer, #tab_plugin_slicer, ...
    [ "#plugin_anywhere" ]
]);
