/*global opener */
(function() {
    'use strict';
    var initData = JSON.parse(document.getElementById('django-admin-popup-response-constants').dataset.popupResponse);

    console.log('---', initData)

    // switch(initData.action) {
    // case 'change':
    //     opener.dismissChangeRelatedObjectPopup(window, initData.value, initData.obj, initData.new_value);
    //     break;
    // case 'delete':
    //     opener.dismissDeleteRelatedObjectPopup(window, initData.value);
    //     break;
    // default:
    //     opener.dismissAddRelatedObjectPopup(window, initData.value, initData.obj);
    //     break;
    // }


    let index = parent.layer.getFrameIndex(window.name);
    console.log('---index--', index);
    parent.layer.close(index);
    parent.window.location.reload();

})();
