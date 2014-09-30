$().ready(function() {
    var $document = $(document);

    var escapeMarkup = function (markup) {
        var replace_map = {
            '\\': '&#92;',
            '&': '&amp;',
            '<': '&lt;',
            '>': '&gt;',
            '"': '&quot;',
            "'": '&#39;',
            "/": '&#47;'
        };
        return String(markup).replace(/[&<>"'\/\\]/g, function (match) {
            return replace_map[match[0]];
        });
    };

    var redraw_full_content = function(data) {
        $('.container-fluid').children('.row-fluid.label-type, .alert').remove();
        $('#labels-editor-content').html(data);
    }

    var LabelEditor = {
        opened_popover: null,
        name_change_interval: null,
        popover_options: {
            title: '<strong style="border-bottom-color: #%(color)s">%(name)s</strong>',
            content: $('#label-edit-form').html(),
            html: true,
            placement: function(tip, element) {
                var $tip = $(tip);

                // place the tip in the dom to get its width (will be redone exactly the same way in tooltip.js)
                $tip.detach().css({ top: 0, left: 0, display: 'block' });
                this.options.container ? $tip.appendTo(this.options.container) : $tip.insertAfter(this.$element)

                var width = tip.offsetWidth + 10,  // arrow size
                    pos = this.getPosition();

                return (document.body.offsetWidth < pos.right + width) ? 'left' : 'right';
            },
            trigger: 'manual',
        },
        success_tooltip_options: {
            template: '<div class="tooltip success"><div class="tooltip-arrow"></div><div class="tooltip-inner"></div></div>',
        },
        spectrum_options: {
            showInitial: true,
            showInput: true,
            showButtons: true,
            clickoutFiresChange: true,
            preferredFormat: "hex6",
            maxSelectionSize: 10,
            showPalette: true,
            showSelectionPalette: true,
            localStorageKey: "spectrum.label.color",
            palette: [
                ["rgb(0, 0, 0)", "rgb(67, 67, 67)", "rgb(102, 102, 102)", "rgb(153, 153, 153)","rgb(183, 183, 183)",
                "rgb(204, 204, 204)", "rgb(217, 217, 217)", "rgb(239, 239, 239)", "rgb(243, 243, 243)", "rgb(255, 255, 255)"],
                ["rgb(152, 0, 0)", "rgb(255, 0, 0)", "rgb(255, 153, 0)", "rgb(255, 255, 0)", "rgb(0, 255, 0)",
                "rgb(0, 255, 255)", "rgb(74, 134, 232)", "rgb(0, 0, 255)", "rgb(153, 0, 255)", "rgb(255, 0, 255)"],
                ["rgb(230, 184, 175)", "rgb(244, 204, 204)", "rgb(252, 229, 205)", "rgb(255, 242, 204)", "rgb(217, 234, 211)",
                "rgb(208, 224, 227)", "rgb(201, 218, 248)", "rgb(207, 226, 243)", "rgb(217, 210, 233)", "rgb(234, 209, 220)"],
                ["rgb(221, 126, 107)", "rgb(234, 153, 153)", "rgb(249, 203, 156)", "rgb(255, 229, 153)", "rgb(182, 215, 168)",
                "rgb(162, 196, 201)", "rgb(164, 194, 244)", "rgb(159, 197, 232)", "rgb(180, 167, 214)", "rgb(213, 166, 189)"],
                ["rgb(204, 65, 37)", "rgb(224, 102, 102)", "rgb(246, 178, 107)", "rgb(255, 217, 102)", "rgb(147, 196, 125)",
                "rgb(118, 165, 175)", "rgb(109, 158, 235)", "rgb(111, 168, 220)", "rgb(142, 124, 195)", "rgb(194, 123, 160)"],
                ["rgb(166, 28, 0)", "rgb(204, 0, 0)", "rgb(230, 145, 56)", "rgb(241, 194, 50)", "rgb(106, 168, 79)",
                "rgb(69, 129, 142)", "rgb(60, 120, 216)", "rgb(61, 133, 198)", "rgb(103, 78, 167)", "rgb(166, 77, 121)"],
                ["rgb(133, 32, 12)", "rgb(153, 0, 0)", "rgb(180, 95, 6)", "rgb(191, 144, 0)", "rgb(56, 118, 29)",
                "rgb(19, 79, 92)", "rgb(17, 85, 204)", "rgb(11, 83, 148)", "rgb(53, 28, 117)", "rgb(116, 27, 71)"],
                ["rgb(91, 15, 0)", "rgb(102, 0, 0)", "rgb(120, 63, 4)", "rgb(127, 96, 0)", "rgb(39, 78, 19)",
                "rgb(12, 52, 61)", "rgb(28, 69, 135)", "rgb(7, 55, 99)", "rgb(32, 18, 77)", "rgb(76, 17, 48)"]
            ]
        },
        finalize_spectrum_options: function() {
            $.extend(LabelEditor.spectrum_options, {
                move: LabelEditor.on_spectrum_change,
                change: LabelEditor.on_spectrum_change,
                hide: LabelEditor.on_spectrum_hide
            });
        },
        update_color: function($color_input, color) {
            if (!color) {
                color = '#' + $color_input.val();
            }
            $color_input.data('label-title').css('border-bottom-color', color);
        },
        on_spectrum_change: function(color) {
            LabelEditor.update_color($(this), color.toHexString());
        },
        on_spectrum_hide: function(ev) {
            var $color_input = $(this);
            $color_input.val($color_input.val().replace('#',  ''))
            LabelEditor.update_color($color_input);
        },
        update_name: function($name_input) {
            var $label_title = $name_input.data('label-title');
            if ($label_title) {
                $label_title.text($name_input.val().trim() || '...');
            }
        },
        on_name_focus: function(ev) {
            var $name_input = $(this);
            if (LabelEditor.name_change_interval) {
                clearInterval(LabelEditor.name_change_interval);
            }
            LabelEditor.name_change_interval = setInterval(function() {
                LabelEditor.update_name($name_input);
            }, 300);
        },
        on_name_blur: function(ev) {
            if (LabelEditor.name_change_interval) {
                clearInterval(LabelEditor.name_change_interval);
                LabelEditor.name_change_interval = null;
            }
        },
        init_popover: function($label) {
            $label.data('parent-title', $label.parent().attr('title'));
            var $type_node = $label.closest('.label-type'),
                label_type_id = $type_node.data('label-type-id'),
                display_order = label_type_id ? !!$type_node.data('has-order') : false,
                name = escapeMarkup($label.data('name')),
                color = $label.data('color'),
                id = $label.data('id'),
                order = display_order ? $label.data('order') || '' : '',
                display_name = label_type_id ? $label.data('typed-name') || name : name,
                content = LabelEditor.popover_options.content
                            .replace('%(name)s', display_name)
                            .replace('%(color)s', color)
                            .replace('%(order)s', order)
                            .replace('%(label_type_id)s', label_type_id || '');
            if (!id) {
                content = content.replace('delete btn-loading', 'delete btn-loading hide');
                content = content.replace('%(id)s', "");
            } else {
                content = content.replace('%(id)s', id);
            }
            if (display_order) {
                content = content.replace('hide-order', 'show-order');
            }
            $label.popover($.extend(
                {},
                LabelEditor.popover_options,
                {
                    title: LabelEditor.popover_options.title
                            .replace('%(name)s', display_name || '...')
                            .replace('%(color)s', color),
                    content: content
                }
            )).on('shown.tooltip', LabelEditor.on_popover_shown);
            $label.removeAttr('title');
        },
        on_popover_shown: function(ev) {
            var $label = $(this),
                $popover = $label.next('.popover'),
                $color_input = $popover.find('input[name=color]'),
                $name_input = $popover.find('input[name=name]'),
                $label_title = $popover.find('.popover-title strong'),
                $to_focus = $name_input;
            $color_input.spectrum(LabelEditor.spectrum_options)
                        .data('label-title', $label_title);
            if ($popover.find('form').hasClass('show-order')) {
                $to_focus = $popover.find('input[name=order]');
            }
            $to_focus.focus();
            try {
                // position the cursor at the end
                var input = $to_focus[0];
                input.selectionStart = input.value.length;
            } catch(err) {}
        },
        open_popover: function($label) {
            LabelEditor.opened_popover = $label;
            $label.popover('show');
            $label.parent().removeAttr('title');
        },
        close_popover: function($label) {
            LabelEditor.opened_popover = null;
            $label.popover('hide');
            $label.parent().attr('title', $label.data('parent-title'));
        },
        on_label_click: function(ev) {
            ev.preventDefault();
            ev.stopPropagation();
            if (LabelEditor.opened_popover) {
                var opened_popover = LabelEditor.opened_popover;
                LabelEditor.close_popover(LabelEditor.opened_popover);
                if (opened_popover[0] == this) {
                    return;
                }
            }
            var $label = $(this);
            if (!$label.data('popover')) {
                LabelEditor.init_popover($label);
            }
            LabelEditor.open_popover($label);
        },
        on_form_cancel: function(ev) {
            ev.preventDefault();
            ev.stopPropagation();
            LabelEditor.close_popover($(this).closest('div.popover').prev());
        },
        on_name_keydown: function(ev) {
            if (ev.keyCode == 27) { // ESC
                $(this).closest('form').find('.cancel').focus().click();
            }
        },
        get_urls: function() {
            var $block = $('#label-edit-form');
            LabelEditor.base_edit_url = $block.data('edit-url');
            LabelEditor.base_delete_url = $block.data('delete-url');
            LabelEditor.create_url = $block.data('create-url');
        },
        redraw_content: function(data) {
            redraw_full_content(data);
            var $li_tooltip = $('.label-type ul.labels li[data-toggle=tooltip][data-trigger=manual]');
            if ($li_tooltip.length) {
                $li_tooltip.attr('original-title', $li_tooltip.attr('title'));
                $li_tooltip.removeAttr('title');
                $li_tooltip.tooltip(LabelEditor.success_tooltip_options);
                $li_tooltip.tooltip('show');
                $li_tooltip.attr('title', $li_tooltip.attr('original-title'));
                setTimeout(function() { $li_tooltip.tooltip('hide'); }, 2000);
            }
        },
        on_submit_done: function($form, data) {
            if (data.substr(0, 19) == '<div class="error">') {
                // we have an error, the whole form is returned
                $form.prepend(data);
                $form.find('.btn.submit').removeClass('loading');
            } else {
                // no error, we replace the whole content
                LabelEditor.redraw_content(data);
            }
        },
        on_submit_failed: function($form) {
            $form.prepend('<div class="alert alert-error">A problem prevented us to save the label</div>');
            $form.find('.btn.submit').removeClass('loading');
        },
        on_form_submit: function(ev) {
            ev.preventDefault();
            ev.stopPropagation();
            var $form = $(this),
                id = $form.data('id'),
                $save_btn = $form.find('.btn.submit'),
                url;
            if (id) {
                url = LabelEditor.base_edit_url.replace('label/0/', 'label/' + id + '/');
            } else {
                url = LabelEditor.create_url
            }
            LabelEditor.clean_errors($form);
            $save_btn.addClass('loading');
            $.post(url, $form.serialize())
                .done(function(data) { LabelEditor.on_submit_done($form, data); })
                .fail(function() { LabelEditor.on_submit_failed($form); });
        },
        clean_errors: function($form) {
            $form.children('.alert, .error').remove();
        },
        on_form_delete: function(ev) {
            var $delete_btn = $(this),
                $form = $delete_btn.closest('form');
            LabelEditor.clean_errors($form);
            if (!$delete_btn.data('popover')) {
                $delete_btn.popover();
            }
            $delete_btn.popover('show');
        },
        on_delete_done: function($form, data) {
            LabelEditor.redraw_content(data);
        },
        on_delete_failed: function($form) {
            $form.find('.btn.delete').removeClass('loading');
            $form.prepend('<div class="alert alert-error">A problem prevented us to delete this label</div>');
        },
        on_confirm_deletion: function(ev) {
            var $form = $(this).closest('form'),
                id = $form.data('id'),
                url = LabelEditor.base_delete_url.replace('label/0/', 'label/' + id + '/');
                data = {
                    csrfmiddlewaretoken: $form[0].csrfmiddlewaretoken.value
                },
                $delete_btn = $form.find('.btn.delete');
            $delete_btn.popover('hide');
            $delete_btn.addClass('loading');
            if (url && data.csrfmiddlewaretoken) {
                $.post(url, data)
                    .done(function(data) { LabelEditor.on_delete_done($form, data) })
                    .fail(function(data) { LabelEditor.on_delete_failed($form) });
            } else {
                LabelEditor.on_delete_failed($form);
            }
        },
        on_cancel_deletion: function(ev) {
            $(this).closest('.popover').prev().popover('hide');
        },
        init: function() {
            LabelEditor.get_urls();
            LabelEditor.finalize_spectrum_options();
            $document.on('click', '.label-type ul.labels li a', LabelEditor.on_label_click);
            $document.on('focus', '.label-edit-form input[name=name]', LabelEditor.on_name_focus);
            $document.on('blur', '.label-edit-form input[name=name]', LabelEditor.on_name_blur);
            $document.on('keydown', '.label-edit-form input[name=name]', LabelEditor.on_name_keydown);
            $document.on('click', '.label-edit-form .btn.cancel', LabelEditor.on_form_cancel);
            $document.on('click', '.label-edit-form .btn.delete', LabelEditor.on_form_delete);
            $document.on('submit', '.label-edit-form', LabelEditor.on_form_submit);
            $document.on('click', '.label-edit-form .cancel-deletion', LabelEditor.on_cancel_deletion);
            $document.on('click', '.label-edit-form .confirm-deletion', LabelEditor.on_confirm_deletion);
        }
    }; // LabelEditor
    LabelEditor.init();


    var TestButton = {
        $button: $('#label-type-test-button'),
        initialized: false,
        update_content_and_show: function(content) {
            TestButton.$button.data('popover').options.content = content;
            TestButton.$button.popover('show');
            TestButton.initialized = false;
            TestButton.$button.removeClass('loading');
        },
        get_form: function() {
            return TestButton.$button.closest('.modal').find('.modal-body form');
        },
        on_test_done: function(data) {
            TestButton.update_content_and_show(data);
        },
        on_test_failed: function() {
            TestButton.update_content_and_show('<div class="alert alert-error">A problem prevented us to do the test</div>');
        },
        on_popover_show: function(ev) {
            if (!TestButton.initialized) {
                TestButton.initialized = true;
                TestButton.$button.addClass('loading');
                var $form = TestButton.get_form();
                $.post($form.data('preview-url'), $form.serialize())
                    .done(TestButton.on_test_done)
                    .fail(TestButton.on_test_failed);

                ev.preventDefault();
            }
        },
        init: function() {
            TestButton.$button.popover({html: true})
                .on('show.tooltip', TestButton.on_popover_show);
        }
    }; // TestButton
    TestButton.init();


    window.LabelTypeForm = {
        $modal: $('#label-type-edit-form'),
        $modal_body: $('#label-type-edit-form .modal-body'),
        $modal_footer: $('#label-type-edit-form .modal-footer'),
        $modal_submit: $('#label-type-edit-form .modal-footer button.submit'),
        $modal_delete: $('#label-type-edit-form .modal-footer button.delete'),
        edit_mode_texts: {
            1: 'The more powerful mode, you can enter a real regular expression to automatically assign labels to this group',
            2: 'This intermediate mode allow you to simply construct a format to automatically assign labels to this group',
            3: 'The simplest mode, you just have to choose manually which labels to add to this group'
        },
        get_form: function() {
            return $('#label-type-form');
        },
        edit_mode_select2_options: {
            formatResult: function(edit_mode) {
                var text = LabelTypeForm.edit_mode_texts[edit_mode.id];
                var result = '<strong>' + edit_mode.text + '</strong>';
                result += '<div class="note">' + text + '</div>';
                return result;
            },
            escapeMarkup: function(m) { return m; },
            dropdownCssClass: 'edit-mode-dropdown'
        },
        prepare_edit_mode_select2: function() {
            $('#id_edit_mode').select2(
                LabelTypeForm.edit_mode_select2_options
            ).change(LabelTypeForm.on_edit_mode_changed);
        },
        on_edit_mode_changed: function(ev) {
            LabelTypeForm.get_form().removeClass('mode1 mode2 mode3').addClass('mode' + ev.val);
        },
        format_labels_list_select2: function(state) {
            if (state.children) {
                return state.text;
            }
            var data = LabelTypeForm.labels_data[state.id];
            return '<span style="border-bottom-color: #' + data.color + '">' + data.name + '</span>';
        },
        labels_list_select2_options: {
            tokenSeparators: [",", ";"],
            maximumInputLength: 250,
            closeOnSelect: false,
            dropdownCssClass: 'select2-labels',
            formatSelection: function(state) { return LabelTypeForm.format_labels_list_select2(state); },
            formatResult: function(state) { return LabelTypeForm.format_labels_list_select2(state); }
        },
        prepare_labels_list_select2: function() {
            var labels = $('#id_labels_list').data('labels');
            LabelTypeForm.labels_list_select2_options.tags = $.map(labels, function(value, key) { 
                return key;
            }).sort(function(a, b) {
               return a.toLowerCase().localeCompare(b.toLowerCase());
            });
            LabelTypeForm.labels_data = labels;
            $('#id_labels_list').select2(LabelTypeForm.labels_list_select2_options);
        },
        update: function() {
            LabelTypeForm.prepare_edit_mode_select2();
            LabelTypeForm.prepare_labels_list_select2();
            LabelTypeForm.$modal_delete.toggle(!!LabelTypeForm.get_form().data('delete-url'));
        },
        on_sample_click: function(ev) {
            ev.preventDefault();
            var $li = $(this),
                $target = $($li.closest('.label-type-samples').data('target')),
                content = $li.find('strong').text().replace('&lt;', '<').replace('&gt;', '>');
            $target.val(content);
        },
        on_modal_hide: function(ev) {
            LabelTypeForm.$modal_body.scrollTop(0);
            LabelTypeForm.$modal_footer.find('.alert').remove();
        },
        on_modal_hidden: function(ev) {
            TestButton.$button.popover('hide');
            LabelTypeForm.$modal_delete.popover('hide');
        },
        init_modal: function(ev) {
            LabelTypeForm.$modal.modal({
                backdrop: 'static',
                show: false
            }).on('hide.modal', LabelTypeForm.on_modal_hide)
              .on('hidden.modal', LabelTypeForm.on_modal_hidden);
        },
        update_modal_body_and_show: function($link, html) {
            LabelTypeForm.$modal_body.html(html);
            LabelTypeForm.$modal.modal('show');
            $link.removeClass('loading');
        },
        on_load_done: function($link, data) {
            LabelTypeForm.update_modal_body_and_show($link, data);
            $('.label-type .box-header .title .label').remove();
        },
        on_load_failed: function($link) {
            LabelTypeForm.update_modal_body_and_show($link, '<div class="alert alert-error">A problem prevented us to display the form</div>');
        },
        on_link_click: function(ev) {
            ev.preventDefault();
            ev.stopPropagation();

            var $link = $(this);

            $link.addClass('loading');

            $.get($link.attr('href'))
                .done(function(data) {
                    LabelTypeForm.on_load_done($link, data);
                })
                .fail(function(data) {
                    LabelTypeForm.on_load_failed($link);
                });

        },
        redraw_content: function(data) {
            redraw_full_content(data);
            LabelTypeForm.$modal.modal('hide');
            var $just_label = $('.label-type .box-header .title .label');
            if ($just_label.length) {
                 setTimeout(function() { $just_label.hide(); }, 2000);
            }
        },
        on_submit_done: function(data) {
            if (data.substr(0, 6) == '<form ') {
                // we have an error, the whole form is returned
                var $form = LabelTypeForm.get_form();
                $form.replaceWith(data);
                LabelTypeForm.update();
                LabelTypeForm.$modal_body.scrollTop(0);
            } else {
                // no error, we replace the whole content
                LabelTypeForm.redraw_content(data);
            }
            LabelTypeForm.$modal_submit.removeClass('loading');
        },
        on_submit_failed: function() {
            LabelTypeForm.$modal_submit.removeClass('loading');
            LabelTypeForm.$modal_footer.prepend('<div class="alert alert-error">A problem prevented us to save the group</div>');
        },
        on_form_submit: function(ev) {
            ev.preventDefault();
            ev.stopPropagation();
            TestButton.$button.popover('hide');
            LabelTypeForm.$modal_submit.addClass('loading');
            LabelTypeForm.$modal_footer.find('.alert').remove();
            var $form = LabelTypeForm.get_form();
            $.post($form.attr('action'), $form.serialize())
                .done(LabelTypeForm.on_submit_done)
                .fail(LabelTypeForm.on_submit_failed);
        },
        on_cancel_deletion: function(ev) {
            LabelTypeForm.$modal_delete.popover('hide');
        },
        on_delete_done: function(data) {
            LabelTypeForm.redraw_content(data);
            LabelTypeForm.$modal_delete.removeClass('loading');
        },
        on_delete_failed: function() {
            LabelTypeForm.$modal_delete.removeClass('loading');
            LabelTypeForm.$modal_footer.prepend('<div class="alert alert-error">A problem prevented us to delete this group</div>');
        },
        on_confirm_deletion: function(ev) {
            LabelTypeForm.$modal_delete.popover('hide');
            LabelTypeForm.$modal_delete.addClass('loading');
            var $form = LabelTypeForm.get_form(),
                url = $form.data('delete-url'),
                data = {
                    csrfmiddlewaretoken: $form[0].csrfmiddlewaretoken.value
                };
            if (url && data.csrfmiddlewaretoken) {
                $.post(url, data)
                    .done(LabelTypeForm.on_delete_done)
                    .fail(LabelTypeForm.on_delete_failed);
            } else {
                LabelTypeForm.on_delete_failed();
            }
        },
        init_deletion: function() {
            LabelTypeForm.$modal_delete.popover();
            LabelTypeForm.$modal_footer.on('click', '.cancel-deletion', LabelTypeForm.on_cancel_deletion);
            LabelTypeForm.$modal_footer.on('click', '.confirm-deletion', LabelTypeForm.on_confirm_deletion);
        },
        init: function() {
            LabelTypeForm.init_modal();
            $document.on('click', '.btn-edit-label-type a', LabelTypeForm.on_link_click);
            $document.on('submit', '#label-type-form', LabelTypeForm.on_form_submit);
            LabelTypeForm.$modal_submit.on('click', LabelTypeForm.on_form_submit);
            $document.on('click', '.label-type-samples li', LabelTypeForm.on_sample_click);
            LabelTypeForm.init_deletion();
        }
    }; // LabelTypeForm

});
