$().ready(function() {
    // receive data from ajax with a table+thead+tbody + 1 TR for a repo
    // insert/update in relevant tabs, remove in others
    function receive_data(data) {
        var $data_table = $(data),
            repo_name = $data_table.data('repo'),
            in_tabs = $data_table.data('in-tabs'),
            org_name = $data_table.children('thead').data('org');

        // remove existing entries
        $('table.repos tr[data-repo="' + repo_name + '"]').remove();

        // add new entries
        if (in_tabs) {
            in_tabs = eval(in_tabs);
            for (var i = 0; i < in_tabs.length; i++) {
                var $tab = $('#choose-' + in_tabs[i]);
                if (!$tab.length) { continue; }

                // check if we already have a table
                if (!$tab.find('table.repos').length) {
                    // no table found, add ours
                    var $new_table = $data_table.clone();
                    $new_table.removeData('repo');
                    $new_table.removeData('org');
                    var $empty_area = $tab.find('.empty-area');
                    $empty_area.before($new_table);
                    $empty_area.remove();
                    // ok done for this tab
                    continue;
                }

                // check if we already have the thead+tbody we need
                var $thead = $tab.find('thead.group-'+org_name);
                if (!$thead.length) {
                    // get the thead where to put our table before
                    var $thead_position = $tab.find('thead').filter(function() {
                        return org_name < $(this).data('org');
                    }).first();
                    if ($thead_position.length) {
                        // found one, insert before
                        $thead_position.before($data_table.clone().children());
                    } else {
                        // not found, insert at the end of the table
                        $tab.find('table.repos').append($data_table.clone().children())
                    }
                    // ok done for this tab
                    continue;
                }

                // table and thead are ok, found where to insert repo in the tbody
                var $tbody = $thead.next(),
                    $data_tr = $data_table.find('tbody tr'),
                    repo_name_lower = repo_name.toLowerCase();
                // get the tr where to put our one before
                var $tr_position = $tbody.children('tr').filter(function() {
                    return repo_name_lower < $(this).data('repo').toLowerCase()
                }).first();
                if ($tr_position.length) {
                    // found one, insert before
                    $tr_position.before($data_tr.clone());
                } else {
                    // not found, insert at the end of the list (tbody)
                    $tbody.append($data_tr.clone());
                }
            };
        }

        // clean empty tbody
        $('table.repos tbody').each(function() {
            var $tbody = $(this);
            if (!$tbody.children('tr').length) {
                $tbody.prev().remove();  // thead
                $tbody.remove();
            }
        });

        // clean empty tables
        $('table.repos').each(function() {
            var $table = $(this);
            if (!$table.children('tbody').length) {
                $table.after('<p class="empty-area">No repositories to show here !</p>');
                $table.remove();
            }
        })
    };

    $(document).on('submit', 'form', function(ev) {
        var $form = $(this);

        $form.find('button.btn-loading').addClass('loading');

        if (!$form.hasClass('toggle-form') && !$form.hasClass('repository-input')) {
            return;
        }

        var success_callback = receive_data,
            error_callback = function() {
                alert('Unable to do your action :(');
            };

        if (!$form.hasClass('toggle-form')) {
            success_callback = function(data) {
                receive_data(data);
                if (data.indexOf('<table') >= 0) {
                    $form.find('input[type=text]').val('');
                }
                $form.find('button').removeClass('loading');
                $form.find('input').focus();
            }
            error_callback = function() {
                error_callback();
                $form.find('button').removeClass('loading');
                $form.find('input').focus();
            }
        }

        $.post($form.attr('action'), $form.serialize())
            .done(success_callback)
            .fail(error_callback);

        ev.preventDefault();
        ev.stopPropagation();
    });

    // load "starred" tab when showing it
    $('a[href=#choose-starred]').on('show.tab', function() {
        var $deferrable = $('#choose-starred .deferrable');
        if ($deferrable.length) {
            $deferrable.trigger('reload');
        }
    });
});
