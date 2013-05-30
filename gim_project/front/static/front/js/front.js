$().ready(function() {
    var $issue_container = $('#issue');

    var on_issue_link_click = (function on_issue_link_click (e) {
        var link = this;
        e.preventDefault();
        e.stopPropagation();
        $.get(this.href, function(data) {
            $issue_container.html(data);
            $('.issue-item.active').removeClass('active');
            $(link).closest('.issue-item').addClass('active');
        });
    });

    $(document).on('click', 'a.issue-link', on_issue_link_click);
});
