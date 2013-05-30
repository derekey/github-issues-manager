$().ready(function() {
    var $issue_container = $('#issue');

    var on_issue_link_click = (function on_issue_link_click (e) {
        e.preventDefault();
        e.stopPropagation();
        $.get(this.href, function(data) {
            $('#issue').html(data);
        });
    });

    $(document).on('click', 'a.issue-link', on_issue_link_click);
});
