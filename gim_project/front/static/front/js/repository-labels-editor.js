$().ready(function() {

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
            TestButton.update_content_and_show('<div class="alert alert-error">An internal problem prevented us to do the test</div>');
        },
        on_popover_stop_propopagation_event: function(ev) {
            // mandatory to avoid events beeing propagated to the modal containing this popover
            ev.stopPropagation();
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
                .on('show', TestButton.on_popover_show)
                .on('shown', TestButton.on_popover_stop_propopagation_event)
                .on('hide', TestButton.on_popover_stop_propopagation_event)
                .on('hidden', TestButton.on_popover_stop_propopagation_event);
        }
    }; // TestButton
    TestButton.init();

    window.LabelTypeForm = {
        $modal: $('#label-type-edit-form'),
        $modal_body: $('#label-type-edit-form .modal-body'),
        $modal_footer: $('#label-type-edit-form .modal-footer'),
        $modal_submit: $('#label-type-edit-form .modal-footer button.submit'),
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
        labels_list_select2_options: {
            tokenSeparators: [",", ";"],
            maximumInputLength: 250
        },
        prepare_labels_list_select2: function() {
            $('#id_labels_list').select2(LabelTypeForm.labels_list_select2_options);
        },
        update: function() {
            LabelTypeForm.prepare_edit_mode_select2();
            LabelTypeForm.prepare_labels_list_select2();
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
        },
        init_modal: function(ev) {
            LabelTypeForm.$modal.modal({
                backdrop: 'static',
                show: false
            }).on('hide', LabelTypeForm.on_modal_hide)
              .on('hidden', LabelTypeForm.on_modal_hidden);
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
            LabelTypeForm.update_modal_body_and_show($link, '<div class="alert alert-error">An internal problem prevented us to display the form</div>');
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
        on_submit_done: function(data) {
            if (data.substr(0, 6) == '<form ') {
                // we have an error, the whole form is returned
                var $form = LabelTypeForm.get_form();
                $form.replaceWith(data);
                LabelTypeForm.update();
                LabelTypeForm.$modal_body.scrollTop(0);
            } else {
                // no error, we replace the whole content
                $('.container-fluid .row-fluid.label-type').remove();
                $('.container-fluid .row-fluid.row-header').after(data);
                LabelTypeForm.$modal.modal('hide');
            }
            LabelTypeForm.$modal_submit.removeClass('loading');
        },
        on_submit_failed: function() {
            LabelTypeForm.$modal_submit.removeClass('loading');
            LabelTypeForm.$modal_footer.prepend('<div class="alert alert-error">An internal problem prevented us to save your changes</div>');
        },
        on_form_submit: function(ev) {
            ev.preventDefault();
            ev.stopPropagation();
            LabelTypeForm.$modal_submit.addClass('loading');
            LabelTypeForm.$modal_footer.find('.alert').remove();
            var $form = LabelTypeForm.get_form();
            $.post($form.attr('action'), $form.serialize())
                .done(LabelTypeForm.on_submit_done)
                .fail(LabelTypeForm.on_submit_failed);
        },
        init: function(labels) {
            var $document = $(document);
            LabelTypeForm.labels_list_select2_options.tags = labels;
            LabelTypeForm.init_modal();
            $document.on('click', '.btn-edit-label-type a', LabelTypeForm.on_link_click);
            $document.on('submit', '#label-type-form', LabelTypeForm.on_form_submit);
            LabelTypeForm.$modal_submit.on('click', LabelTypeForm.on_form_submit);
            $document.on('click', '.label-type-samples li', LabelTypeForm.on_sample_click);
        }
    }; // LabelTypeForm

});
