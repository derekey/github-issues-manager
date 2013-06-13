$().ready(function() {

    var Ev = {
        stop_event_decorate: (function stop_event_decorate(callback) {
            /* Return a function to use as a callback for an event
               Call the callback and if it returns false (strictly), the
               event propagation is stopped
            */
            var decorator = function(e) {
                if (e.isPropagationStopped()) { return false; }
                if (callback(e) === false) {
                    e.preventDefault();
                    e.stopPropagation();
                    return false;
                }
            };
            return decorator;
        }), // stop_event_decorate

        stop_event_decorate_dropdown: (function stop_event_decorate_dropdown(callback) {
            /* Return a function to use as a callback for clicks on dropdown items
               It will close the dropwdown before calling the callback, and will
               return false to tell to the main decorator to stop the event
            */
            var decorator = function(e) {
                var dropdown = $(e.target).closest('.dropdown');
                if (dropdown.hasClass('open')) {
                    dropdown.children('.dropdown-toggle').dropdown('toggle');
                }
                callback(e);
                return false;
            };
            return Ev.stop_event_decorate(decorator);
        }), // stop_event_decorate_dropdown

        key_decorate: (function key_decorate(callback) {
            /* Return a function to use as a callback for a jwery event
               Will cancel the call of the callback if the focus is actually on an
               input element.
               If not, the callback is called, and if it returns true
               (strictly), the event propagation is stopped
            */
            var decorator = function(e) {
                if ($(e.target).is(':input')) { return; }
                return callback(e);
            };
            return Ev.stop_event_decorate(decorator);
        }) // key_decorate
    };


    var IssuesListIssue = (function IssuesListIssue__constructor (node, issues_list_group) {
        this.group = issues_list_group;

        this.node = node;
        this.node.IssuesListIssue = this;
        this.$node = $(node);
        this.$link = this.$node.find(IssuesListIssue.link_selector);

        this.number = this.$node.data('issue-number');
    }); // IssuesListIssue__constructor

    IssuesListIssue.selector = '.issue-item';
    IssuesListIssue.link_selector = '.issue-link';

    IssuesListIssue.on_issue_node_event = (function IssuesListIssue_on_issue_node_event (group_method, stop) {
        var decorator = function(e) {
            var issue_node = $(e.target).closest(IssuesListIssue.selector);
            if (!issue_node.length || !issue_node[0].IssuesListIssue) { return; }
            return issue_node[0].IssuesListIssue[group_method]();
        };
        return stop ? Ev.stop_event_decorate(decorator) : decorator;
    }); // IssuesListIssue_on_issue_node_event

    IssuesListIssue.init_events = (function IssuesListIssue_init_events () {
        $(document).on('click', IssuesListIssue.link_selector, IssuesListIssue.on_issue_node_event('on_click', true));
    });

    IssuesListIssue.prototype.on_click = (function IssuesListIssue__on_click (e) {
        this.set_current(true);
        return false; // stop event propagation
    }); // IssuesListIssue__on_click

    IssuesListIssue.prototype.unset_current = (function IssuesListIssue__unset_current () {
        this.group.current_issue = null;
        this.$node.removeClass('active');
    }); // IssuesListIssue__unset_current

    IssuesListIssue.prototype.set_current = (function IssuesListIssue__set_current (propagate) {
        this.get_html();
        if (!this.group.no_visible_issues) {
            if (propagate) {
                this.group.list.set_current();
                this.group.set_current();
            }
            if (this.group.current_issue) {
                this.group.current_issue.unset_current();
            }
            this.group.current_issue = this;
            this.group.unset_active();
            this.$node.addClass('active');
            var issue = this;
            if (this.group.collapsed) {
                this.group.open(false, function() { issue.$link.focus(); });
            } else {
                this.$link.focus();
            }
        }
    }); // IssuesListIssue__set_current

    IssuesListIssue.prototype.get_html = (function IssuesListIssue__get_html (url) {
        if (!IssuesList.can_display_issue_html(this.number)) {
            return;
        }
        if (!url) { url = this.$link.attr('href'); }
        $.ajax({
            url: url,
            success: this.display_html,
            error: this.error_getting_html,
            context: this
        });
    }); // IssuesListIssue__get_html

    IssuesListIssue.prototype.display_html = (function IssuesListIssue__display_html (html) {
        IssuesList.display_issue_html(html, this.number);
    }); // IssuesListIssue__display_html

    IssuesListIssue.prototype.error_getting_html = (function IssuesListIssue__error_getting_html (jqXHR) {
        IssuesList.clear_issue_html('error ' + jqXHR.status);
    }); // IssuesListIssue__error_getting_html


    var IssuesListGroup = (function IssuesListGroup__constructor (node, issues_list) {
        this.list = issues_list;

        this.node = node;
        this.node.IssuesListGroup = this;
        this.$node = $(node);
        this.$link = this.$node.find(IssuesListGroup.link_selector);
        this.$issues_node = this.$node.find(IssuesListGroup.issues_list_selector);
        this.$count_node = this.$node.find('.issues-count');

        this.collapsable = this.$issues_node.hasClass('collapse');
        this.collapsed = this.collapsable && !this.$issues_node.hasClass('in');

        var group = this;
        this.issues = $.map(this.$node.find(IssuesListIssue.selector),
                    function(node) { return new IssuesListIssue(node, group); });
        this.filtered_issues = this.issues;
        this.current_issue = null;

        this.no_visible_issues = this.filtered_issues.length === 0;
    }); // IssuesListGroup__constructor

    IssuesListGroup.selector = '.issues-group';
    IssuesListGroup.link_selector = '.box-header';
    IssuesListGroup.issues_list_selector = '.issues-group-issues';

    IssuesListGroup.prototype.unset_active = (function IssuesListGroup__unset_active () {
        this.$node.removeClass('active');
    }); // IssuesListGroup__unset_active

    IssuesListGroup.prototype.set_active = (function IssuesListGroup__set_active () {
        if (this.current_issue) {
            this.current_issue.unset_current();
        }
        IssuesList.clear_issue_html();
        this.$node.addClass('active');
        this.$link.focus();
    }); // IssuesListGroup__set_active

    IssuesListGroup.prototype.unset_current = (function IssuesListGroup__unset_current () {
        this.unset_active();
        if (this.current_issue) {
            this.current_issue.unset_current();
        }
        this.list.current_group = null;
    }); // IssuesListGroup__set_current

    IssuesListGroup.prototype.set_current = (function IssuesListGroup__set_current (active) {
        if (this.list.current_group) {
            this.list.current_group.unset_current();
        }
        this.list.current_group = this;
        if (active) {
            this.set_active();
        }
    }); // IssuesListGroup__set_current

    IssuesListGroup.prototype.open = (function IssuesListGroup__open (set_active, on_shown_callback) {
        if (!this.collapsable || !this.collapsed || this.no_visible_issues) { return ; }
        if (set_active) { this.set_active(); }
        if (on_shown_callback) {
            var group = this,
                on_shown = function() {
                    group.$issues_node.off('shown', on_shown);
                    on_shown_callback();
                };
            this.$issues_node.on('shown', on_shown);
        }
        this.$issues_node.collapse('show');
        return false; // stop event propagation
    }); // IssuesListGroup__open

    IssuesListGroup.prototype.close = (function IssuesListGroup__close (set_active) {
        if (!this.collapsable || this.collapsed || this.no_visible_issues) { return; }
        if (set_active) { this.set_active(); }
        this.$issues_node.collapse('hide');
        return false; // stop event propagation
    }); // IssuesListGroup__close

    IssuesListGroup.prototype.toggle = (function IssuesListGroup__toggle (set_active) {
        if (!this.collapsable || this.no_visible_issues) { return; }
        return this.collapsed ? this.open(set_active) : this.close(set_active);
    }); // IssuesListGroup__toggle

    IssuesListGroup.on_group_node_event = (function IssuesListGroup_on_group_node_event (group_method, stop) {
        var decorator = function(e) {
            var group_node = $(e.target).closest(IssuesListGroup.selector);
            if (!group_node.length || !group_node[0].IssuesListGroup) { return; }
            return group_node[0].IssuesListGroup[group_method]();
        };
        return stop ? Ev.stop_event_decorate(decorator): decorator;
    }); // IssuesListGroup_on_group_node_event

    IssuesListGroup.on_current_group_key_event = (function IssuesListGroup_on_current_group_key_event (group_method, param) {
        var decorator = function(e) {
            if (!IssuesList.current) { return; }
            if (!IssuesList.current.current_group) { return; }
            return IssuesList.current.current_group[group_method](param);
        };
        return Ev.key_decorate(decorator);
    }); // IssuesListGroup_on_current_group_key_event

    IssuesListGroup.init_events = (function IssuesListGroup_init_events () {
        $(document).on('click', IssuesListGroup.link_selector, IssuesListGroup.on_group_node_event('on_click', true));
        $(document).on('show', IssuesListGroup.issues_list_selector, IssuesListGroup.on_group_node_event('on_show'));
        $(document).on('hide', IssuesListGroup.issues_list_selector, IssuesListGroup.on_group_node_event('on_hide'));
        jwerty.key('o/→', IssuesListGroup.on_current_group_key_event('open', true));
        jwerty.key('c/←', IssuesListGroup.on_current_group_key_event('close', true));
        jwerty.key('t', IssuesListGroup.on_current_group_key_event('toggle'));
        jwerty.key('⇞', IssuesListGroup.on_current_group_key_event('go_to_first_issue_if_opened'));
        jwerty.key('⇟', IssuesListGroup.on_current_group_key_event('go_to_last_issue_if_opened'));
    });

    IssuesListGroup.prototype.on_click = (function IssuesListGroup__on_click (e) {
        this.list.set_current();
        this.set_current(true);
        this.toggle(true);
        return false; // stop event propagation
    }); // IssuesListGroup__on_click

    IssuesListGroup.prototype.go_to_previous_item = (function IssuesListGroup__go_to_previous_item () {
        if (this.collapsed || this.no_visible_issues) { return; }
        // if we have no current issue, abort
        if (!this.current_issue) { return; }
        // try to select the previous issue
        var previous_issue = this.get_previous_issue();
        if (previous_issue) {
            previous_issue.set_current();
        } else {
            // no previous issue, select the current group itself
            this.set_active();
        }
        return false; // stop event propagation
    }); // IssuesListGroup__go_to_previous_item

    IssuesListGroup.prototype.go_to_next_item = (function IssuesListGroup__go_to_next_item () {
        if (this.collapsed || this.no_visible_issues) { return; }
        // if we have no current issue, select the first issue if we have one
        if (!this.current_issue) {
            if (!this.filtered_issues.length) { return; }
            this.filtered_issues[0].set_current();
            return false; // stop event propagation
        }
        // try to select the next issue
        var next_issue = this.get_next_issue();
        if (!next_issue) { return; }
        next_issue.set_current();
        return false; // stop event propagation
    }); // IssuesListGroup__go_to_next_item

    IssuesListGroup.prototype.go_to_first_issue = (function IssuesListGroup__go_to_first_issue (propagate) {
        if (this.collapsed || this.no_visible_issues) { return; }
        this.filtered_issues[0].set_current(propagate);
        return false; // stop event propagation
    }); // IssuesListGroup__go_to_first_issue

    IssuesListGroup.prototype.go_to_first_issue_if_opened = (function IssuesListGroup__go_to_first_issue_if_opened (propagate) {
        if (!this.current_issue) { return; }
        return this.go_to_first_issue(propagate);
    }); // IssuesListGroup__go_to_first_issue_if_opened

    IssuesListGroup.prototype.go_to_last_issue = (function IssuesListGroup__go_to_last_issue (propagate) {
        if (this.collapsed || this.no_visible_issues) { return; }
        this.filtered_issues[this.filtered_issues.length-1].set_current(propagate);
        return false; // stop event propagation
    }); // IssuesListGroup__go_to_last_issue

    IssuesListGroup.prototype.go_to_last_issue_if_opened = (function IssuesListGroup__go_to_last_issue_if_opened (propagate) {
        if (!this.current_issue) { return; }
        return this.go_to_last_issue(propagate);
    }); // IssuesListGroup__go_to_last_issue_if_opened

    IssuesListGroup.prototype.get_previous_issue = (function IssuesListGroup__get_previous_issue () {
        if (!this.current_issue) { return false; }
        var pos = this.filtered_issues.indexOf(this.current_issue);
        if (pos < 1) { return null; }
        return this.filtered_issues[pos - 1];
    }); // IssuesListGroup__get_previous_issue

    IssuesListGroup.prototype.get_next_issue = (function IssuesListGroup__get_next_issue () {
        if (!this.current_issue) {
            if (!this.filtered_issues.length) { return null; }
            return this.filtered_issues[0];
        }
        var pos = this.filtered_issues.indexOf(this.current_issue);
        if (pos == this.filtered_issues.length - 1) { return null; }
        return this.filtered_issues[pos + 1];
    }); // IssuesListGroup__get_next_issue

    IssuesListGroup.prototype.on_show = (function IssuesListGroup__on_show () {
        this.collapsed = false;
    }); // IssuesListGroup__on_show

    IssuesListGroup.prototype.on_hide = (function IssuesListGroup__on_hide () {
        this.collapsed = true;
    }); // IssuesListGroup__on_hide

    IssuesListGroup.prototype.get_issue_by_number = (function IssuesListGroup__get_issue_by_number(number) {
        var issue = null;
        for (var i = 0; i < this.issues.length; i++) {
            if (this.issues[i].number == number) {
                issue = this.issues[i];
                break;
            }
        }
        return issue;
    }); // IssuesListGroup__get_issue_by_number

    IssuesListGroup.prototype.update_filtered_issues = (function IssuesListGroup__update_filtered_issues () {
        this.filtered_issues = [];
        for (var i = 0; i < this.issues.length; i++) {
            var issue = this.issues[i];
            if (!issue.$node.hasClass('hidden')) {
                this.filtered_issues.push(issue);
            }
        }
        this.no_visible_issues = this.filtered_issues.length === 0;
        var filtered_length = this.filtered_issues.length,
            total_length = this.issues.length;
        this.$count_node.text(filtered_length == total_length ? total_length : filtered_length + '/' + total_length);
    }); // update_filtered_issues


    var IssuesList = (function IssuesList__constructor (node) {
        this.node = node;
        this.node.IssuesList = this;
        this.$node = $(node);
        this.$search_input = this.$node.find('.quicksearch');
        if (!this.$search_input.length && this.$node.data('quicksearch')) {
            this.$search_input = $(this.$node.data('quicksearch'));
        }

        var list = this;
        this.groups = $.map(this.$node.find(IssuesListGroup.selector),
                        function(node) { return new IssuesListGroup(node, list); });
        this.current_group = null;
    }); // IssuesList__constructor

    IssuesList.selector = '.issues-list';
    IssuesList.modal_window = $('#modal-issue-view');
    IssuesList.modal_window_body = IssuesList.modal_window.children('.modal-body');
    IssuesList.issue_container = $('.main-issue-container');
    IssuesList.all = [];
    IssuesList.current = null;

    IssuesList.prototype.unset_current = (function IssuesList__unset_current () {
    }); // IssuesList__unset_current

    IssuesList.prototype.set_current = (function IssuesList__set_current () {
        if (IssuesList.current) {
            IssuesList.current.unset_current();
        }
        IssuesList.current = this;
    }); // IssuesList__set_current

    IssuesList.init_all = (function IssuesList_init_all () {
        IssuesList.all = $.map($(IssuesList.selector),
                            function(node) { return new IssuesList(node); });
        if (IssuesList.all.length) {
            IssuesList.all[0].set_current();
        }
        IssuesListIssue.init_events();
        IssuesListGroup.init_events();
        IssuesList.init_events();
    }); // IssuesList_init_all

    IssuesList.on_current_list_key_event = (function IssuesList_key_decorate (list_method) {
        var decorator = function(e) {
            if (!IssuesList.current) { return; }
            return IssuesList.current[list_method]();
        };
        return Ev.key_decorate(decorator);
    });

    IssuesList.init_events = (function IssuesList_init_event () {
        jwerty.key('p/k/↑', IssuesList.on_current_list_key_event('go_to_previous_item'));
        jwerty.key('n/j/↓', IssuesList.on_current_list_key_event('go_to_next_item'));
        jwerty.key('⇞', IssuesList.on_current_list_key_event('go_to_first_group'));
        jwerty.key('⇟', IssuesList.on_current_list_key_event('go_to_last_group'));
        jwerty.key('s', IssuesList.on_current_list_key_event('focus_search_input'));
        jwerty.key('ctrl+u', IssuesList.on_current_list_key_event('clear_search_input'));
        jwerty.key('d', Ev.key_decorate(IssuesList.toggle_details));
        for (var i = 0; i < IssuesList.all.length; i++) {
            var issues_list = IssuesList.all[i];
            if (issues_list.$search_input.length) {
                issues_list.$search_input.on('quicksearch.after', $.proxy(issues_list.on_filter_done, issues_list));
                issues_list.$search_input.on('keydown', jwerty.event('↑', issues_list.go_to_previous_item, issues_list));
                issues_list.$search_input.on('keydown', jwerty.event('↓', issues_list.go_to_next_item, issues_list));
                issues_list.$search_input.on('keydown', jwerty.event('ctrl+u', issues_list.clear_search_input, issues_list));
            }
        }
    }); // IssuesList_init_event

    IssuesList.prototype.on_filter_done = (function IssuesList__on_filter_done () {
        var continue_issue_search = this.$search_input.val() !== '';
        for (var i = 0; i < this.groups.length; i++) {
            var group = this.groups[i];
            group.update_filtered_issues();
            if (continue_issue_search !== false) {
                continue_issue_search = group.go_to_first_issue(true);
                if (continue_issue_search === false) {
                    this.$search_input.focus();
                }
            }
        }
        if (continue_issue_search !== false) {
            this.go_to_first_group();
            this.$search_input.focus();
        }

    }); // on_filter_done

    IssuesList.prototype.focus_search_input = (function IssuesList__focus_search_input () {
        if (!this.$search_input.length) { return; }
        this.$search_input.focus();
        return false;
    }); // IssuesList__focus_search_input

    IssuesList.prototype.clear_search_input = (function IssuesList__clear_search_input () {
        if (!this.$search_input.length) { return; }
        this.$search_input.val('');
        this.$search_input.data('quicksearch').trigger_search();
        return false;
    }); // IssuesList__clear_search_input

    IssuesList.prototype.go_to_previous_item = (function IssuesList__go_to_previous_item () {
        // if we have no current group, abort
        if (!this.current_group) { return; }
        // try to select the previous issue on the current group
        if (this.current_group.go_to_previous_item() === false) {
            return false; // stop event propagation
        }
        // no previous issue on the current group, try to select the previous group
        var previous_group = this.get_previous_group();
        if (!previous_group) {
            if (this.$search_input.length) {
                this.current_group.unset_current();
                this.$search_input.focus();
            }
            return false; // stop event propagation
        }
        if (previous_group.collapsed || previous_group.no_visible_issues) {
            previous_group.set_current(true);
        } else {
            previous_group.set_current();
            previous_group.go_to_last_issue();
        }
        return false; // stop event propagation
    }); // IssuesList__go_to_previous_item

    IssuesList.prototype.go_to_next_item = (function IssuesList__go_to_next_item () {
        // if we have no current group, select the first group if we have one
        if (!this.current_group) {
            if (!this.groups.length) { return; }
            this.groups[0].set_current(true);
            return false; // stop event propagation
        }
        // try to select the next issue on the current group
        if (this.current_group.go_to_next_item() === false) {
            return false; // stop event propagation
        }
        // no next issue on the current group, try to select the next group
        var next_group = this.get_next_group();
        if (!next_group) { return; }
        this.current_group.unset_current();
        next_group.set_current(true);
        return false; // stop event propagation
    }); // IssuesList__go_to_next_item

    IssuesList.prototype.get_previous_group = (function IssuesList__get_previous_group () {
        if (!this.current_group) { return null; }
        var pos = this.groups.indexOf(this.current_group);
        if (pos < 1) { return null; }
        return this.groups[pos - 1];
    }); // IssuesList__get_previous_group

    IssuesList.prototype.get_next_group = (function IssuesList__get_next_group () {
        if (!this.current_group) {
            if (!this.groups.length) { return null; }
            return this.groups[0];
        }
        var pos = this.groups.indexOf(this.current_group);
        if (pos == this.groups.length - 1) { return null; }
        return this.groups[pos + 1];
    }); // IssuesList__get_next_group

    IssuesList.prototype.go_to_first_group = (function IssuesList__go_to_first_group () {
        if (!this.groups.length) { return; }
        this.groups[0].set_current(true);
        return false; // stop event propagation
    }); // IssuesList__go_to_first_group

    IssuesList.prototype.go_to_last_group = (function IssuesList__go_to_last_group () {
        if (!this.groups.length) { return; }
        this.groups[this.groups.length - 1].set_current(true);
        return false; // stop event propagation
    }); // IssuesList__go_to_last_group

    IssuesList.get_issue_html_container = (function IssuesList_get_issue_html_container () {
        if (IssuesList.issue_container.length) {
            return {
                $window: null,
                $node: IssuesList.issue_container
            };
        } else {
            return {
                $window: IssuesList.modal_window,
                $node: IssuesList.modal_window_body
            };
        }
    }); // IssuesList_get_issue_html_container

    IssuesList.can_display_issue_html = (function IssuesList_can_display_issue_html (issue_number) {
        var container = IssuesList.get_issue_html_container();
        if (container.$node.data('issue-number') == issue_number) { return false; }
        container.$node.data('issue-number', issue_number);
        return true;
    }); // IssuesList_can_display_issue_html

    IssuesList.display_issue_html = (function IssuesList_display_issue_html (html, issue_number) {
        var container = IssuesList.get_issue_html_container();
        if (container.$node.data('issue-number') != issue_number) { return; }
        container.$node.html(html);
        if (container.$window) {
            container.$window.modal("show");
        }
    }); // IssuesList_display_issue_html

    IssuesList.clear_issue_html = (function IssuesList_clear_issue_html (code) {
        var container = IssuesList.get_issue_html_container();
        container.$node.data('issue-number', 0);
        container.$node.html('<p class="empty-column">' + (code ? code + ' :(' : '...') + '</p>');
    }); // IssuesList_clear_issue_html

    IssuesList.toggle_details = (function IssuesList_toggle_details () {
        for (var i = 0; i < IssuesList.all.length; i++) {
            var list = IssuesList.all[i];
            list.$node.toggleClass('without-details');
        }
        return false; // stop event propagation
    }); // IssuesList_toggle_details

    IssuesList.close_all_groups = (function IssuesList_close_all_groups () {
        for (var i = 0; i < IssuesList.all.length; i++) {
            var list = IssuesList.all[i];
            list.close_all_groups();
        }
        return false; // stop event propagation
    }); // IssuesList_close_all_groups

    IssuesList.prototype.close_all_groups = (function IssuesList__close_all_groups () {
        for (var i = 0; i < this.groups.length; i++) {
            var group = this.groups[i];
            group.close();
        }
        return false; // stop event propagation
    }); // IssuesList__close_all_groups

    IssuesList.open_all_groups = (function IssuesList_open_all_groups () {
        for (var i = 0; i < IssuesList.all.length; i++) {
            var list = IssuesList.all[i];
            list.open_all_groups();
        }
        return false; // stop event propagation
    }); // IssuesList_open_all_groups

    IssuesList.prototype.open_all_groups = (function IssuesList__open_all_groups () {
        for (var i = 0; i < this.groups.length; i++) {
            var group = this.groups[i];
            group.open();
        }
        return false; // stop event propagation
    }); // IssuesList__open_all_groups

    IssuesList.get_issue_by_number = (function IssuesList_get_issue_by_number(number) {
        var issue = null;
        for (var i = 0; i < IssuesList.all.length; i++) {
            issue = IssuesList.all[i].get_issue_by_number(number);
            if (issue) { break; }
        }
        return issue;
    }); // IssuesList_get_issue_by_number

    IssuesList.prototype.get_issue_by_number = (function IssuesList__get_issue_by_number(number) {
        var issue = null;
        for (var i = 0; i < this.groups.length; i++) {
            issue = this.groups[i].get_issue_by_number(number);
            if (issue) { break; }
        }
        return issue;
    }); // IssuesList__get_issue_by_number

    IssuesList.init_all();

    var IssueByNumber = {
        $window: $('#go-to-issue-window'),
        $form: $('#go-to-issue-window form'),
        $input: $('#go-to-issue-window form input'),
        open: (function IssueByNumber_open () {
            IssueByNumber.$window.modal('show');
        }), // IssueByNumber_open
        on_show: (function IssueByNumber_on_show (e) {
            IssueByNumber.$input.val('');
        }), // IssueByNumber_on_show
        on_shown: (function IssueByNumber_on_shown (e) {
            IssueByNumber.$input.focus();
            IssueByNumber.$input.prop('placeholder', "Type an issue number");

        }), //IssueByNumber_on_shown
        on_submit: (function IssueByNumber_on_submit (e) {
            var number = IssueByNumber.$input.val(),
                fail = false;
            if (!number) {
                fail = true;
            } else if (number[0] == '#') {
                number = number.slice(1);
            }
            IssueByNumber.$input.val('');
            if (!fail && !isNaN(number)) {
                IssueByNumber.$window.modal('hide');
                IssueByNumber.$input.prop('placeholder', "Type an issue number");
                IssueByNumber.open_issue(number);
            } else {
                IssueByNumber.$input.prop('placeholder', "Type a correct issue number");
            IssueByNumber.$input.focus();
            }
        }), // IssueByNumber_on_submit
        open_issue: (function IssueByNumber_open_issue (number) {
            var issue = IssuesList.get_issue_by_number(number);
            if (issue) {
                issue.set_current(true);
            } else {
                var url = IssueByNumber.$input.data('base-url') + number + '/';
                issue = new IssuesListIssue({}, null);
                issue.number = number;
                issue.get_html(url);
            }
        }), // IssueByNumber_on_submit
        init_events: (function IssueByNumber_init_events () {
            jwerty.key('i/⇧+#', Ev.key_decorate(IssueByNumber.open));  // "#" is shift-3 ?!?
            IssueByNumber.$window.on('show', IssueByNumber.on_show);
            IssueByNumber.$window.on('shown', IssueByNumber.on_shown);
            IssueByNumber.$form.on('submit', Ev.stop_event_decorate(IssueByNumber.on_submit));
        }) // IssueByNumber_init_events
    };

    IssueByNumber.init_events();

    var on_resize_issue_click = (function on_resize_issue_click(e) {
        $('body').toggleClass('big-issue');
        return false; // stop event propagation
    }); // on_resize_issue_click

    var on_help = (function on_help(e) {
        $('#show-shortcuts').click();
        return false; // stop event propagation
    }); // on_help

    // keyboard events
    jwerty.key('f', Ev.key_decorate(on_resize_issue_click));
    $(document).on('click', '#resize-issue', Ev.stop_event_decorate(on_resize_issue_click));
    jwerty.key('?/⇧+slash', Ev.key_decorate(on_help));  // slash is "/"
    $(document).on('click', '#toggle-issues-details', Ev.stop_event_decorate_dropdown(IssuesList.toggle_details));
    $(document).on('click', '#close-all-groups', Ev.stop_event_decorate_dropdown(IssuesList.close_all_groups));
    $(document).on('click', '#open-all-groups', Ev.stop_event_decorate_dropdown(IssuesList.open_all_groups));


    // select the issue given in the url's hash, or an active one in the html,
    // or the first item of the current list
    if (IssuesList.all.length) {
        IssuesList.all[0].set_current();
        var issue_to_select = null;
        if (location.hash && /^#issue\-\d+$/.test(location.hash)) {
            issue_to_select = $(location.hash);
            if (issue_to_select.length && issue_to_select[0].IssuesListIssue) {
                issue_to_select[0].IssuesListIssue.set_current(true);
            } else {
                issue_to_select = null;
            }
        } else {
            issue_to_select = $(IssuesListIssue.selector + '.active');
            if (issue_to_select.length) {
                issue_to_select.removeClass('active');
                issue_to_select[0].IssuesListIssue.set_current(true);
            } else {
                issue_to_select = null;
            }
        }
        if (!issue_to_select) {
            IssuesList.current.go_to_next_item();
        }
    }

    var activate_quicksearches = (function activate_quicksearches () {
        $('input.quicksearch').each(function() {
            var input, target, content, options, qs;
            $input = $(this);
            if (!$input.data('quicksearch')) {
                target = $input.data('target'),
                content = $input.data('content'),
                options = {
                    show: function () {
                        this.style.display = "";
                        $(this).removeClass('hidden');
                    },
                    hide: function() {
                        this.style.display = "none";
                        $(this).addClass('hidden');
                    },
                    onBefore: function() {
                        $input.trigger('quicksearch.before');
                    },
                    onAfter: function() {
                        $input.trigger('quicksearch.after');
                    }
                };
                if (target) {
                    if (content) {
                        options.selector = content;
                    }
                    qs = $input.quicksearch(target, options);
                    $input.data('quicksearch', qs);
                }
            }
        });
    });
    activate_quicksearches();
});
