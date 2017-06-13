/*
 * View model for OctoPrint-Anywhere
 *
 * Author: Kenneth Jiang
 * License: AGPLv3
 */

'use strict';

function AnywhereViewModel(parameters) {
    debugger;

}


// view model class, parameters for constructor, container to bind to
OCTOPRINT_VIEWMODELS.push([
    AnywhereViewModel,

    // e.g. loginStateViewModel, settingsViewModel, ...
    [ "printerStateViewModel", "printerProfilesViewModel" ],

    // e.g. #settings_plugin_slicer, #tab_plugin_slicer, ...
    [ "#settings_anywhere" ]
]);
