$().ready(function() {
    var $issue_container = $('#issue'),
        $issues_list_container = $('#issues-list'),
        current_issue_number = null;

    var on_issue_link_click = (function on_issue_link_click (e) {
        var link = this, $link = $(this), $item = $link.closest('.issue-item');
        e.preventDefault();
        e.stopPropagation();
        if ($item.hasClass('active')) { return; }
        current_issue_number = $link.data('issue-number');
        $.get(link.href, function(data) {
            if ($link.data('issue-number') != current_issue_number) { return; }
            $issue_container.html(data);
            $('.issue-item.active').removeClass('active');
            $item.addClass('active');
        });
    }); // on_issue_link_click

    var KEYUP = 38, KEYDOWN = 40, KEYHOME = 36, KEYEND = 35;

    var on_issues_list_keydown = (function on_issues_list_keydown (e) {
        if (e.ctrlKey || e.shiftKey || e.metaKey) { return; }

        var $issue_item = $(this),
            something_done = false,
            $issue_link, $list, $group;

        switch (e.keyCode) {
             case KEYUP:
                $issue_link = $issue_item.prev().find('.issue-link').first();
                if (!$issue_link.length) {
                    // try to get the last of the previous group
                    $issue_link = $issue_item.closest('.issues-group').prev().find('.issue-link').last();
                }
                break;
             case KEYDOWN:
                $issue_link = $issue_item.next().find('.issue-link').first();
                if (!$issue_link.length) {
                    // try to get the first of the next group
                    $issue_link = $issue_item.closest('.issues-group').next().find('.issue-link').first();
                }
                break;
            case KEYHOME:
                $issue_link = $issues_list_container.find('.issue-link').first();
                break;
            case KEYEND:
                $issue_link = $issues_list_container.find('.issue-link').last();
                break;
        }

        if ($issue_link && $issue_link.length) {
            // doing stuff if a new issue link must be focused

            // save the wanted issue number as the current one
            var issue_number = $issue_link.data('issue-number');
            current_issue_number = issue_number;

            $list = $issue_link.closest('ul');
            var focus_and_link = function () {
                // remove the previously event set on this function
                $list.off('shown', focus_and_link);
                // is the wanted issue is still the current asked one, go
                if (issue_number == current_issue_number) {
                    $issue_link.focus().click();
                }
            };

            if ($list.hasClass('collapse') && !$list.hasClass('in')) {
                // we are on a collapsed group, open it and when done, focus
                // the link
                $list.on('shown', focus_and_link);
                $list.collapse('show');
            } else {
                // normal and visible link, focus it
                focus_and_link();
            }
        } // if ($issue_link && $issue_link.length)

        if (something_done) {
            // stop event only if we did something with it
            e.preventDefault();
            e.stopPropagation();
        }
    }); // on_issues_list_keydown

    $(document).on('click', 'a.issue-link', on_issue_link_click);
    $(document).on('keydown', '.issue-item', on_issues_list_keydown);
});
